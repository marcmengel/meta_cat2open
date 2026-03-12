from metacat.webapi import MetaCatClient
import conversion_dicts import meta2open_dict
import requests


def field_convert(entry):
    res = {}
    extra = {}
    for k in entry:
        if k in meta2open_dict:
             res[meta2open_dict[k]] = entry[k]
        else:
             extra[k] = entry[k]
    for k in entry["metadata"]:
        if k in meta2open_dict:
             res[meta2open_dict[k]] = entry["metadata"][k]
        else:
             extra[k] = entry[k]
    # special conversion cases:
    if "ParentFQN" in res:
        res["ParentFQN"] = [ x["name"] for x in res["ParentFQN"] ]
    res["extra"] = extra

def post_create(s, cf, type, entity_dict)
    amsc_url = cf.get("general","amsc_url") 
    resp = s.post(f"{amsc_url}/catalog/{entity_dict['type']}", entity_dict)
    return r.json()

def put_update(s, cf, type, entity_dict)
    amsc_url = cf.get("general","amsc_url") 
    resp = s.put(f"{amsc_url}/catalog/{entity_dict['fqn']}", entity_dict)
    return r.json()

def convert(cfg):
    fq = cf.get("general", "file_query")
    dq = cf.get("general", "dataset_query")
    mcsu = cf.get("metacat", "server_url")`
    mcasu = cf.get("metacat", "auth_server_url")`
    mcuser = cf.get("metacat", "user")`

    # in development, we need an ssh tunnel to get to the AMSC API..."
    tunnel = cf.get("general", "tunnel_command")
    if tunnel:
        os.system(tunnel)

    mcc = MetaCatClient(server_url=mcsu, auth_server_url=mcasu)
    omc = requests.Session()
    omc.headers.update( {"Authorization": cf.get("openmetadata","jwt_token")})

    mcc.login_token(cf.get("general", mcuser)
    
    dataset_list = mcc.query(dq, with_metadata=true, with_provenance=true)
    for d_entry in dataset_list:
        amsc_data = field_convert(d_entry)

        amsc_data["domain"] = domain

        if not amsc_data["fqn"]:
            # not previously migrated
            res_data = post_create(s, cf, amsc_data)
            mcc.update_dataset(
                namespace=d_entry["namespace"],
                name=d_entry["name"],
                metadata={"AmSC.common.fqn",res_data["fqn"]}
            )
        else:
            # previously migrated: update
            res_data = put_update(s, cf, amsc_data)
        

    file_list = mcc.query(fq)
    for file_info in file_list:

        file_entry = mcc.get_file(name = file_info["name"], namespace = file_info["namespace"], with_datasets=True)
        amsc_data = field_convert(file_entry)

        amsc_data["domain"] = domain

        if not amsc_data["fqn"]:
            # not previously migrated
            res_data = post_create(s, cf, amsc_data)
            mcc.update_file(
                namespace=d_entry["namespace"],
                name=d_entry["name"],
                metadata={"AmSC.common.fqn",res_data["fqn"]}
            )
        else:
            # previously migrated
            res_data = put_update(s, cf, amsc_data)

