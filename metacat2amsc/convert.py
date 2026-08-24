from metacat.webapi import MetaCatClient
from .conversion_dicts import meta2amsc_dict
from .version import __version
from .amsc_client import AmSCClient
import os
import json
import requests
import urllib.parse
import logging
import re
import time
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
        if not self.fqnmap.get(did, ""):
            logging.debug(f"looking up fqn for {did}...")
            try:
                md = self.mcc.get_dataset(did=did)
            except Exception as e:
                logging.debug(f"failed looking up:")
                traceback.print_exc()
                exit(1)

            if md and "AmSC.common.fqn" in md["metadata"]:
                self.fqnmap[did] = md["metadata"]["AmSC.common.fqn"]
            else:
                logging.debug(f"no fqn found in metadata {md=}")
                exit(1)

        if not self.fqnmap.get(did, ""):
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
            res["parent_fqn"] = ",".join(
                [fc.lookup_fqn(x["namespace"], x["name"]) for x in res["parent_fqn"]]
            )
        except:
            logging.debug(f"unable to convert parent_fqn: {repr(res['parent_fqn'])}!")
            res["parent_fqn"] = ""

    if "location" not in res:
        res["location"] = "http://www.fnal.gov/"

    # extra isn't actually supported yet...
    # res["extra"] = extra
    return res

def convert(cf):
    migrated_files = []
    migrated_datasets = []
    logging.debug("entering convert")
    mcsu = cf.get("metacat", "server_url", fallback=os.environ.get("METACAT_SERVER_URL",None))
    mcasu = cf.get("metacat", "auth_server_url", fallback=os.environ.get("METACAT_AUTH_SERVER_URL",None))
    # mcuser = cf.get("metacat", "user")

    # in development, we need an ssh tunnel to get to the AMSC API..."
    tunnel = cf.get("general", "tunnel_command")
    if tunnel:
        logging.debug(f"running: {tunnel}")
        os.system(tunnel)

    # default timestamp to epoch...
    timestamp = "1970-01-01T00:00:00+00"
    timestamp_file = cf.get("general", "timestamp_file", fallback="")

    if timestamp_file:
        if os.path.exists(timestamp_file):
            logging.debug(f"getting last run time from {timestamp_file=}")
            sbuf = os.stat(timestamp_file)
            timestamp = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.gmtime(sbuf.st_mtime))
            logging.debug(f"got {timestamp=}")

        # update time on timestamp file, save start time
        open(timestamp_file, mode="w").close()

    start_timestamp = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.gmtime(time.time()))

    mcc = MetaCatClient(server_url=mcsu, auth_server_url=mcasu)

    fc = fqncache(mcc)
    amscc = AmSCClient(cf)
    duflag = cf.getboolean("general", "update_by_delete_add", fallback=False)

    do_htgettoken = cf.get("metacat", "htgettoken", fallback="")
    if do_htgettoken:
        os.system(do_htgettoken)
    
    login_user = cf.get("metacat", "user", fallback="")
    if login_user:
        mcc.login_token(login_user)

    queries_list = cf.get("general", "query_list", fallback="").split(" ")
    if not queries_list or not queries_list[0]:
        namespace_skip_pat = cf.get("general", "namespace_skip_pat", fallback=".*")
        queries_list = [
           x['name'] 
           for x in mcc.list_namespaces() 
               if not re.search(namespace_skip_pat, x['name'])
        ]

    fqt = cf.get("general", "file_query_template", fallback="")
    dqt = cf.get("general", "dataset_query_template", fallback="")

    logging.debug(f"{queries_list=}")

    for namespace in queries_list:

        if fqt:
            fq = fqt.replace('{namespace}', namespace)
        else:
            fq = cf.get(namespace, "file_query" )
        
        if dqt:
            dq = dqt.replace('{namespace}', namespace)
        else:
            dq = cf.get(namespace, "dataset_query")


        if fq.find("%timestamp") > 0:
           fq = fq.replace('%timestamp', f"'{timestamp}'") 
        else:
            fq = f"{fq} and updated_timestamp > '{timestamp}'"

        logging.debug(f"querying: {dq}")
        dataset_list = list(mcc.query(dq, with_metadata=True, with_provenance=True))
        for d_entry in dataset_list:
            logging.debug(f"{d_entry=}")
            amsc_data = field_convert(d_entry, fc)

            if "fn.locations" in d_entry and d_entry["fn.locations"]:
                amsc_data["description"] += "\nAvailable via:"
                for loc in d_entry["fn.locations"]:
                    amsc_data["description"] = f"{amsc_data['description']}\n* {loc}"
            if "fn.tape_stage_in" in d_entry and d_entry["fn.tape_stage_in"]:
                amsc_data[
                    "description"
                ] = f"{amsc_data['description']}\nRequest Stage-in from tape here:\n{d_entry['fn.tape_stage_in']}"

            if amsc_data.get("fqn") and not amscc.get(amsc_data["fqn"]):
                logging.debug("we think we migrated it, but its gone...")
                del amsc_data["fqn"]

            if not amsc_data.get("fqn", None):
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
                    fc.register_fqn(
                        d_entry["namespace"], d_entry["name"], res_data.get("fqn", None)
                    )

                    mcc.update_dataset(
                        dataset=f'{d_entry["namespace"]}:{d_entry["name"]}',
                        metadata={"AmSC.common.fqn": res_data.get("fqn", "")},
                    )
            else:
                # previously migrated: update
                if duflag:
                    res_data = amscc.delete_item(amsc_data)
                    res_data = amscc.post_create(amsc_data)
                else:
                    res_data = amscc.put_update(amsc_data)

                # remember fqn
                fc.register_fqn(
                    d_entry["namespace"], d_entry["name"], res_data.get("fqn", None)
                )

            migrated_datasets.append(f'{d_entry["namespace"]}:{d_entry["name"]}')

        file_list = mcc.query(fq)
        for file_info in file_list:

            file_entry = mcc.get_file(
                name=file_info["name"],
                namespace=file_info["namespace"],
                with_datasets=True,
            )
            amsc_data = field_convert(file_entry, fc)

            logging.debug(f"{file_info=}")

            if not amsc_data.get("parent_fqn", ""):
                logging.debug(
                    f"Skipping file {file_info['name']}, parent dataset not migrated"
                )
                continue

            if amsc_data.get("fqn") and not amscc.get(amsc_data["fqn"]):
                logging.debug("we think we migrated it, but its gone...")
                del amsc_data["fqn"]

            if not amsc_data.get("fqn", None):
                # not previously migrated, or deleted
                logging.debug(f"I would post {json.dumps(amsc_data,indent=4)}")
                if "fqn" in amsc_data:
                    del amsc_data["fqn"]
                if "updated_by" in amsc_data:
                    del amsc_data["updated_by"]
                res_data = amscc.post_create(amsc_data)
                if "fqn" in res_data:
                    mcc.update_file(
                        namespace=file_info["namespace"],
                        name=file_info["name"],
                        metadata={"AmSC.common.fqn": res_data["fqn"]},
                    )
            else:
                # previously migrated
                if duflag:
                    res_data = amscc.delete_item(amsc_data)
                    res_data = amscc.post_create(amsc_data)
                else:
                    res_data = amscc.put_update(amsc_data)

            migrated_files.append(f'{file_info["namespace"]}:{file_info["name"]}')

    # update timestamp again at end
    if timestamp_file:
        open(timestamp_file, mode="w").close()

    # check for files/datasets that appeared since we started, but didn't get migrated,
    # and bump their dates so the next run will pick them up.
    # we could try to migrate them, but that leads to a hall of mirrors where we 
    # then have to migrate any files declared while *that* pass was running, etc.
  
    for namespace in queries_list:

        if fqt:
            fq = fqt.replace('{namespace}', namespace)
        else:
            fq = cf.get(qsect, "file_query", "")
        
        if dqt:
            dq = dqt.replace('{namespace}', namespace)
        else:
            dq = cf.get(namespace, "dataset_query")

        if fq.find("%timestamp") > 0:
           fq = fq.replace('%timestamp', f"'{start_timestamp}'") 
        else:
            fq = f"{fq} and updated_timestamp > '{start_timestamp}'"

        logging.debug(f"re-querying: {dq}")
        dataset_list = list(mcc.query(dq, with_metadata=True, with_provenance=True))
        for d_entry in dataset_list:

            did = f"{d_entry['namespace']}:{d_entry['name']}" 
            if not did in migrated_datasets:
                # the type should already be this, this just fixes the update_timestamp
                mcc.update_dataset( did, metadata={"AmSC.common.type": "scientificWork"})

        file_list = mcc.query(fq)
        for file_info in file_list:
            did = f"{d_entry['namespace']}:{d_entry['name']}" 
            if not did in migrated_files:
                # the type should already be this, this just fixes the update_timestamp
                mcc.update_file_metadata( {"AmSC.common.type", "artifact"}, dids=[did])
