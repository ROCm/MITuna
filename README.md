TUNA
====

Tuna is a distributed tuning infrastructure that provides pre-compiled kernels
for MIOpen customers through automated Jenkins pipelines and SLURM scalable
architecture. MITuna also provides a scalable task management infrastructure
ready to integrate with external libaries.

Prerequisites
-------------

Install python3.9
```
apt-get update && apt-get install software-properties-common
add-apt-repository ppa:deadsnakes/ppa
apt install python3.9 python3.9-dev python3.9-venv
```

Install pip for python3.9
```
wget https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3.9 get-pip.py
rm get-pip.py
```

Install MySQL server
```
apt-get install mysql-server
```

```
mysqld --initialize
grep 'temporary password' /var/log/mysql/error.log
```

Enable the service
```
systemctl start mysql
```

```
mysql -u root -p
<use the temporary password>
mysql> ALTER USER 'root'@'localhost' IDENTIFIED BY 'root-password';
mysql> CREATE DATABASE <database_name>;
```

Install ipmitool
```
apt-get install ipmitool
```

Setup passwordless ssh between all machines, for example:
```
ssh-keygen -t rsa
ssh-copy-id <user>@<ip-address>
ssh <user>@<ip-address>
```
For the tuning cycle, every machine needs to be able to access every other machine through
passwordless ssh.


Installation
------------
Clone the repo using
```
git clone <repo url>
```
Enter the Tuna directory
```
cd MITuna
```
Create a virtual environment, and activate it (by sourcing its `activate` script)
```
python3.9 -m venv myvenv
source myvenv/bin/activate
```
Install the required dependencies:
```
python3.9 -m pip install -r requirements.txt
```
The above assumes that Tuna lives in the home directory and the virtual environment was created using the command indicated above.

Add the following environment variables to a local file and then source the file:
```
export TUNA_DB_USER_NAME=root
export TUNA_DB_USER_PASSWORD=<password for root>
export TUNA_DB_HOSTNAME=localhost
export TUNA_DB_NAME=<database_name>
export TUNA_CELERY_JOB_BATCH_SIZE=<integer>

#rabbitMQ
export TUNA_CELERY_BROKER_HOST=localhost
export TUNA_CELERY_BROKER_USER=<username>
export TUNA_CELERY_BROKER_PWD=<pwd>
export TUNA_CELERY_BROKER_PORT=5672
#redis
export TUNA_CELERY_BACKEND_HOST=localhost
export TUNA_CELERY_BACKEND_PORT=6379

export gateway_ip=<gateway_ip>
export gateway_port=<gateway_port>
export gateway_user=<gateway_user>
```

All machines used in the tuning process must have ssh-keys enabled. MITuna needs to
have all-to-all machine communication available and passwords must not be required at run-time.

Run the setup scripts:
```
python3.9 setup.py develop
```

The root tuna folder needs to be appended to the PYTHONAPTH:
```
export PYTHONPATH=/<path_to_MITuna>/:$PYTHONPATH
```

To create the database run the following script:
```
./tuna/miopen/db/build_schema.py
```

The installation and setup are now complete. To start a tuning cycle, please follow the steps
documented in [TuningCycle](https://github.com/ROCm/MITuna/blob/develop/doc/src/TuningCycle.md)

Logs Storing and Analysis
---------------
For use cases requiring logs to be stored, searched and analyzed, Tuna integrates with Logstash and Elastic Search. 

This can be done through exporting the logstash destination details to enable the logs storing service. 

```
export TUNA_LOGSTASH_STATUS=true // this will turn logstash exporting on
export TUNA_LOGSTASH_HOST= <Your logstash host destination>
export TUNA_LOGSTASH_PORT= <Your logstash host port>

```

Code formatting
---------------

MITuna used yapf for code formatting:
```
cd MITuna/
yapf -i --style='{based_on_style: google, indent_width: 2}' --recursive tuna/ tests/ alembic/
```

Static code analysis
--------------------

In order for a PR to be accepted the following pylint command needs to result in 10/10 analysis:
```
cd MITuna/tuna
pylint -f parseable --max-args=8 --ignore-imports=no --indent-string='  ' *.py miopen/*.py example/*.py rocmlir/*.py utils/*.py miopen/celery_tuning/* miopen/utils/*.py
cd tuna && find miopen/scripts/ -type f -name '*.py' | xargs pylint -f parseable --max-args=8 --ignore-imports=no --indent-string=' '
cd tuna && find miopen/driver/ -type f -name '*.py' | xargs pylint -f parseable --max-args=8 --ignore-imports=no --indent-string=' '
cd tuna && find miopen/worker/ -type f -name '*.py' | xargs pylint -f parseable --max-args=8 --ignore-imports=no --indent-string=' '
cd tuna && pylint -f parseable --max-args=8 --ignore-imports=no --indent-string=' ' miopen/subcmd/import_configs.py
cd tuna && pylint -f parseable --max-args=8 --ignore-imports=no --indent-string=' ' miopen/subcmd/import_db.py
cd tuna && pylint -f parseable --max-args=8 --ignore-imports=no --indent-string=' ' miopen/subcmd/export_db.py
cd tuna && pylint -f parseable --max-args=8 --ignore-imports=no --indent-string=' ' miopen/subcmd/merge_db.py
cd tuna && pylint -f parseable --max-args=8 --ignore-imports=no --indent-string=' ' miopen/subcmd/update_golden.py
mypy tuna/miopen/utils/config_type.py
mypy tuna/connection.py --ignore-missing-imports
mypy tuna/abort.py --ignore-missing-imports
mypy tuna/miopen/utils/analyze_parse_db.py --ignore-missing-imports
mypy tuna/miopen/scripts/build_driver_cmd.py --ignore-missing-imports --follow-imports=skip
mypy tuna/miopen/scripts/corrupt_configs.py --ignore-missing-imports --follow-imports=skip
mypy tuna/miopen/subcmd/import_configs.py --ignore-missing-imports --follow-imports=skip
mypy tuna/miopen/subcmd/load_job.py --ignore-missing-imports --follow-imports=skip
mypy tuna/miopen/subcmd/export_db.py --ignore-missing-imports --follow-imports=skip
mypy tuna/miopen/subcmd/update_golden.py --ignore-missing-imports --follow-imports=skip
mypy tuna/miopen/parse_miopen_args.py --ignore-missing-imports --follow-imports=skip
mypy tuna/miopen/driver/convolution.py --ignore-missing-imports --follow-imports=skip
mypy tuna/yaml_parser.py --ignore-missing-imports --follow-imports=skip
mypy tuna/flask_example.py --ignore-missing-imports --follow-imports=skip
mypy tuna/go_fish.py --ignore-missing-imports --follow-imports=skip
mypy tuna/miopen/driver/batchnorm.py --ignore-missing-imports --follow-imports=skip
mypy tuna/miopen/worker/fin_class.py --ignore-missing-imports --follow-imports=skip
mypy tuna/miopen/worker/fin_eval.py --ignore-missing-imports --follow-imports=skip
mypy tuna/miopen/worker/fin_utils.py --ignore-missing-imports --follow-imports=skip
mypy tuna/utils/db_utility.py --ignore-missing-imports --follow-imports=skip
mypy tuna/worker_interface.py --ignore-missing-imports --follow-imports=skip
mypy tuna/grafana_dict.py --ignore-missing-imports --follow-imports=skip
mypy tuna/mituna_interface.py --ignore-missing-imports --follow-imports=skip
mypy tuna/libraries.py
mypy tuna/lib_utils.py --ignore-missing-imports --follow-imports=skip
mypy tuna/machine_management_interface.py --ignore-missing-imports --follow-imports=skip
yamllint tuna/miopen/yaml_files/*.yaml
yamllint tuna/example/*.yaml
mypy tuna/miopen/driver/base.py --ignore-missing-imports --follow-imports=skip
mypy tuna/machine.py --ignore-missing-imports --follow-imports=skip
mypy tuna/db/session_mixin.py --ignore-missing-imports --follow-imports=skip
mypy tuna/db/tuna_tables.py --ignore-missing-imports --follow-imports=skip
mypy tuna/parse_args.py --ignore-missing-imports --follow-imports=skip
mypy tuna/worker_interface.py --ignore-missing-imports --follow-imports=skip
mypy tuna/tables_interface.py --ignore-missing-imports --follow-imports=skip
mypy tuna/sql.py --ignore-missing-imports
mypy tuna/example/example_lib.py --ignore-missing-imports --follow-imports=skip
mypy tuna/example/example_tables.py --ignore-missing-imports --follow-imports=skip
mypy tuna/dbBase/sql_alchemy.py --ignore-missing-imports --follow-imports=skip
mypy tuna/dbBase/base_class.py --ignore-missing-imports
mypy tuna/example/session.py --ignore-missing-imports --follow-imports=skip
mypy tuna/example/tables.py --ignore-missing-imports --follow-imports=skip
mypy tuna/example/load_job.py --ignore-missing-imports --follow-imports=skip
mypy tuna/example/example_worker.py --ignore-missing-imports --follow-imports=skip
mypy tuna/rocmlir/import_configs.py --ignore-missing-imports --follow-imports=skip
mypy tuna/rocmlir/load_job.py --ignore-missing-imports --follow-imports=skip
mypy tuna/rocmlir/rocmlir_lib.py --ignore-missing-imports --follow-imports=skip
mypy tuna/rocmlir/rocmlir_tables.py --ignore-missing-imports --follow-imports=skip
mypy tuna/rocmlir/rocmlir_worker.py --ignore-missing-imports --follow-imports=skip
```
