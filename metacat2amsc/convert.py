from metacat.webapi import MetaCatClient
from conversion_dicts import meta2amsc_dict
from version import __version
import os
import json
import requests
import urllib
import logging
logger = logging.getLogger(__name__)

class fqncache:
    def __init__(self, mcc):
        self.fqnmap = {}
        self.mcc = mcc

    def register_fqn(self, name, namespace, fqn):
        did = f"{namespace}:{name}"
        self.fqnmap[did] = fqn

    def lookup_fqn(self, name, namespace):
        did = f"{namespace}:{name}"
        if not(did in self.fqnmap):
            md = self.mcc.get_dataset(did)
            if md and "AmSC.common.fqn" in md["metadata"]:
                self.fqnmap[did] = md["metadata"]["AmSC.common.fqn"]
        if not  self.fqnmap.get(did, ""):
            logger.warning(f"Error: Unable to find fqn for: {did}")
        return self.fqnmap.get(did, "")

class AmSCClient:
    def __init__(self, cf, fqncache):
        self.amsc_url = cf.get("general","amsc_url") 
        self.catalog_name = cf.get("general","catalog_name") 
        self.sess = requests.Session()
        self.sess.headers.update( {"Authorization": cf.get("openmetadata","jwt_token")})
        self.fqncache = fqncache

    def query(self, querystring, limit=0, offset=0):
        url = f"{self.amsc_url}/search/catalog?q={urllib.quote_plust(querystring)}"
        if limit:
            url += f"&{limit=}"
        if offset:
            url += f"&{offset=}"
        resp = self.sess.get(url)
        return resp.json()

    def post_create(self, entity_dict):
        url = f"{self.amsc_url}/catalog/{self.catalog_name}/{entity_dict['type']}"
        print(f"posting {json.dumps(entity_dict, indent=4)} to {url}")
        resp = self.sess.post(url , json=entity_dict)
        if resp.status_code != 200: 
         
             if resp.text.find("already exists") > 0:
                 logger.info(f"Exists already: {entity_dict['name']}") 
             else:        
                 raise RuntimeError(f"got status {resp.status_code} for POST catalog entry: {resp.text}")
        return resp.json()

    def put_update(self, entity_dict):
        url = f"{self.amsc_url}/catalog/{entity_dict['fqn']}"
        print(f"posting {json.dumps(entity_dict, indent=4)} to {url}")
        resp = self.sess.put(url, json=entity_dict)
        if resp.status_code != 200:
             raise RuntimeError(f"got status {resp.status_code} for PUT catalog entry: {resp.text}")
        return resp.json()


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

    if "location" not in res:
        res["location"] = "http://www.fnal.gov/"

    res["extra"] = extra
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

    mcc = MetaCatClient(server_url=mcsu, auth_server_url=mcasu)
    fc = fqncache(mcc)
    amscc = AmSCClient(cf, fc)

    #mcc.login_token(cf.get("general", mcuser))

    queries_list = cf.get("general", "query_list", fallback="general").split(" ")
    print(f"{queries_list=}")
    for qsect in queries_list:

        fq = cf.get(qsect, "file_query")
        dq = cf.get(qsect, "dataset_query")

        print(f"querying: {dq}")
        dataset_list = list(mcc.query(dq, with_metadata=True, with_provenance=True))

        for d_entry in dataset_list:
            print("{d_entry=}")
            amsc_data = field_convert(d_entry, fc)

            if not amsc_data.get("fqn",None):
                # not previously migrated
                if "fqn" in amsc_data:
                    del amsc_data["fqn"]
                if "updated_by" in amsc_data:
                    del amsc_data["updated_by"]
                res_data = amscc.post_create(amsc_data)

                # remember fqn, and update in metacat
                fc.register_fqn(d_entry['namespace'], d_entry['name'], res_data.get("fqn",None))

                mcc.update_dataset(
                    dataset=f'{d_entry["namespace"]}:{d_entry["name"]}',
                    metadata={"AmSC.common.fqn":res_data.get("fqn", "")},
                )
            else:
                # previously migrated: update
                res_data = amscc.put_update(amsc_data)

                # remember fqn
                fc.register_fqn(d_entry['namespace'], d_entry['name'], res_data.get("fqn",None))
            

        file_list = mcc.query(fq)
        for file_info in file_list:

            file_entry = mcc.get_file(name = file_info["name"], namespace = file_info["namespace"], with_datasets=True)
            amsc_data = field_convert(file_entry, fc)

            print("{file_info=}")

            if not amsc_data.get("fqn",None):
                # not previously migrated
                print(f"I would post {json.dumps(amsc_data,indent=4)}")
                if "fqn" in amsc_data:
                    del amsc_data["fqn"]
                if "updated_by" in amsc_data:
                    del amsc_data["updated_by"]
                res_data = amscc.post_create(amsc_data)
                mcc.update_file( 
                    namespace=file_info["namespace"],
                    name=file_info["name"],
                    metadata={"AmSC.common.fqn": res_data["fqn"]}
                )
            else:
                # previously migrated
                res_data = amscc.put_update(amsc_data)

