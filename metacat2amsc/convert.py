from metacat.webapi import MetaCatClient
from .conversion_dicts import meta2amsc_dict
from .version import __version
from .amsc_client import AmSCClient
import os
import json
import requests
import urllib.parse
import logging
import traceback
logger = logging.getLogger(__name__)

class fqncache:
    def __init__(self, mcc):
        self.fqnmap = {}
        self.mcc = mcc
        whoami = self.mcc.auth_info()
        if not whoami:
            raise AuthenticationError("not logged into metacat")

    def register_fqn(self, name, namespace, fqn):
        did = f"{namespace}:{name}"
        self.fqnmap[did] = fqn

    def lookup_fqn(self, namespace, name):
        did = f"{namespace}:{name}"
        if not self.fqnmap.get(did,""):
            print(f"looking up fqn for {did}...")
            try:
                md = self.mcc.get_dataset(did=did)
            except Exception as e:
                print(f"failed looking up:")
                traceback.print_exc()
                exit(1)

            if md and "AmSC.common.fqn" in md["metadata"]:
                self.fqnmap[did] = md["metadata"]["AmSC.common.fqn"]
            else:
                print(f"no fqn found in metadata {md=}")
                exit(1)

        if not  self.fqnmap.get(did, ""):
            logger.warning(f"Error: Unable to find fqn for: {did}")
        return self.fqnmap.get(did, "")


def field_convert(entry, fc):
    res = {}
    extra = {
       "converter": "meta_cat2amsc",
       "converter_version": __version,
    }
    for k in entry:
        if k in meta2amsc_dict:
             if entry[k]:
                 res[meta2amsc_dict[k]] = entry[k]
             else:
                 res[meta2amsc_dict[k]] = None
        else:
             if k not in ("metadata",) and entry[k]:
                 extra[f"MetaCat.{k}"] = entry[k]

    for k in entry["metadata"]:
        if k in meta2amsc_dict:
             if entry["metadata"][k]:
                 res[meta2amsc_dict[k]] = entry["metadata"][k]
             else:
                 res[meta2amsc_dict[k]] = None
        else:
             if k not in ("metadata",) and entry["metadata"][k]:
                 extra[k] = entry["metadata"][k]

    # special conversion cases:
    if "parent_fqn" in res and res["parent_fqn"]:
        try:
            res["parent_fqn"] = ",".join([ fc.lookup_fqn(x["namespace"], x["name"]) for x in res["parent_fqn"] ])
        except:
            print(f"unable to convert parent_fqn: {repr(res['parent_fqn'])}!")
            res["parent_fqn"] = ""

    if "location" not in res:
        res["location"] = "http://www.fnal.gov/"

    # extra isn't actually supported yet...
    # res["extra"] = extra
    return res

def convert(cf):
    print("entering convert")
    mcsu = cf.get("metacat", "server_url")
    mcasu = cf.get("metacat", "auth_server_url")
    #mcuser = cf.get("metacat", "user")

    # in development, we need an ssh tunnel to get to the AMSC API..."
    tunnel = cf.get("general", "tunnel_command")
    if tunnel:
        print(f"running: {tunnel}") 
        os.system(tunnel)

    #mcc = MetaCatClient(server_url=mcsu, auth_server_url=mcasu)
    mcc = MetaCatClient()
    fc = fqncache(mcc)
    amscc = AmSCClient(cf)

    #mcc.login_token(cf.get("general", mcuser))

    queries_list = cf.get("general", "query_list", fallback="general").split(" ")
    print(f"{queries_list=}")
    for qsect in queries_list:

        fq = cf.get(qsect, "file_query")
        dq = cf.get(qsect, "dataset_query")

        print(f"querying: {dq}")
        dataset_list = list(mcc.query(dq, with_metadata=True, with_provenance=True))

        for d_entry in dataset_list:
            print(f"{d_entry=}")
            amsc_data = field_convert(d_entry, fc)

            if 'fn.locations' in d_entry and d_entry['fn.locations']:
               amsc_data['description'] += "\nAvailable via:"
               for loc in d_entry['fn.locations']:
                   amsc_data['description'] =  f"{amsc_data['description']}\n* {loc}"
            if 'fn.tape_stage_in' in d_entry and d_entry['fn.tape_stage_in']:
               amsc_data['description'] = f"{amsc_data['description']}\nRequest Stage-in from tape here:\n{d_entry['fn.tape_stage_in']}"

            if amsc_data.get("fqn") and not amscc.get(amsc_data["fqn"]):
                print("we think we migrated it, but its gone...")
                del amsc_data["fqn"]

            if not amsc_data.get("fqn",None):
                # not previously migrated, or deleted
                if "fqn" in amsc_data:
                    del amsc_data["fqn"]
                if "updated_by" in amsc_data:
                    del amsc_data["updated_by"]
                if "updated_at" in amsc_data:
                    del amsc_data["updated_at"]
                if "parent_fqn" in amsc_data and not amsc_data["parent_fqn"]:
                    del amsc_data["parent_fqn"]
                res_data = amscc.post_create(amsc_data)

                if "fqn" in res_data:
                    # remember fqn, and update in metacat
                    fc.register_fqn(d_entry['namespace'], d_entry['name'], res_data.get("fqn",None))

                    
                    mcc.update_dataset(
                        dataset=f'{d_entry["namespace"]}:{d_entry["name"]}',
                        metadata={"AmSC.common.fqn":res_data.get("fqn", "")},
                    )
            else:
                # previously migrated: update
                duflag = fc.getboolean("general","update_by_delete_add", fallback=False)
                if duflag:
                    res_data = amscc.delete_catalog(amsc_data)
                    res_data = amscc.post_create(amsc_data)
                else:
                    res_data = amscc.put_update(amsc_data)

                # remember fqn
                fc.register_fqn(d_entry['namespace'], d_entry['name'], res_data.get("fqn",None))
            

        file_list = mcc.query(fq)
        for file_info in file_list:

            file_entry = mcc.get_file(name = file_info["name"], namespace = file_info["namespace"], with_datasets=True)
            amsc_data = field_convert(file_entry, fc)

            print(f"{file_info=}")

            if not amsc_data.get("parent_fqn", ""):
                print(f"Skipping file {file_info['name']}, parent dataset not migrated")
                continue

            if amsc_data.get("fqn") and not amscc.get(amsc_data["fqn"]):
                print("we think we migrated it, but its gone...")
                del amsc_data["fqn"]

            if not amsc_data.get("fqn",None):
                # not previously migrated, or deleted
                print(f"I would post {json.dumps(amsc_data,indent=4)}")
                if "fqn" in amsc_data:
                    del amsc_data["fqn"]
                if "updated_by" in amsc_data:
                    del amsc_data["updated_by"]
                res_data = amscc.post_create(amsc_data)
                if "fqn" in res_data:
                    mcc.update_file( 
                        namespace=file_info["namespace"],
                        name=file_info["name"],
                        metadata={"AmSC.common.fqn": res_data["fqn"]}
                    )
            else:
                # previously migrated
                res_data = amscc.put_update(amsc_data)

