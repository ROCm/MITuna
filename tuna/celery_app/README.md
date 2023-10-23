#Install the latest requirements.txt file for your virtual environment.

Make sure redis-server is running on the headnode:
```
redis-server --daemonize yes
```

To launch the worker:
```
cd MITuna
celery -A tuna.celery_app.celery worker --loglevel=INFO -E
```
then run any go_fish.py command that includes: applicability, builder/eval work.
Note: the celery task needs to be registered in the includes part of the Celery() app. 
