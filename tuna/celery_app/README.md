#Install the latest requirements.txt file for your virtual environment.

Launch dockers through docker-compose:
```
sudo -E docker-compose up --build
```
This will launch a redis docker with the latest image and a custom docker for the celery worker.
The celery docker will display information about the celery setup such as the broker and result 
backend. These can be customized in `tuna/celery_app.celery.py`

Open a terminal and launch a tuning job, sample:
```
./go_fish.py miopen --fin_steps miopen_find_compile -l tuna_celery_compile --session_id 1
```


Note: if redis is not running in a docker, from docker-compose.
Make sure redis-server is running on the headnode:
```
redis-server --daemonize yes
```
