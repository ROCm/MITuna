from celery import Celery, shared_task
from celery.utils.log import get_task_logger
from tuna.miopen.utils.lib_helper import get_worker
from tuna.utils.utility import SimpleDict

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
def celery_task(self, args, kwargs):
  """defines a celery task"""
  #logger.info(worker.session_id)
  #arg[0] is job
  #arg[1] is worker_type
  #kwargs for Worker constructor
  #print(f"args[0] {args[0]}")
  #logger.info(args[1])
  #logger.info(kwargs)
  
  new_job = SimpleDict(**args[0])
  job_config = args[1]
  print(f"config {args[1]}")
  kwargs["job"] = new_job 
  #kwargs["config"] = job_config 
  kwargs["config"] = SimpleDict(**args[1]) 
  
  print(f"JOB {kwargs['job']}")
  print(f"CONFIG {kwargs['config']}")
  worker = get_worker(kwargs, args[2])
  worker.run()
  #print(worker.worker_type)
  return args[0]

if __name__ == '__main__':
  app.start()
