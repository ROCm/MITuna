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
from celery.utils.log import get_task_logger
from tuna.miopen.utils.lib_helper import get_worker
from tuna.miopen.utils.helper import prep_kwargs
from tuna.celery_app.celery_app import app

logger = get_task_logger(__name__)


def prep_worker(context):
  """Creating tuna worker object based on context"""
  args = [context['job'], context['config'], context['worker_type']]
  kwargs = prep_kwargs(context['kwargs'], args)
  worker = get_worker(kwargs, args[2])
  return worker


@app.task(trail=True, reply_to='eval_q_session_153')
def celery_enqueue(context):
  """Defines a celery task"""
  logger.info("Enqueueing gfx908-120")
  worker = prep_worker(copy.deepcopy(context))
  ret = worker.run()
  return ret, context