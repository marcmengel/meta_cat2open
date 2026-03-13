
## meta_cat2open

This is a gateway script betweeen the MetaCat and AmSC metadata catalogs
for sharing data between production MetaCat setups at Fermilab and the 
American Science Cloud OpenMetadata catalog. 

You can configure metadata queries to migrate metadata between the systems.

Currently only metacat->AmSC is implemented at all.  But we should be able to do a 
similar reverse mapping; we would have to put a field in the "extra" metadata to 
reflect what was migrated on the AmSC / OpenMetadata side.
