What is Tuna
============

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

When do we tune
---------------

There are two occasions that trigger tuning:
1. Someone opens a Github issue that contains the configurations and network to be tuned.
This implies we only need to tune the network specified in the issue along with the
configurations specified. If the person requesting this did not mention any configurations,
please ask for them. The Tuna team does not provide these.
2. Recurrent configurations need retuning when internals of MIOpen/Tuna change. The tuning
phase of all the recurrent configurations takes up to a few days. There are many configurations
used for each network and one should try and use as many machines as possible to speed up
the tuning part.

Tuning Steps
------------

Tuning stores intermittent data in a central mySQL database. Each reference to a table,
refers to a table in this database. Each table and its associated schema is found in miopen_tables.py.

Tuning is divided in multiple steps and each step builds on top of the previous ones.
To start a tuning session, some prerequisite have to be asserted: setting up configurations,
getting the latest solvers and their associated applicability from MIOpen,
and adding the jobs that compose the tuning session.
Once these prerequisite are established the tuning session can begin. Each step,
including the prerequisites are detailed below.

**Add Network Configurations(1)**

Before a configuration gets tagged, a model and framework need to be added. This allows for
benchmarking of a certain model, post tuning.

```
./go_fish.py --add_model Resnet50 --md_version 1
./go_fish.py --add_framework Pytorch --fw_version 1
--add_model - model name
--md_version - model version
--add_framework - framework name
--fw_version - framework version
```

The config table contains network configurations. If provided with a text file of MIOpenDriver
commands, the import script can translate those commands and populate the config table.
Additionally the user may provide a name to tag a configuration for easier recall later.
A tag will be required when adding a tuning job. Tags are stored in the config_tags table.
A model and framework name and version are also required. This enables MITuna to track
benchmark performance post-tuning.

```
./go_fish.py miopen import_configs --add_model Resnet50 --md_version 1
./go_fish.py miopen import_configs --add_framework Pytorch --fw_version 1
./go_fish.py miopen import_configs -t resnet50 -f ../utils/recurrent_cfgs/resnet50.txt
--model Resnet50 --md_version 1 --framework Pytorch --fw_version 1</p>
-t - tag
-f - filepath
--model - model name
--md_version - model version
--framework - framework name
--fw_version - framework version
-
```

**Add Solvers (2)**

The solver table contains MIOpen solvers and solver characteristics.
This should be updated when an MIOpen version modifies solvers.

```
./go_fish.py miopen --update_solvers
```

**Add Tuning Session (3)**

Session will track the architecture and skew, as well as the miopen version and
rocm version for the tuning session.

This command will need to be run from inside the tuning environment eg MITuna docker
and will populate the table with the version and architecture information.

[Use backend=HIPNOGPU docker]
```
./go_fish.py miopen --init_session -l reason
--init_session - create a session entry
-l             - reference text description
```

**Add Applicability (4)**
Each network configuration has a set of applicable solvers. This step will update the
solver_applicability table with applicable solvers for each configuration for the session.

[Use backend=HIPNOGPU docker]
```
./go_fish.py miopen --update_applicability --session_id 1
--session_id - tuning session id
```

**Load Jobs (5)**

Time to create the jobs for the tuning session. Specify the session id, the configs that
should be tuned, and the fin_step to be executed. Configs can be added by using the tag from
the config_tags table. Jobs should have a compile and an eval fin step pair.

Fin steps include: miopen_perf_compile, miopen_perf_eval, miopen_find_compile, and miopen_find_eval.

```
./load_job.py --session_id 1 -t resnet50 --fin_steps miopen_perf_compile,miopen_perf_eval -o -l reason
--session_id - tuning session id
-t           - config tag
--fin_steps  - operations to be performed by fin (tuning handle into miopen)
-o           - only_applicable, will create a job for each applicable solver
-l           - reference text description
```

**Compile Step (6)**

Once prerequisites are set, tuning can begin. To compile the jobs,
supply the session id along with the compile fin_step matching the one in the job table.

[Use backend=HIPNOGPU docker]
```
./go_fish.py miopen --session_id 1 --fin_steps miopen_perf_compile
--session_id    - tuning session id
--fin_steps     - execute this operation
```

**Evaluation Step (7)**

Once compilation has been started, evaluation can also be launched.
This command is similar to the previous.

[Use backend=HIP docker]
```
./go_fish.py miopen --session_id 1 --fin_steps miopen_perf_eval
--session_id    - tuning session id
--fin_steps     - execute this operation
```

**Database Export (8)**

To export the results the export_db.py script can be run with options
for selecting session as well as database type.

The outputs of this function are database files in the format that MIOpen keeps and manages.
eg for MI100, -p will produce a gfx90878.db file, -f will produce gfx90878.HIP.fdb.txt, and -k will produce gfx90878.kdb.

```
./export_db.py --session_id 1 -p
--session_id - tuning session id
-p           - export performance db
-f           - export find db
-k           - export kernel db
```
