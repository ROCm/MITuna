New library integration 
=======================
An example of how to integrate external applications in Tuna to utilize the scaling
features of Tuna


Example library
---------------
*Example* is mock library that runs the *rocminfo* binary.
The supported tuning steps are:
```
./go_fish.py example --add_tables
./go_fish.py example --init_session -l my_label
./tuna/example/load_job.py -a gfx908 -n 120 -l my_lable --session_id 1
./go_fish.py example --execute --session_id 1
```

The first step is:
```
./go_fish.py example --add_tables
```
This command will create the following new tables in the DB:
- machine
- session_example
- job

The next command is:
```
./go_fish.py example --init_session -l my_label
```
This command will add a new session in the *session_example* table. This session id will be
used to add new jobs and track the tuning data, post execution step.

The third step is:
```
./tuna/example/load_job.py -a gfx908 -n 120 -l my_lable --session_id 1

```
This steps loads jobs in the *job* table. These jobs will be picked up for execution in the
next step. Once these jobs are completed their status will be updated to 'completed' or 'errored'.

The last step:
```
./go_fish.py example --execute --session_id 1

```
This command will pick up jobs in the *new* state from the job tables associated with the
session_id 1. The job status will be updated as the jobs are executing, from new to running and
completed or errored.

To integrate a new library, similar source code would have to be provided, as the one included
in */tuna/example*. The full MIOpen library source code for tuning is included in
*/tuna/miopen*.
