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
import time
import asyncio
from datetime import timedelta
from multiprocessing import Process, Value
import kombu

from tuna.utils.logger import setup_logger
from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.miopen_utility import load_machines
from tuna.miopen.utils.json_to_sql import get_worker_type
from tuna.celery_app.celery_workers import launch_celery_worker
from tuna.celery_app.celery_app import stop_active_workers, purge_queue
from tuna.celery_app.utility import get_q_name

LOGGER: logging.Logger = setup_logger('tuning')


def prep_tuning(library):
  """Prep env for tuning start"""
  worker_type = get_worker_type(library.args)
  machines = load_machines(library.args)
  cmd = None
  subp_list = []
  q_name = None
  if worker_type == 'fin_build_worker':
    q_name = get_q_name(library, compile=True)
    cmd = f"celery -A tuna.celery_app.celery_app worker -l info -E -n tuna_HOSTNAME_sess_{library.args.session_id} -Q {q_name}"  #pylint: disable=line-too-long
  else:
    q_name = get_q_name(library, eval=True)
    cmd = f"celery -A tuna.celery_app.celery_app worker -l info -E -c 1 -n tuna_HOSTNAME_sess_{library.args.session_id}_gpu_id_GPUID -Q {q_name}"  #pylint: disable=line-too-long

  if not library.args.enqueue_only:
    try:
      subp_list = launch_celery_worker(machines,
                                       library.get_worker_granularity(), cmd,
                                       True)
      if not subp_list:
        raise ValueError('Could not launch celery worker')
    except kombu.exceptions.OperationalError as k_err:
      LOGGER.error('Redis error ocurred: %s', k_err)
      return False
  else:
    purge_queue([q_name])

  return q_name, subp_list


#pylint: disable=too-many-locals
def tune(library, job_batch_size=1000):
  """tuning loop to spin out celery tasks"""

  if library.args.shutdown_workers:
    LOGGER.info('Shutting down all celery workers')
    stop_active_workers()
    return True

  try:
    LOGGER.info('Launching celery workers')
    q_name, subp_list = prep_tuning(library)
    LOGGER.info('Done launching celery workers')
  except ValueError as verr:
    LOGGER.error(verr)
    return False

  try:
    #if enqueue_only is False, we launch the celery workers
    if not library.args.enqueue_only:
      for subp in subp_list:
        subp.wait()
      return True
  except KeyboardInterrupt:
    for subp in subp_list:
      subp.kill()
    return False

  start = time.time()

  db_name = os.environ['TUNA_DB_NAME']
  prefix = f"d_{db_name}_sess_{library.args.session_id}"
  prefix = "test"
  with DbSession() as session:
    job_list = library.get_jobs(session,
                                library.fetch_state,
                                library.set_state,
                                library.args.session_id,
                                no_update=True)
  job_counter = Value('i', len(job_list))
  LOGGER.info('Job counter: %s', job_counter.value)
  enqueue_proc = None
  try:
    if job_counter.value == 0:
      LOGGER.info('No new jobs found')
    else:

      enqueue_proc = Process(target=library.enqueue_jobs,
                             args=[job_batch_size, q_name])
      #Start enqueue proc
      enqueue_proc.start()

    #start async consume thread, blocking
    LOGGER.info('Starting consume thread')
    asyncio.run(library.consume(job_counter, prefix))
    LOGGER.info('Closed consume thread')

    if enqueue_proc:
      enqueue_proc.join()

  except (KeyboardInterrupt, Exception) as exp:  #pylint: disable=broad-exception-caught
    LOGGER.error('Error ocurred %s', exp)
    purge_queue([q_name])
    library.cancel_consumer(q_name)
    library.reset_job_state_on_ctrl_c()

  library.cancel_consumer(q_name)
  end = time.time()
  LOGGER.info("Took {:0>8} to tune".format(str(timedelta(seconds=end - start))))  #pylint: disable=consider-using-f-string

  return True
