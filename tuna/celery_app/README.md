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
sudo -E docker-compose up --build
```
This will launch a redis docker with the latest image and a custom docker for the celery worker.
The celery docker will display information about the celery setup such as the broker and result 
backend. These can be customized in `tuna/celery_app/celery_app.py`

Launch the celery docker container:
```
sudo docker exec -it mituna_celery_1 bash

To test celery on a local machine:
Start the redis server:
```
redis-server --daemonize yes
```

Clone MITuna and launch a celery worker:
```
git clone https://github.com/ROCmSoftwarePlatform/MITuna.git
cd MITuna
source ~/myvenv/bin/activate
source ~/db_env.db
celery -A tuna.celery_app.celery worker -l info -E -n worker_name -Q custom_q_name

```

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
export TUNA_CELERY_BROKER=localhost
```
