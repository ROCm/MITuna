MIOpen Golden Database
======================

Tuna's MySQL database tracks versioned data for MIOpen.
These versions are kept in the golden table. A golden miopen version holds
the complete tuning history at each step. 

Adding to the Golden Table
--------------------------

Once a tuning session is approved, the results in the generated find db
may be used to populate the golden table.

> ```  
> ./update_golden.py --session_id \<id\> --golden_v \<new_ver\> --base_golden_v \<old_ver\>  
> --golden_v      - create this golden version  
> --base_golden_v - initialize the new golden version with this previous golden data  
> --session_id    - id of the tuning session to populate the golden version  
> --overwrite     - may be used to force writing to existing golden_v  
> ```  

If there are no previous golden version `--base_golden_v` need not be specified.
Otherwise writing a new golden version will require `--base_golden_v`.

