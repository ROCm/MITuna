# TUNA 
Tuna is a distributed tuning infrastructure that provides pre-compiled kernels for MIOpen customers
through automated Jenkins pipelines and SLURM scalable architecture.


## Prerequisites
Install python3.9
```
apt-get update && apt-get install software-properties-common
add-apt-repository ppa:deadsnakes/ppa
apt install python3.9
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
Enter the Tuna directory
```
cd MITuna
```
Create a virtual envornment, and activate it (by sourcing its `activate` script)
```
virtualenv -p python3.9 myvenv
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
export TUNA_DB_PASSWORD=<password for root>
export TUNA_DB_HOSTNAME=localhost
export TUNA_DB_NAME=<database_name>
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

The root tuna folder needs to be appeneded to the PYTHONAPTH:
```
export PYTHONPATH=/<path_to_MITuna>/:$PYTHONPATH
```

To create the database run the following script:
```
./tuna/db_tables.py
```

The installation and setup are now complete. To start a tuning cycle, please follow the steps
documented in [TuningCycle](https://github.com/ROCmSoftwarePlatform/MITuna/blob/develop/doc/TuningCycle.md)

## Code formatting

MITuna used yapf for code formatting:
```
yapf -i --style='{based_on_style: google, indent_width: 2}' --recursive tuna/
yapf -i --style='{based_on_style: google, indent_width: 2}' --recursive tests/
```

## Static code analysis

In order for a PR to be accepted the following `pylint` command needs to result in 10/10 analysis:
```
cd MITuna/tuna
pylint -f parseable -d duplicate-code --max-args=8 --indent-string '  ' *.py
```
