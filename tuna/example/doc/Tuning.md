Tuning through the Example library
==================================
An example of how to integrate external applications in MITuna.


*Example* is mock library that runs the *rocminfo* binary.
The supported tuning steps are:

.. code-block::  

  ./go_fish.py example --add_tables  
  ./go_fish.py example --init_session -l my_label  
  ./example/load_job.py -a gfx908 -n 120 -l my_label --session_id 1  
  ./go_fish.py example --execute --session_id 1  

Creating the database tables:

.. code-block::  

  ./go_fish.py example --add_tables  

This command will create the following new tables in the DB:
* machine
* session_example
* job

Adding a new session:

.. code-block::  

  ./go_fish.py example --init_session -l my_label  

This command will add a new session in the *session_example* table. This session id will be
used to add new jobs and track the tuning data, post execution step.

Setting up jobs for tuning:

.. code-block::  

  ./tuna/example/load_job.py -a gfx908 -n 120 -l my_label --session_id 1

This steps loads jobs in the *job* table. These jobs will be picked up for execution in the
next step. Once these jobs are completed their status will be updated to 'completed' or 'errored'.

The first tuning step:

.. code-block::  

  ./go_fish.py example --session_id 1 --enqueue_only

This command will pick up jobs in the *new* state from the job tables associated with the
session_id 1. The job status will be updated to running and jobs will be placed in a celery
queue. This step needs to be executed on the headnode (or any node with access to the rabbitMQ
broker, celery backend result and mySQL DB.) This main process will write results from the redis DB
into the final mySQL DB.


The last tuning step:

.. code-block::  

  ./go_fish.py example --session_id 1

This last step launches a celery worker. The worker will pick up jobs from the queue and execute.
This step needs to be launched on the machine where the job is to be executed.

To execute a single command, in this case `rocminfo`:

.. code-block::  

  ./go_fish.py example --session_id 1 --execute

For the purpose of this example, the command `rocminfo` is hardcoded. this step is not considered
a tuning step. This is a standalone step that launches a particular command.


To integrate a new library, similar source code would have to be provided, as the one included
in */tuna/example*. The full MIOpen library source code for tuning MIOpen is included in
=======
The last step:

.. code-block::  

  ./go_fish.py example --execute --session_id 1

This command will pick up jobs in the *new* state from the job tables associated with the
session_id 1. The job status will be updated as the jobs are executing, from new to running and
completed or errored.

To integrate a new library, similar source code would have to be provided, as the one included
in */tuna/example*. The full MIOpen library source code for tuning is included in
