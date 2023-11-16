#!/usr/bin/env python3
###############################################################################
#
# MIT License
#
# Copyright (c) 2023 Advanced Micro Devices, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
###############################################################################
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
