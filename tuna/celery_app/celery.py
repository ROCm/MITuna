from celery import Celery, shared_task
from celery.utils.log import get_task_logger

app = Celery('celery_app',
              broker='redis://localhost:6379/0',
              backend='redis://localhost:6379/0',
              includes=['tuna.celery_app.celery.celery_task'])
logger = get_task_logger(__name__)

#             include=['proj.tasks'])

# Optional configuration, see the application user guide.
app.conf.update(result_expires=3600,)
app.autodiscover_tasks()

@app.task(bind=True)
def celery_task(self, kwargs, job):
  """defines a celery task"""
  #logger.info(worker.session_id)
  logger.info(job)

if __name__ == '__main__':
  app.start()
