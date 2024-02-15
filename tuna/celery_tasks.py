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
import os
import logging
import subprocess
#import time
from celery.result import ResultSet

from tuna.utils.logger import setup_logger
from tuna.utils.utility import serialize_chunk
from tuna.celery_app.celery import hardware_pick, app
from tuna.machine import Machine
from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.miopen_utility import load_machines

LOGGER: logging.Logger = setup_logger('tune')


def launch_worker_compile():
  """Launch celery worker for compile"""
  cmd = "celery -A tuna.celery_app.celery worker -l info -E -n compile_worker".split(
      ' ')
  try:
    _ = subprocess.Popen(cmd)  #pylint: disable=consider-using-with
  except Exception as exp:  #pylint: disable=broad-exception-caught
    LOGGER.warning(exp)
    return False

  LOGGER.info('Successfully launched celery worker for compile')

  return True


def launch_worker_eval(library):
  """Launch celery worker for eval"""
  machines = load_machines(library.args)
  curr_env = dict(os.environ.copy())
  for machine in machines:
    num_gpus = machine.get_avail_gpus()
    try:
      for gpu_id in num_gpus:
        cmd = f"celery -A tuna.celery_app.celery worker -l info -E -c 1 -n eval_worker_{gpu_id}".split(' ')  #pylint: disable=line-too-long
        curr_env['HIP_VISIBLE_DEVICES'] = str(gpu_id)
        _ = subprocess.Popen(cmd, env=curr_env)  #pylint: disable=consider-using-with
        LOGGER.info("Successfully launched celery worker #%s for eval", gpu_id)
    except Exception as exp:  #pylint: disable=broad-exception-caught
      LOGGER.warning(exp)
      return False

  return True


def launch_celery_worker(library):
  """Helper function to launch celery workers"""
  if 'miopen_find_compile' in library.args.fin_steps \
  or 'miopen_perf_compile' in library.args.fin_steps:
    ret = launch_worker_compile()
  elif 'miopen_find_eval' in library.args.fin_steps or 'miopen_perf_eval' in library.args.fin_steps:
    ret = launch_worker_eval(library)
  else:
    raise ValueError('Operation does not support celery workers')

  return ret


def stop_active_workers():
  """Shutdown active workers"""
  if app.control.inspect.active() is not None:
    app.control.shutdown()

  return True


def result_callback(task_id, value):
  """Function callback for celery async jobs to store resutls"""
  _ = app.AsyncResult(task_id).get()
  #LOGGER.info('task id %s : done', task_id)
  LOGGER.info('result : %s', value)


#pylint: disable=too-many-locals
def tune(library, job_batch_size=1000):
  """tuning loop to spin out celery tasks"""

  #stop_active_workers()
  if not launch_celery_worker(library):
    return False

  f_vals = library.get_f_vals(Machine(local_machine=True), range(0))
  kwargs = library.get_kwargs(0, f_vals, tuning=True)

  res_set = ResultSet([])

  while True:
    job_list = []
    with DbSession() as session:
      job_list = library.get_jobs(session, library.fetch_state,
                                  library.set_state, library.args.session_id,
                                  job_batch_size)

      for i in range(0, len(job_list), job_batch_size):
        batch_jobs = job_list[i:min(i + job_batch_size, len(job_list))]
        if library.args.fin_steps:
          entries = library.compose_work_objs_fin(session, batch_jobs,
                                                  library.dbt)

        entries = library.compose_work_objs_fin(session, job_list, library.dbt)
        serialized_jobs = serialize_chunk(entries)

        for job in serialized_jobs:
          context = {
              'job': job[0],
              'config': job[1],
              'worker_type': library.worker_type,
              'arch': library.dbt.session.arch,
              'num_cu': library.dbt.session.num_cu,
              'kwargs': kwargs
          }
          res_set.add(hardware_pick.apply_async((context,), queue="celery"))

    if not job_list:
      if not res_set:
        return False
      LOGGER.info('All tasks added to queue')
      break

  LOGGER.info('Gathering async results')
  _ = res_set.join(callback=result_callback)
  LOGGER.info('Done gathering results')

  return True
