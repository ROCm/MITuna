# What is Tuna
As a high-performance kernels library, MIOpen needs a substantive tuning effort to discover the
optimal tuning parameters. Kernel tuning entails compiling and running MIOpen kernels with different
tuning parameters to determine the best performing tuning parameters for each kernel. While MIOpen
contains much of the logic needed to iterate over possible tuning parameters, it is only applicable
to a single machine. Therefore, a mechanism is required to parallelize this process across different
machines as well as across multiple GPUs to speed up this inherently parallel procedure. Among other
features, such a framework, it needs to be able to handle errors in both MIOpen and the stack on which
MIOpen depends.

Tuna is MIOpens team library, which parallelizes the tuning procedure across multiple GPUs on
multiple machines. In addition to distributing jobs to servers, it is aware of the various
architectures, whether a tuning effort was successful, or resulted in an error and other housekeeping.
This makes it a useful automation tool. Tuna is also the custodian of the convolution layer parameters
of interest (to the MIOpen team), received from customers, as well as various benchmarks. With the
introduction of 'find database' for immediate mode, Tuna is also responsible for generating Find
database as well as the upcoming precompiled kernels package.

## When do we tune
There are two occasions that trigger tuning:
1. Someone opens a Github issue that contains the configurations and network to be tuned.
This implies we only need to tune the network specified in the issue along with the
configurations specified. If the person requesting this did not mention any configurations,
please ask for them. The Tuna team does not provide these.
2. Recurrent configurations need retuning when internals of MIOpen/Tuna change. The tuning
phase of all the recurrent configurations takes up to a few days. There are many configurations
used for each network and one should try and use as many machines as possible to speed up
the tuning part. The current configurations we tune for are:

|architecture   | num_cu     |
|---------------|------------|
|gfx900         |56          |
|gfx900         |60          |
|gfx906         |60          |
|gfx906         |64          |
|gfx908         |120         |

For some older architecture we do not retune anymore, but we overwrite the associated .fdb.txt
files like so:

|architecture num_cu| overwritten     |
|-------------------|-----------------|
|gfx803 56          |gfx900 64        |
|gfx803 56          |gfx900 64        |

# Tuna breakdown
The purpose of this documentation is to describe in detailed steps a full tuning cycle.
This cycle consist of 2 major steps:
    ..*  Compiling and running binaries (longest step up to a few days)
    ..* Comparing results with the existing DB and updating the DB (could take just 1 day).

Tuna makes use of the following components:
    * reachable GPUs for different architectures
    * docker to launch jobs on the GPUs
    * python - scripts that create && launch the jobs and then gather results.
    * MySQL database

Tuna produces 2 databases:
1. perf_db (miopen.db)
2. find_db (<name>.fdb)

1. During the tuning process, perf_db resides in 2 distinct locations:
a. system db - location: /opt/rocm/miopen/share/miopen/db
b. user db - location: ~/.config/miopen
When MIOpen is installed, the packaged copied of these are placed in '/opt/rocm/miopen/share/
miopen/db/' and are referred to as the system db. When the user runs MIOpen and some new entries
are created for either of these, they are placed in ~/.config/miopen and referred to as the
user db.
Additionally, Tuna has a MySQL database for managing the machines/configs/jobs.

2. The main script is go_fish.py
go_fish.py is used to launch jobs(which will write results into local Databases on the machine on which
these jobs are running). This script is used to compile jobs as well as use the compiled binary to
run the benchmarking.
DB local to the server where these jobs are being launched from.

# Tuning steps fpadmin@zigzag
1. Source environment variables
2. Set up machines
3. Set up jobs for tuning in the DB
4. Create docker image for tuning
5. Generating the cluster perf_dbs. Run tuning jobs (go_fish.py)
6. Generating the find_db. Create docker img (HIP/OCL)
7. Generate the find_db. 

Bellow are the detailed instructions for each step.

1. Source environment variables:
All the TUNA_DB_* env variables need to be sourced. On zigzag you can run the following commands:
```
source ~/db.env
source <tuna_dir>/myenv/bin/activate
```

2. Set up machines (as available) for tuning. We have a local DB on zigzag where we keep track of
available machines and jobs to run. Follow steps bellow to make machines available for tuning.

```
mysql -u root -p; 
mysql> USE perf_cgfs;
mysql> SELECT * FROM machine;
```
Look for machine with 'host ip' and 'port' from MIOpen Servers spreadsheet (get link from any
Tuna members) that correspond to desired architecture and num_cu. We tune for specific
arch/num_cu combinations. (ask team lead/members which ones are current).
```
mysql> UPDATE machine SET available=1 WHERE id=X;
```
X corresponds to the id in the DB for the machine with the 'host ip' and 'port' from MIOpen Servers
Google doc spreadsheet. This is important because a tuning job will run on any available machine
with a matching arch/num_cu.
Note: You can also the MySQL Workbench GUI to run SQL commands.

3. Set up the tuning jobs by using the import_configs.py and load_job.py script. We have a 
comprehensive file to pass to the script, located at /home/fpadmin/recurrant_perfdb/all.txt.
This file contains all the MIOpen driver commands (This is an attempt at containing the most
frequently used configurations, but do not rely on it being up to date at all times).
The resulting MIOpenDriver commands contain arguments that specify neural network parameters,
such as input, height, weight, width, filter size, filter step etc. From here, MIOpen tries to
determine which aglorithm is best to use.

In tuna/src - run the import_configs.py script for each combination of arch/num_cu that you are
currently interested in testing.
The import_configs.py script is used to tag a config with a specific tag (in the config_tags table)
in the DB and later use that tag to set up jobs through the load_job.py script.
The load_job.py script can create multiple entries (in the jobs table) for various directions,
solvers etc. Run the scrip with -h to see list of arguments.

Here are some examples of a workflow.
If you are setting jobs for specific lables (JIRAs etc) use the following command to tag those
configs, so you can later use the tag to set up jobs.
```
./import_configs.py -f ~/recurrant_perfdb/all.txt -t myTag
./import_configs.py -f ~/recurrant_perfdb/all.txt -t myTag
./import_configs.py -f ~/recurrant_perfdb/all.txt -t myTag
```
Note: If you want to use a different batchsize than what is in all.txt, you can use the -b arg like:
```
./import_configs.py -f ~/recurrant_perfdb/all.txt -t myTag -b 32,64,128
```
To set up jobs that were tagged in the command above, run the following:
```
./load_job.py -a 'gfx900' -n 64  -l myLabel -t myTag
./load_job.py -a 'gfx906' -n 60  -l myLabel -t myTag
./load_job.py -a 'gfx906' -n 64  -l myLabel -t myTag
```
Notice in the commands above we have set up jobs for 3 different architectures: 900/64, 906/60 and
906/64 (each config in all 3 directions). Use the -h command to see more options.

If you are setting jobs for all the configs in the DB (convolutions only) use the following SQL
statement and circumvent Tuna scripts:
```
mysql> INSERT INTO job(config, arch, num_cu, state, direction, valid, reason) SELECT config.id,
   'gfx900', 56, 'new', 4, 1, 'my_custom_lable' FROM config where valid=1 and cmd like "conv%";
mysql> INSERT INTO job(config, arch, num_cu, state, direction, valid, reason) SELECT config.id,
   'gfx900', 56, 'new', 2, 1, 'my_custom_label' FROM config where valid=1 and cmd like "conv%";
mysql> INSERT INTO job(config, arch, num_cu, state, direction, valid, reason) SELECT config.id,
   'gfx900', 56, 'new', 1, 1, 'my_custom_label' FROM config where valid=1 and cmd like "conv%";
```
Notice the above command does not use any scripts, but instead makes use of mySQL commands. We
insert 1 job per direction. Repeat the above commands for each architecture.

If you are setting up find_db jobs (for a subset of configs for example - a subset you ran perf_db)
for, then you can use the following to set up find_db jobs for that subset.
```
mysql> INSERT INTO job(config, arch, num_cu, state, direction, solver, valid, reason)
       SELECT config, arch, num_cu, "new", direction, solver, 1, "my_label_fdb"
       FROM job WHERE reason="my_label_perf_db" AND valid=1;
```

Please make the label descriptive, include the date if possible and other details if needed.
Once you execute these commands check the DB and run:
```
mysql> SELECT state, count(*) FROM job WHERE reason='mylabel' GROUP BY state;
```
This will show you all the jobs the command created! At this point they should all have state='new'.
Once these jobs will start running, you will be able to see which machine/num_cu they were
assigned to, and their state will be updated to state=running/started/completed/error/aborted.

4. Create docker image with latest MIOpen develop branch (you will need a Docker Hub account and
access to the private rocm/miopen-private repo - ask team lead for permissions). You will need to find
the correct version to use with -v. Also use the -n flag to disable local cache and make sure you have
a fresh build every time.
```
./build_docker.sh -d my_docker_img -b develop -v x.x.x -n 
```
This will create a new docker img called 'my_docker_img' for the develop branch in the private MIOpen repo 
```
docker login
docker tag my_docker_img rocm/miopen-private:my_docker_img
docker push rocm/miopen-private:my_docker_img
```

Login to docker from all the machines using the go_fish.py script and pull the docker img onto each
available machine, then tag it as miopentuna:latest :
```
./go_fish.py -e "sudo docker login -u username -p password"
./go_fish.py -e 'sudo docker pull rocm/miopen-private:my_docker_img'
./go_fish.py -e 'sudo docker tag rocm/miopen-private:my_docker_img miopentuna:latest'
```
go_fish.py will pull a copy of this docker img to each machine available, but multiple instances
might be launched on the machine. Keep in mind that the MIOpenDriver command runs in a docker env
on each GPU.
This command tags your docker img as the miopentuna:latest which will later be run in the tuning job.

5. Generating the perf_db(miopen.db). The perf_db generation is done in 2 steps:
a. Run compile jobs. This will generate local binaries(udb files) on the machines used for tuning.
In step b, these binaries will be transfered to a machine that launches benchmarking jobs and used
in generating the perf_db
b. Run benchmarking jobs

These task will have to be launched in separate, persistent windows. We recommend you run each
arch/num_cu in its on peristent window. This will later allow you to stop/restart jobs per arch/num_cu
rather than stopping them all. First launch step a:
```
./go_fish.py -a gfx900 -n 56 --compile -l myLabel
```
In a new window launch step b:
```
./go_fish.py -a gfx900 -n 56 --run_perf -l myLabel
```

Step a is the compile step. This step can be executed on any machine. The compiled kernel binaries 
will be for the architecture specified by the job. Resulting binaries will be stored in 
.cache/tuna_kcache/<job id>.

Step b is the run step. This will consume the binaries produced by step a. Files will be copied
over as necessary from the compile machine.

In either step -a <arch> and -n <num_cu> specifies the machines the commands will issue to.
Additionally docker can be specified with --docker_name <the image name>. You must specify a label
to ensure you are only executing the jobs you have set up.

This will run the tuning! Go grab some coffee, take a walk...
As the tunning progresses, you will see the compile jobs completed under the state `compiled`. When
jobs are in this state, they will be picked up by benchmarking jobs which will terminate with the
state `evaluated`. The count of the `new` jobs will be going down and there might be some
`error_xxx`, some `error_status`, some `aborted`. Keep an eye on the `retries` column for the job, if
you see a machine that keeps retrying some high# - you might want to investigate.


6. Generating find_db.
Use your newly created branch from step #6 the create the docker for find_db.
```
~./Tuna/bin/build_docker.sh -d my_docker_img -b `mybranch` -v 4.x -n
```
Note: -v specified the rocm version to be used.

Repeat the steps at #4 to tag the docker, push to docker hub, pull on the nodes and tag it as
miopentuna:latest
```
docker login
docker tag my_docker_img rocm/miopen-private:my_docker_img
./go_fish.py -e "sudo docker login -u username -p password"
docker push rocm/miopen-private:my_docker_img
./go_fish.py -e 'sudo docker pull rocm/miopen-private:my_docker_img'
./go_fish.py -e 'sudo docker tag rocm/miopen-private:my_docker_img miopentuna:latest'
```
Remove the .cache and .config directories as described in step #6.

8. Set up jobs for find_db for all existing configs in the DB. The find step will have to run for
all configs for every architecture. Use the following command to set up these jobs:
```
mysql> insert into job(config, arch, num_cu, state, direction, valid, reason) select config.id,
       'gfx908', 120, 'new', 0, 1, 'my_label' from config where valid=1;
```
Repeat this step for every desired architecture.

9. Once the jobs are set up for find_db Run go_fish.py with `-f 1 --find_mode 1` to generate the
find_db. Before you do this, remember to clear .config directories as described in #6.
For up to date results, ensure miopen.db has the latest tuning.

USe the following command to run find. This will leave a user find_db in the form of a text file
in ~/.cache/version/ (example ~/.cache/2.10.0.8281-a28ff8dd) on the target machine.
```
./go_fish.py -f 1 --find_mode 1
```
--docker_name is also available here to select an image.

The tuning steps are now done and we need to update MIOpen with the results.

# Update MIOpen databases
Once steps 1-8 are complete, you are now ready to update the MIOpen databases.
Follow these steps:

1. Checkout your MIOpen branch with the new miopen.db file from step #6.
2. Replace all .fdb.txt files from <MIOpen_location>/src/kernels  with your local .fdb.txt files
4. Open a PR

# Generate binary cache files
Binary cache files are pre-compiled kernels we ship which users of MIOpen will pick up and use.
This will save them time, as they will not have to recompile themselves.

To generate the binary cache files, `*.kdb` file you must set up jobs for all convolution configs
in the Tuna DB. Instructions can be found in step #3 above.

Once the jobs are set up, go_fish.py will run with the --bin_cache flag and find_mode 3:
```
./go_fish.py -l myLabel_kdb -a gfx900 -n 56 --bin_cache --find_mode 3
```
This command will place `*.kdb` file on all remote machines involved in tuning in the following
location: /home/fpadmin/.cache/2.x.x-xyz123/gfx900_56.kdb.

This command will run as an evaluator and when all jobs will finish in the DB, all jobs will have
the state updated to "evaluated".

Once all the kdb files have been generated they need to be placed at this location on zigzag
```
/var/www/zigzag/rocm/miopen-kernel/rel-<release_version>
```

# Debug knowledge
---------------------------------------------------------------------------------------------------
Each job dumps text to:
~/tmp/tuna_logs/builder/(mid)mid_(host_ip)_(port)p/(proc_id).log
~/tmp/tuna_logs/evaluator/(mid)mid_(host_ip)_(port)p/(proc_id).log

These files contain output dump from each job arch/num_cu combination for the host/ip/GPU it ran on.
The log level is determined by MIOPEN_LOG_LEVEL set in go_fish.py. These log files contain dumps
from Tuna and MIOpen.

You can check job progressions in the Tuna DB. You can also check if jobs fail and then find the
failure reason in the log file. Sample workflow:
```
mysql> select count(*), arch, num_cu, state from job where reason="myLabel" group by arch, num_cu,
       state;
mysql> select count(*), arch, num_cu, state from job where reason="myLabel" group by arch, num_cu,
       state where state="error_status";
mysql> select count(*), arch, num_cu, state, machine_id, eval_mid, gpu_id from job where reason="myLabel" group by arch, num_cu,
       state, machine_id, gpu_id, eval_mid where state="error_status";
```
Depending on whether the job you are investgating is a builder (compile job) or an evaluator(run_perf)
job, you are interested in the machine_id for builder and eval_mid for evaluators. You can use this
id to find the correct log file to investigate.
Say we are looking at an evaluator job fail, so we are interested in the eval_mid=5. We look into
/tmp/tuna_logs/evaluator/gfx900/60cu_<machine_ip>/eval_mid.log

In this file, search for the job_id that failed and you can see where the job_id was set to
"error_status" and the reason for this state will be in the lines just above that.

# Aborting jobs in progress 
---------------------------------------------------------------------------------------------------
To temporarily abort jobs in progress and the restart you can:
```
touch /tmp/miopen_abort_gfx900 or
touch /tmp/miopen_abort_mid_12 --> find the machine id in the machine table

mysql> select id from machine where available=1 and arch="gfx900" and num_cu=56;
```
We prefer aborting jobs by mid rather than entire arch/num_cu in case someone else has Tuna jobs
running on the system. If you abort by arch/num_cu you will terminate everyones jobs that are
running on the system for that architecture. Please avoid doing so and use mid.

To restart these jobs simple remove the abort files created and run the Tuna go_fish.py command.
If you want to reset some of the jobs that failed in error before you restart the script, you can:

```
mysql> update job set state="new" where state="error_status" and arch="gfx900" and num_cu=56
       and reason="myLabel";
```
Keep in mind that if you are resetting evaluator jobs you want to reset the state to "compiled"
and not "new", example:
```
mysql> update job set state="compiled" where state="error_status" and arch="gfx900" and num_cu=56
       and reason="myLabel";
```
