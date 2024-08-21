#!/usr/bin/env python3

###############################################################################
#
# MIT License
#
# Copyright (c) 2024 Advanced Micro Devices, Inc.
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
"""Module to register MIOpen celery tasks"""
import copy
from celery.signals import celeryd_after_setup
from celery.utils.log import get_task_logger
from tuna.celery_app.celery_app import app
from tuna.libraries import Operation
from tuna.machine import Machine
from tuna.utils.utility import SimpleDict
from tuna.example.example_lib import Q_NAME
from tuna.example.example_worker import ExampleWorker

logger = get_task_logger(__name__)


@celeryd_after_setup.connect
def capture_worker_name(sender, instance, **kwargs):  #pylint: disable=unused-argument
  """Capture worker name"""
  app.worker_name = sender


cached_machine = Machine(local_machine=True)


def prep_kwargs(kwargs, args):
  """Populate kwargs with serialized job and machine"""
  kwargs["job"] = SimpleDict(**args[0])
  kwargs["machine"] = cached_machine

  return kwargs


cached_worker = {}


def prep_worker(context):
  """Creating tuna worker object based on context"""
  operation = context['operation']
  if operation in cached_worker:
    worker = cached_worker[operation]
    worker.job = SimpleDict(**context['job'])
    worker.gpu_id = context['kwargs']['gpu_id']
  else:
    args = [context['job'], context['operation']]
    kwargs = prep_kwargs(context['kwargs'], args)
    worker = ExampleWorker(**kwargs)
    cached_worker[operation] = worker
  return worker


@app.task(trail=True, reply_to=Q_NAME)
def celery_enqueue(context):
  """Defines a celery task"""
  worker = prep_worker(copy.deepcopy(context))
  ret = worker.run()
  return {"ret": ret, "context": context}
