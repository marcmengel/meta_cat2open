

amsctype2mctype_dict = {
   "scientificWork": "dataset",
   "artifactCollection": "dataset"
   "artifact": "file",
   "mlmodel": "file",
   "table": "file",
   "reference": "file",
}

amsctype2omtype_dict = {
   "scientificWork": "Collection",
   "artifactCollection": "Collection"
   "artifact": "File",
   "mlmodel": "mlModel",
   "table": "Table",
   "reference": "file",
}

meta2open_dict = {
 "id": "fqn",
 "name": "name",
 "owner": "owner",
 "size": "size",
 "datasets": "parentFQN",
 "updated_by": "updatedBy",
 "updated_timestamp": "updatedAt",
 "AmSC.common.description": "description",
 "AmSC.common.displayName": "displayName",
 "AmSC.common.domains": "domains",
 "AmSC.common.fqn": "fqn",
 "AmSC.common.location": "location", 
 "AmSC.common.type": "type",
 "AmSC.common.license": "license",
 "AmSC.common.originalSource": "originalSource",
 "AmSC.common.persistentIdentifier": "persistentIdentifier",
 "AmSC.common.tags": "tags",
 "AmSC.common.version": "version",
 "AmSC.artifact.format": "format",
 "AmSC.mlModel.serviceType": "serviceType",
 "AmSC.mlModel.algorithm": "algorithm",
 "AmSC.mlModel.hyperparameters": "hyperParameters",
 "AmSC.mlModel.storageLocation": "storageLocation",
 "AmSC.mlModel.features": "features",
 "AmSC.mlModel.targetVariable": "targetVariable",
 "AmSC.mlModel.serverEndpoint": "serverEndpoint",
 "AmSC.mlModel.dashboard": "dashboard",
 "AmSC.mlModel.modelVersion": "modelVersion",
 "AmSC.mlModel.extension": "extension",
 "AmSC.table.columns": "columns",
 "AmSC.table.tableType": "tableType",
 "AmSC.table.serviceType": "serviceType",
 "AmSC.reference.referenceType": "referenceType",
 "AmSC.reference.relationshipType": "relationshipType",
 "AmSC.reference.sourceEntity": "sourceEntity",
 "AmSC.reference.targetURI", "targetURI",
}

open2meta_dict = { v: k for k,v in meta2open_dict.items() }
