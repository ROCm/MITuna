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
"""Interface class to set up and launch tuning functionality"""
import logging
import time
from itertools import islice
from celery.result import ResultBase

from tuna.utils.logger import setup_logger
from tuna.utils.utility import serialize_chunk
from tuna.celery_app.celery import group_tasks
from tuna.machine import Machine

LOGGER: logging.Logger = setup_logger('tune')


def tune(library, blocking=None):
  """tuning loop to spin out celery tasks"""

  f_vals = library.get_f_vals(Machine(local_machine=True), range(0))
  kwargs = library.get_kwargs(0, f_vals, tuning=True)

  job_config_rows = library.get_jobs(library.fetch_state,
                                     library.args.session_id)
  if not job_config_rows:
    return False

  iterator = iter(job_config_rows)
  #test launching 5 async jobs at a time,
  #celery default is 72
  while chunk := list(islice(iterator, 5)):
    serialized_jobs = serialize_chunk(chunk)
    #delay launches each group in separate process
    result = group_tasks.delay(serialized_jobs, library.worker_type, kwargs,
                               library.dbt.session.arch,
                               str(library.dbt.session.num_cu))
    if blocking:
      LOGGER.info('Collecting result for group task: %s ', result.id)
      while not result.ready():
        time.sleep(5)
      LOGGER.info('Group %s ready: %s', result.id, result.ready())
      LOGGER.info('Group successful: %s', result.successful())
      LOGGER.info(result.get())

    #v = ResultGroup = tree, leafs are AsyncTasks
    #print([
    #    v for v in result.collect() if not isinstance(v, (ResultBase, tuple))
    #  ])
    else:
      #async result gather
      print(v for v in result.collect())

  return False
