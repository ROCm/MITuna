# TUNA 
## Distributed tuning infrastructure


## Prerequisites
Install Python3.9
```
apt-get update && apt-get install software-properties-common
add-apt-repository ppa:deadsnakes/ppa
apt install python3.9
```

Install MySQL server
```
apt-get install mysql-server
```

Enable the service
```
systemctl start mysql
```

Install ipmitool
```
apt-get install ipmitool
```

## Installation
Clone the repo using 
```
git clone <repo url>
```
Then create a virtual env using 
```
virtualenv -p python3.9 myvenv
```
Enter the Tuna directory
```
cd Tuna
```
Activate the virtualenv and source the virtual env for subsequent use
```
virtualenv -p python3.9 myvenv
source myvenv/bin/activate
```
Install the required dependencies:
```
pip install -r requirements.txt
```
The above assumes that Tuna lives in the home directory and the virtual environment was created using the command indicated above.

load the latest backup database
```
mysql -u root -p < MySQLData.sql 
```

add os environment variables
```
export TUNA_DB_USER_NAME=root
export TUNA_DB_PASSWORD=<password for root>
export TUNA_DB_HOSTNAME=localhost
```

## To query the database for the existence of a config
Source the virtual env as above
then:
```
cd src/tuna
```

The script called QueryDb.py can query the MySQL database for either a driver command line or a performance database. A driver command line is identified by the existence of the `MIOpenDriver` binary name in the line, and a performance db line is identified by the presence of an equality sign `=`. 

For example:
```
python QueryDb.py "miopenConvolutionBackwardData: ./bin/MIOpenDriver conv -n 512 -c 192 -H 13 -W 13 -k 384 -y 3 -x 3 -p 1 -q 1 -u 1 -v 1 -l 1 -j 1 -m conv -g 1 -t 1"
```

Should query the database for the above driver command line. Note that the logging preamble is ignored by the Tuna script. Also other driver parameters which do not have an impact on the problem description are ignored, such as `verify` and `time` etc. 

The above query will result in output as follows:

```
+-------+--------+--------+-----------+---------------------+---------------------+--------+---------+------------+--------+-------+------+------+-------+-----------+--------------+----------+-------------+------------+----------+------+---------------+-------------+-------------+------+------------+---------------+-------+-----------+-------+----------+-----------+
| id    | config | arch   | state     | started             | completed           | result | reason  | machine_id | gpu_id | valid | id   | cmd  | pad_h | activMode | out_channels | filter_w | fusion_mode | dilation_w | filter_h | in_h | conv_stride_1 | group_count | in_channels | in_w | dilation_h | conv_stride_0 | pad_w | batchsize | valid | pad_mode | conv_mode |
+-------+--------+--------+-----------+---------------------+---------------------+--------+---------+------------+--------+-------+------+------+-------+-----------+--------------+----------+-------------+------------+----------+------+---------------+-------------+-------------+------+------------+---------------+-------+-----------+-------+----------+-----------+
| 23    | 2935   | gfx906 | errored   | 2018-12-11 17:10:18 | 2018-12-11 17:10:21 | None   | missing | 4          | 2      | 0     | 2935 | conv | 1     | None      | 384          | 3        | None        | 1          | 3        | 13   | 1             | 1           | 192         | 13   | 1          | 1             | 1     | 512       | 1     | default  | conv      |
| 4702  | 2935   | gfx900 | completed | 2018-12-10 04:21:18 | 2018-12-10 04:25:16 | None   | missing | 8          | 6      | 0     | 2935 | conv | 1     | None      | 384          | 3        | None        | 1          | 3        | 13   | 1             | 1           | 192         | 13   | 1          | 1             | 1     | 512       | 1     | default  | conv      |
| 23888 | 2935   | gfx900 | completed | 2019-01-11 15:51:41 | 2019-01-11 15:51:42 | None   | scan    | 8          | 5      | 0     | 2935 | conv | 1     | None      | 384          | 3        | None        | 1          | 3        | 13   | 1             | 1           | 192         | 13   | 1          | 1             | 1     | 512       | 1     | default  | conv      |
| 47528 | 2935   | gfx906 | completed | 2019-01-16 17:39:09 | 2019-01-16 17:42:49 | None   | missing | 12         | 0      | 1     | 2935 | conv | 1     | None      | 384          | 3        | None        | 1          | 3        | 13   | 1             | 1           | 192         | 13   | 1          | 1             | 1     | 512       | 1     | default  | conv      |
+-------+--------+--------+-----------+---------------------+---------------------+--------+---------+------------+--------+-------+------+------+-------+-----------+--------------+----------+-------------+------------+----------+------+---------------+-------------+-------------+------+------------+---------------+-------+-----------+-------+----------+-----------+
********************************************************************************
PDB Key: 192-13-13-3x3-384-13-13-512-1x1-1x1-1x1-0-NCHW-FP32
```

The above output indicates the presence of the config as well as if it was run for tuning and other parameters associated with a tuning job. The last section prints out a Perf-DB key for this config as well. Please note that the Perf-DB key feature is still unverified. 


## Performance Database Generation

Setup Docker

1. Checkout latest MIOpen.
2. Generate Docker image for branch.
    - May use build_docker.sh (uses Dockerfile) in Tuna/bin. 
        - Clones MIOpen repo from git, -b to specify branch.
        - Add --opencl for OpenCL build.
        - specify -v for a rocm version, or -k for bkc (overrids rocm version)
        ```
        ./build_docker.sh -d <docker_image_name> -b <miopen_branch>
        ```
3. Upload image to Docker repo, in preparation for download to nodes.
    ```
    docker login
    docker tag <docker_image_name> <docker_repo_name>
    docker push <docker_repo_name>
    ```

Setup SQL database

1. Set available field in the machine table for each machine being used to test.
    - Author recommends opening the machine table as read/write with a viewer eg MySQL Workbench, update the available column and apply with the automated query.
    - in MySQL Workbench, open the machine table with:
        ```
        select * from machine;
        ```
    - This will affect what machines are targeted by ‘go_fish.py -e’.
2. In job table set valid to 0 for unused jobs. Examples follow.
    - invalidate all jobs:
        ```
        update job set valid=0 where id!=-1;
        ```
    - invalidate jobs labeled ‘old_job’:
        ```
        update job set valid=0 where reason=’old_job’ and id!=-1;
        ```
    - invalidate jobs for gfx906 60:
        ```
        update job set valid=0 where arch=’gfx906’ and num_cu=60 and id!=-1;
        ```
3. Add jobs to the MySQL database (valid=1).
    - Use SQL queries based on existing configs.
        - This may be as simple as copying previous jobs by reason.
            ```
            insert into job(config, arch, num_cu, state, direction, valid, reason)
              select config, arch, num_cu, ‘new’, direction, 1, <new_reason> from job
              where valid = TRUE and reason=<old_reason>;
            ```
        - This could be complicated by a vague requirement set, eg.

            All configs on record satisfying the following criteria need to be tuned for gfx906 60:

            |Parameter|Constraints|
            |---|---|
            Direction | Forward
            Layout | NCHW
            Precision | FP32 only
            Dimension | 2 D
            arch | gfx906
            X | 1 
            Y | 1 
            C % 8 == 0 |
            K % 8 == 0 |
            group counts | 1
            padding | 0
            strides | 1
            dilation | 1

            Which will look like:
            ```
            insert into job(config, arch, num_cu, state, direction, valid, reason) 
              select id, ‘gfx906’, 60, ‘new’, 1, TRUE, ‘issue_####’ from config where valid  = TRUE
              and cmd=’conv’
              and in_h > 0 and in_w > 0
              and filter_w = 1
              and filter_h = 1
              and in_channels % 8 = 0
              and out_channels % 8 = 0
              and group_count = 1
              and pad_w = 0 and pad_h = 0
              and conv_stride_0 = 1 and conv_stride_1 = 1
              and dilation_w = 1 and dilation_h = 1;
            ```

    - Use the import_configs.py script in Tuna/src/tuna to import a list of driver commands from a file 
        - creates missing configs
        - tags configs and creates a set of related configs in config_tags
        - option -t is required and adds a label to the config
        - option -T will only add tags and will not create new configs
        - option -b allows batchsize override
        - option -c allos convolution command override
        - option --mark_recurrent will mark the config as recurring
        ```
        ./import_configs.py -t <tag> -f <file_name>
        ```

On the head node before running

1. ‘go_fish.py -e’ will perform the command on all valid machines.
2. Pull Docker image to the cluster.
    ```
    ./go_fish.py -e ‘sudo docker login -u <user> -p <password>’
    ./go_fish.py -e ‘sudo docker pull <docker_repo_name>’
    ```
3. Tag Docker image with a <docker_name>, Tuna by default uses miopentuna.
    ```
    ./go_fish.py -e ‘sudo docker tag <docker_repo_name> <docker_name>��
    ```
4. Results of the tuning will be placed in ~/.config/miopen by MIOpen.
    - If there are previous files in ~/.config/miopen, move them to another folder.
    - MIOpen now labels tuning results (ufdb/updb) with the commit hash of the repo. This will separate results by MIOpen commits, but there may still be some overlap like when testing the same MIOpen commit against different rocm versions.
    - The .cache directory should also be cleaned out.
    ```
    ./go_fish.py -e ‘sudo ls .config/’
    ./go_fish.py -e ‘sudo mv .config/miopen <save_dir>’
    ```
5. Log files are created in the /tmp/tuna_logs directory of the head node. 
    - logs are broken down by 
        - tuna function eg builder, evaluator
        - graphics generation: gfx###
        - machine ip
        - worker number
    - /tmp/tuna_logs/<tuna_class>/<gfx###>/<machine_ip>/<worker_num>
    - These are important for debug purposes, between runs move these folders to a save directory.

Run the performance tests
performance tests are done in 2 steps, compile and run

- Use go_fish.py with --compile to trigger compiling of new jobs.
    - Specify docker_name here to the docker that was pulled to the worker nodes, or it will default to miopentuna
    ```
    ./go_fish.py --docker_name <docker_name> --compile
    ```
    - This will take jobs in the 'new' state from the job table.
    - When completed jobs will be in the 'compiled' state.
    - The kernels compiled for these jobs will be in .cache/tuna_kcache/<job_id> on the machine on which they were run

- Use go_fish.py with --run_perf to trigger perf_db update for compiled jobs
    ```
    ./go_fish.py --docker_name <docker_name> --run_perf
    ```
    - This will take jobs in the 'compiled' state from the job table.
    - Compiled kernels will be copied from their respective compile machines and run on the selected worker machine
    - When completed jobs will be in the 'evaluated' state.
    - results will appear in .config/miopen/miopen.udb  on the worker node

Author's Recommendation
Run ./go_fish.py with options specifying architecture and number of cu and split the invocations across as many terminals.
    - option -a <arch>, gfx version eg gfx906 
    - option -n <num_cu>, number of comput units ex 60
    ```
    ./go_fish.py -a <arch> -n <num_cu> ...
    ```


## Find Database Generation

Finish performance database update before find database.
find db generation is the same process as the perf db.

Create a new Docker image using MIOpen with the updated perf db.
Branch off of the latest MIOpen develop branch and paste in the new miopen.db file generated in the perf db step. Generate a new docker using this branch.

In SQL, the job list will have to be added separately for find db. Author recommends using a SQL query to copy the perf db jobs by the unique ‘reason’ field, and creating a new reason for the find db set.
    ```
    insert into job(config, arch, num_cu, state, direction, valid, reason)
        select config, arch, num_cu, ‘new’, direction, 1, <new_reason> from job
        where valid = TRUE and reason=<old_reason>;
    ```

- Use go_fish.py with -f 1 to trigger find db update
    ```
    ./go_fish.py --docker_name <docker_name> -f 1
    ```
    - This will take jobs in the 'new' state from the job table.
    - When completed jobs will be in the 'evaluated' state.
    - results will appear in .config/miopen/<ufdb_file+commit_hash> on the worker node



## Kernel Database Generation

Finish find database update before kernel database update
Generate docker using find db generated in the previous step

- Use go_fish.py with --bin_cache to trigger binary cache update
    ```
    ./go_fish.py --docker_name <docker_name> --bin_cache
    ```
    - This will take jobs in the 'new' state from the job table.
    - When completed jobs will be in the 'evaluated' state.
    - results will appear in .cache/<ukdb_file+commit_hash> on the worker node


## Dockerized Development Environment

To build your local docker with mysql and Tuna schema prepopulated, run the following command
from the root Tuna directory

```
./dev_docker.sh
```

This will build the docker image, tag it `tuna_dev` and then `run` it with your home directory mounted as `/data` inside the docker. Leave this terminal running and use another terminal to interact with the docker.
Keep in mind data stored in this container would be destroyed if the running container is not commited. To commit the docker issue the following command

```
docker commit -m 'commit message' mysql_tuna <docker image name>
```


You can stop the docker image by issuing

```
docker stop mysql_tuna
```

To access the docker using a shell issue the following command

```
docker exec -it mysql_tuna bash
```

Once inside the docker image you can use the mysql to inspect the database. The default password for the `root` user is hardcoded in the Dockerfile. To expose the mysql server directly to the host and external machine run the docker with `--network host`. This would enable remote access to the database.

The docker image is based on the official mysql image and further details about it may be found [here](https://hub.docker.com/_/mysql/?tab=description)

### Schema Dump

The script above uses `schema.sql` in the bin directory to create the database schema for the newly minted database. This file can be generated again by issuing the following command on the database machine:

```
mysqldump  -uroot -p <database_name> --no-data > schema.sql
```

Where `<database_name>` is the name of the database whose schema should be dumped. For our machine the command would be as follows:

```
mysqldump  -uroot -p <db_name> --no-data > schema.sql
```

It may be noted that everytime there is a change in the schema the file `schema.sql` would need to be changed.


### Note

- Most executable scripts in src/tuna/ have detailed help descriptions about their run options, just run with -h.

