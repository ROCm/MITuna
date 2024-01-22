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
#from celery.result import GroupResult

from tuna.utils.logger import setup_logger
from tuna.utils.utility import serialize_chunk
from tuna.utils.db_utility import db_rows_to_obj
from tuna.celery_app.celery import group_tasks
from tuna.machine import Machine
from tuna.dbBase.sql_alchemy import DbSession

LOGGER: logging.Logger = setup_logger('tune')


#pylint: disable=too-many-locals
def tune(library, group_size, blocking=None, job_batch_size=1000):
  """tuning loop to spin out celery tasks"""

  LOGGER.info('Celery running with group size: %s', group_size)
  f_vals = library.get_f_vals(Machine(local_machine=True), range(0))
  kwargs = library.get_kwargs(0, f_vals, tuning=True)

  results_list = []
  while True:
    job_list = []
    with DbSession() as session:
      job_list = library.get_jobs(session, library.fetch_state, library.set_state,
                                         library.args.session_id, job_batch_size)

      for i in range(0, len(job_list), job_batch_size):
        batch_jobs = job_list[i:min(i + job_batch_size, len(job_list))]
        if library.args.fin_steps:
          entries = library.compose_work_objs_fin(session, batch_jobs, library.dbt)

        iterator = iter(entries)
        while chunk := list(islice(iterator, group_size)):
          serialized_jobs = serialize_chunk(chunk)
          job = group_tasks(serialized_jobs, library.worker_type, kwargs,
                            library.dbt.session.arch,
                            str(library.dbt.session.num_cu))
          #result is of type GroupResult aka list of AsyncResult
          result = job.apply_async()
          results_list.append(result)
          if blocking:
            LOGGER.info('Collecting result for group task: %s ', result.id)
            #result.wait(timeout=10)
            while not result.ready():
              time.sleep(5)
            LOGGER.info('Group successful: %s', result.successful())
            LOGGER.info(result.get())

          #v = ResultGroup = tree, leafs are AsyncTasks
          #print([
          #    v for v in result.collect() if not isinstance(v, (ResultBase, tuple))
          #  ])
          #else:
          #async result gather
          #job.apply_async()
          #job.collect()
          #print(v for v in result.collect())
          #print('Non blocking result gather')

        LOGGER.info('Done launching %s celery groups', len(job_list))

    if not job_list:
      if not results_list:
        LOGGER.info('Last celery group finished')
        return False
      #wait for last group
      while results_list:
        result = results_list.pop(0)
        while not result.ready():
          time.sleep(10)
        if len(results_list) < group_size:
          break
      #check if more jobs appeared

  return False
