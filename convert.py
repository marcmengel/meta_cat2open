from metacat.webapi import MetaCatClient
import metadata.sdk.entities
from metadata.generated.schema.api.data.createFile import CreateFileRequest
from metadata.generated.schema.api.data.createTable import CreateTableRequest
from metadata.generated.schema.api.data.createMlModel import CreateMlModelRequest
from metadata.generated.schema.api.data.createContainer import CreateContainerRequest
import conversion_dicts import meta2open_dict

def field_convert(entry):
    res = {}
    for k in entry:
        if k in meta2open_dict:
             res[meta2open_dict[k]] = entry[k]
    for k in entry["metadata"]:
        if k in meta2open_dict:
             res[meta2open_dict[k]] = entry["metadata"][k]
    # special conversion cases:
    if "ParentFQN" in res:
        res["ParentFQN"] = [ x["name"] for x in res["ParentFQN"] ]

def convert(cfg):
    fq = cf.get("general", "file_query")
    dq = cf.get("general", "dataset_query")
    mcu = cf.get("metacat", "url")`
    mcuser = cf.get("metacat", "user")`
    mcc = MetaCatClient(mcu)
    mcc.login_token(cf.get("general", mcuser)
    domain = ",".split(cf.get("openmeta", "add2domains"))
    
    file_list = mcc.query(fq)
    for file_info in file_list:

        file_entry = mcc.get_file(name = file_info["name"], namespace = file_info["namespace"], with_datasets=True)
        amsc_type = file_entry["metadata"]["AmSC.Type"]
        amsc_data = field_convert(file_entry)

        amsc_data["domain"] = domain

        if amsc_type == "artifact":
            created = Files.create(CreateFileRequest( *amsc_data ))
        if amsc_type == "mlmodel":
            created = mlModels.create(CreateMlModelRequest( *amsc_data ))
        if amsc_type == "table":
            created = Tables.create(CreateTableRequest( *amsc_data ))
        if amsc_type == "reference":
             pass # We dont know how to make one of these yet...
        
    dataset_list = mcc.query(dq, with_metadata=true, with_provenance=true)
    for dataset_entry in dataset_list:
        amsc_type = dataset_entry["metadata"]["AmSC.Type"]
        amsc_data = field_convert(file_entry)

        amsc_data["domain"] = domain

        if amsc_type == "scientificWork":
            created = Containers.create(CreateContainerRequest( *amsc_data ))
        if amsc_type == "artifactCollection":
            created = Containers.create(CreateContainerRequest( *amsc_data ))
    
