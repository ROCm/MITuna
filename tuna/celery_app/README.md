#Install the latest requirements.txt file for your virtual environment.

Launch dockers through docker-compose:
```
sudo -E docker-compose up --build
```
This will launch a redis docker with the latest image and a custom docker for the celery worker.
The celery docker will display information about the celery setup such as the broker and result 
backend. These can be customized in `tuna/celery_app.celery.py`

Launch the celery docker container:
```
sudo docker exec -it mituna_celery_1 bash
```
Inside the celery container, set up the correct env and launch a tuning job, sample:
```
sudo docker exec -it mituna_celery_1 bash
export TUNA_DB_USER_NAME=root
export TUNA_DB_NAME=test_db
export TUNA_ROCM_VERSION=osdb-12969
export TUNA_DB_HOSTNAME=10.XXX.XX.XX
export TUNA_DB_USER_PASSWORD=myrootpwd
./go_fish.py miopen --fin_steps miopen_find_compile -l tuna_celery_compile --session_id 1
```

To test celery on a local machine:
Start the redis server:
```
redis-server --daemonize yes
```
Update the celery app backend config:
```
app = Celery('celery_app',
             broker_url="redis://localhost:6379//",
             result_backend="redis://localhost:6379/")
```
Clone MITuna and launch a tuning job:
```
git clone https://github.com/ROCmSoftwarePlatform/MITuna.git
cd MITuna
source ~/myvenv/bin/activate
source ~/db_env.db
celery -A tuna.celery_app.celery worker -l info -E

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
`
```
