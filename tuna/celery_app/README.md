#Tuning with celery

MITuna launches celery workers and uses redis as a broker and backend result. Celery is a custom
scheduler which abstracts job scheduling for the purpose of tuning. Tuna launches 1 celery worker
per node for the compile step and 1 celery worker per GPU for the evaluate step.

MITuna enqueues all tuning jobs into the redis queue. The celery workers then pull from the redis
queue and launch the tuning jobs. The results of the tuning jobs are asynchronously collected by
MITuna and the mySQL backend is updated accordingly.

The following steps in MITuna make use of celery workers:
```
./go_fish.py miopen --fin_steps miopen_find_compile --session_id 1
./go_fish.py miopen --fin_steps miopen_find_eval --session_id 1
./go_fish.py miopen --fin_steps miopen_perf_compile --session_id 1
./go_fish.py miopen --fin_steps miopen_perf_eval --session_id 1
```

A celery worker can be launched manually on a machine like this:

Launch dockers through docker-compose:
```
sudo -E docker compose up --build
```
This will launch a redis docker with the latest image and a custom docker for the celery worker.
The celery docker will display information about the celery setup such as the broker and result 
backend. These can be customized in `tuna/celery_app/celery_app.py`

Launch the celery docker container:
```
sudo docker exec -it mituna_celery_1 bash

To test celery on a local machine:
Install redis and start the redis server:
```
redis-server --daemonize yes
```
Intall rabbitMQ that is used as a broker by celery. Instructions can be found here: [Install rabbitMQ](https://www.rabbitmq.com/docs/install-debian)

Clone MITuna and launch a celery worker:
```
git clone https://github.com/ROCmSoftwarePlatform/MITuna.git
cd MITuna
source ~/myvenv/bin/activate
source ~/db_env.db
celery -A tuna.celery_app.celery worker -l info -E -n worker_name -Q custom_q_name

```

##User interfaces to track redis backend and rabbitMQ broker data

MITuna provides a docker compose file to launch [flower](https://flower.readthedocs.io/en/latest/), which helps track the tuning:
```
docker compose -f docker-compose-flower_rabbitmq.yaml up --build -d
```
Navigate to `http://localhost:5555` to interact with the flower UI.

To track the rabbitMQ broker data,install the following:
```
rabbitmq-plugins enable rabbitmq_management
```
Navigate to `http://localhost:15672` to interact with the rabbitMQ UI. The username and password required
have to be set up through rabbitMQ, see: [rabbitMQ access control](https://www.rabbitmq.com/docs/access-control).


Note:
myvenv is the virtual environment as per MITuna/requirements.txt.

db_env.db contains the database env variables:
```
export TUNA_DB_USER_NAME=root
export TUNA_DB_NAME=test_db
export TUNA_ROCM_VERSION=osdb-12969
export TUNA_DB_HOSTNAME=10.XXX.XX.XX
export TUNA_DB_USER_PASSWORD=myrootpwd
export TUNA_CELERY_JOB_BATCH_SIZE=10 (optional)
#rabbitMQ
export TUNA_CELERY_BROKER_HOST=localhost
export TUNA_CELERY_BROKER_USER=<username>
export TUNA_CELERY_BROKER_PWD=<pwd>
export TUNA_CELERY_BROKER_PORT=5672
#redis
export TUNA_CELERY_BACKEND_HOST=localhost
export TUNA_CELERY_BACKEND_PORT=6379
```

##Flower
[Celery flower](https://flower.readthedocs.io/en/latest/) can be installed to track tuning through
celery. MITuna provides a docker compose in the root directory *docker-compose-flower.yaml*.
To launch:
```
docker compose up -f docker-compose-flower.yaml --build
```

Note:
The docker-compose-flower.yaml file pulls in env variables from the local .env file. This file
does not reside in MITuna and must be created by the user. Sample .env file:
```
export db_name=<db_name>
export db_host=<hostname>
export db_user=root
export db_password=<pwd>
```
