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
from tuna.miopen.utils.lib_helper import get_worker
from tuna.utils.utility import SimpleDict
from tuna.utils.celery_utils import prep_default_kwargs, get_cached_worker
from tuna.miopen.miopen_lib import Q_NAME

logger = get_task_logger(__name__)


@celeryd_after_setup.connect
def capture_worker_name(sender, instance, **kwargs):  #pylint: disable=unused-argument
  """Capture worker name"""
  app.worker_name = sender


cached_machine = Machine(local_machine=True)


def prep_kwargs(kwargs, args):
  """Populate kwargs with serialized job, config and machine"""
  kwargs = prep_default_kwargs(kwargs, args, cached_machine)
  kwargs["config"] = SimpleDict(**args[1])

  return kwargs


cached_worker = {}


def prep_worker(context):
  """Creating tuna worker object based on context"""
  operation = context['operation']
  if operation in cached_worker:
    worker = get_cached_worker(context, cached_worker)
    worker.config = SimpleDict(**context['config'])
  else:
    args = [context['job'], context['config'], context['operation']]
    kwargs = prep_kwargs(context['kwargs'], args)
    worker = get_worker(kwargs, args[2])
    cached_worker[operation] = worker
  return worker


@app.task(trail=True, reply_to=Q_NAME)
def celery_enqueue(context):
  """Defines a celery task"""
  kwargs = context['kwargs']
  operation = context['operation']

  if operation == Operation.EVAL:
    gpu_id = int((app.worker_name).split('gpu_id_')[1])
    kwargs['gpu_id'] = gpu_id
    context['job']['gpu_id'] = gpu_id
    logger.info("Enqueueing worker %s: gpu(%s), job %s", app.worker_name,
                gpu_id, context['job'])
  else:
    logger.info("Enqueueing worker %s: job %s", app.worker_name, context['job'])

  worker = prep_worker(copy.deepcopy(context))
  ret = worker.run()
  return {"ret": ret, "context": context}
