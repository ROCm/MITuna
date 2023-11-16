from os import environ
from celery import Celery
from celery.utils.log import get_task_logger
from tuna.miopen.utils.lib_helper import get_worker
from tuna.miopen.utils.helper import prep_kwargs
from tuna.machine import Machine
from tuna.celery_app import celery_config

environ.setdefault('CELERY_CONFIG_MODULE', 'celery_config')
#app = Celery()
#app.config_from_envvar('CELERY_CONFIG_MODULE')
app = Celery('celery_app',
             broker_url="redis://localhost:6379/",
             result_backend="redis://localhost:6379/")
#app.config_from_module("celery_config")
app.config_from_object(celery_config)
app.conf.update(result_expires=3600,)
app.autodiscover_tasks()
app.conf.result_backend_transport_options = {'retry_policy': {'timeout': 5.0}}
logger = get_task_logger(__name__)


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


if __name__ == '__main__':
  app.start()
