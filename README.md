# TUNA 
Tuna is a distributed tuning infrastructure that provides pre-compiled kernels for MIOpen customers
through automated Jenkins pipelines and SLURM scalable architecture.


## Prerequisites
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

Setup passwordless ssh between all machines, for example:
```
ssh-keygen -t rsa
ssh-copy-id <user>@<ip-address>
ssh <user>@<ip-address>
```
For the tuning cycle, every machine needs to be able to access every other machine through
passwordless ssh.


## Installation
Clone the repo using 
```
git clone <repo url>
```
Then create a virtual env using 
```
virtualenv -p python3 myvenv
```
Enter the Tuna directory
```
cd MITunaX
```
Activate the virtualenv and source the virtual env for subsequent use
```
virtualenv -p python3 myvenv
source myvenv/bin/activate
```
Install the required dependencies:
```
pip install -r requirements.txt
```
The above assumes that Tuna lives in the home directory and the virtual environment was created using the command indicated above.

Add the following environment variables to a local file and then source the file:
```
export TUNA_DB_USER_NAME=root
export TUNA_DB_PASSWORD=<password for root>
export TUNA_DB_HOSTNAME=localhost
export TUNA_DB_NAME=<database_name>
export gateway_ip=<gateway_ip>
export gateway_port=<gateway_port>
export gateway_user=<gateway_user>
```

All machines used in the tuning process must have ssh-keys enabled. MITunaX needs to
have all-to-all machine communication available and passwords must not be required at run-time.

Run the setup scripts:
```
python3 setup.py develop
```

The root tuna folder needs to be appeneded to the PYTHONAPTH:
```
export PYTHONPATH=/<path_to_MITunaX>/:$PYTHONPATH
```

To create the database run the following script:
```
./tuna/db_tables.py
```

The installation and setup are now complete. To start a tuning cycle, please follow the steps
documented in [TuningCycle](https://github.com/ROCmSoftwarePlatform/MITunaX/blob/develop/doc/TuningCycle.md)

## Code formatting

MITunaX used yapf for code formatting:
```
yapf -i --style='{based_on_style: google, indent_width: 2}' --recursive tuna/
yapf -i --style='{based_on_style: google, indent_width: 2}' --recursive tests/
```

## Static code analysis

In order for a PR to be accepted the following `pylint` command needs to result in 10/10 analysis:
```
cd MITunaX/tuna
pylint -f parseable -d duplicate-code --max-args=8 --indent-string '  ' *.py
```
