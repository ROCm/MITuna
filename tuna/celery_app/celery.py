from multiprocessing import Lock, Queue as mpQueue
from celery import Celery
from celery.utils.log import get_task_logger
from tuna.miopen.utils.lib_helper import get_worker
from tuna.utils.utility import SimpleDict
from tuna.machine import Machine

app = Celery('celery_app',
             broker='redis://localhost:6379/0',
             backend='redis://localhost:6379/0',
             includes=[
                 'tuna.celery_app.celery.celery_enqueue_gfx908_120',
                 'tuna.celery_app.celery.celery_enqueue_gfx1030_36',
             ])
logger = get_task_logger(__name__)

#             include=['proj.tasks'])

# Optional configuration, see the application user guide.
app.conf.update(result_expires=3600,)
app.autodiscover_tasks()


@app.task(bind=True)
def celery_enqueue_gfx908_120(self, args, kwargs):
  """defines a celery task"""
  logger.info("Enqueueing gfx908-120")
  kwargs = prep_kwargs(kwargs, args)
  worker = get_worker(kwargs, args[2])
  worker.run()


@app.task(bind=True)
def celery_enqueue_gfx1030_36(self, args, kwargs):
  """defines a celery task"""
  logger.info("Enqueueing gfx1030-36")
  kwargs = prep_kwargs(kwargs)
  worker = get_worker(kwargs, args[2])
  worker.run()


def prep_kwargs(kwargs, args):
  """Populate kwargs with serialized job, config and machine"""
  kwargs["job"] = SimpleDict(**args[0])
  kwargs["config"] = SimpleDict(**args[1])
  kwargs["machine"] = Machine(local_machine=True)
  kwargs["result_queue"] = mpQueue()
  kwargs["result_queue_lock"] = Lock()

  return kwargs


if __name__ == '__main__':
  app.start()
