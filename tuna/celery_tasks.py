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
import time
import copy
import random
import string
from multiprocessing import Queue as mpQueue, Process, Lock
import queue
#import time
from sqlalchemy.exc import OperationalError, DataError, IntegrityError
from sqlalchemy.inspection import inspect

from celery.result import ResultSet

from tuna.utils.logger import setup_logger
from tuna.utils.utility import serialize_chunk
from tuna.utils.db_utility import get_db_obj_by_id, session_retry
from tuna.utils.db_utility import gen_update_query
from tuna.celery_app.celery import hardware_pick, app
from tuna.machine import Machine
from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.miopen_utility import load_machines
from tuna.miopen.utils.json_to_sql import process_fdb_w_kernels, process_pdb_compile
from tuna.miopen.utils.json_to_sql import clean_cache_table, get_worker_type
from tuna.miopen.db.tables import MIOpenDBTables
from tuna.miopen.worker.fin_utils import get_fin_result

LOGGER: logging.Logger = setup_logger('tune')
MAX_ERRORED_JOB_RETRIES = 3


def launch_worker_compile(q_name, machines, session_id):
  """Launch celery worker for compile"""
  for machine in machines:
    cmd = f"celery -A tuna.celery_app.celery worker -l info -E -n tuna_{machine.hostname}_sess_{session_id} -Q {q_name}".split(  #pylint: disable=line-too-long
        ' ')
    try:
      _ = subprocess.Popen(cmd)  #pylint: disable=consider-using-with
    except Exception as exp:  #pylint: disable=broad-exception-caught
      LOGGER.warning(exp)
      return False

    LOGGER.info('Successfully launched celery worker for compile')

  return True


def launch_worker_eval(q_name, machines, session_id):
  """Launch celery worker for eval"""
  curr_env = dict(os.environ.copy())
  for machine in machines:
    num_gpus = machine.get_avail_gpus()
    try:
      for gpu_id in num_gpus:
        cmd = f"celery -A tuna.celery_app.celery worker -l info -E -c 1 -n tuna_{machine.hostname}_sess_{session_id}_gpu_id{gpu_id} -Q {q_name}".split(' ')  #pylint: disable=line-too-long
        curr_env['HIP_VISIBLE_DEVICES'] = str(gpu_id)
        _ = subprocess.Popen(cmd, env=curr_env)  #pylint: disable=consider-using-with
        LOGGER.info("Successfully launched celery worker #%s for eval", gpu_id)
    except Exception as exp:  #pylint: disable=broad-exception-caught
      LOGGER.warning(exp)
      return False

  return True


def launch_celery_worker(library, q_name, machines):
  """Helper function to launch celery workers"""
  if 'miopen_find_compile' in library.args.fin_steps \
  or 'miopen_perf_compile' in library.args.fin_steps:
    ret = launch_worker_compile(q_name, machines, library.dbt.session_id)
  elif 'miopen_find_eval' in library.args.fin_steps or 'miopen_perf_eval' in library.args.fin_steps:
    ret = launch_worker_eval(q_name, machines, library.dbt.session_id)
  else:
    raise ValueError('Operation does not support celery workers')

  return ret


def stop_active_workers():
  """Shutdown active workers"""
  if app.control.inspect().active() is not None:
    app.control.shutdown()

  return True


def result_callback(task_id, value):
  """Function callback for celery async jobs to store resutls"""
  LOGGER.info('task id %s : done', task_id)
  LOGGER.info('fin_json : %s', value[0])
  LOGGER.info('context : %s', value[1])
  result_queue.put([value[0], value[1]])


#def close_job(session, job, worker_type, dbt=DBT):
#  """Setting final job state"""
#  if worker_type == 'fin_builder':
#    set_job_state(session, job, dbt, 'compiled')
#  else:
#    set_job_state(session, job, dbt, 'evaluated')


def process_fin_builder_results(fin_json, context, dbt):
  """Process result from fin_build worker"""
  LOGGER.info('Processing fin_builder result')
  config, job, kwargs = deserialize(context, dbt)
  pending = []

  failed_job = True
  result_str = ''
  failed_job = False
  status = None
  with DbSession() as session:
    try:
      set_job_state(session, job, dbt, 'compiled')
      if 'miopen_find_compile_result' in fin_json:
        status = process_fdb_w_kernels(session, fin_json,
                                       copy.deepcopy(context), dbt,
                                       context['fdb_attr'], pending)

      elif 'miopen_perf_compile_result' in fin_json:
        status = process_pdb_compile(session, fin_json, job, config, kwargs,
                                     dbt, context['fdb_attr'])

      success, result_str = get_fin_result(status)
      failed_job = not success

    except (OperationalError, IntegrityError) as err:
      LOGGER.warning('FinBuild: Unable to update Database %s', err)
      session.rollback()
      failed_job = True
    except DataError as err:
      LOGGER.warning(
          'FinBuild: Invalid data, likely large workspace. DB Error: %s', err)
      session.rollback()
      failed_job = True

    if failed_job:
      set_job_state(session, job, dbt, 'errored', False, result=result_str)
    else:
      set_job_state(session, job, dbt, 'compiled', False, result=result_str)

  return True


def deserialize(context, dbt):
  """Restore dict items(job, config) into objects"""
  config = get_db_obj_by_id(context['config']['id'], dbt.config_table)
  job = get_db_obj_by_id(context['job']['id'], dbt.job_table)
  kwargs = context['kwargs'].copy()

  return config, job, kwargs


def process_fin_evaluator_results(fin_json, context, dbt):
  """Process fin_json result"""
  LOGGER.info('Processing fin_eval result')
  _, job, _ = deserialize(context, dbt)
  failed_job = True
  result_str = ''
  pending = []
  orig_state = 'compiled'

  with DbSession() as session:
    try:
      set_job_state(session, job, dbt, 'evaluated')
      if 'miopen_find_eval_result' in fin_json:
        status = process_fdb_w_kernels(session,
                                       fin_json,
                                       copy.deepcopy(context),
                                       dbt,
                                       context['fdb_attr'],
                                       pending,
                                       result_str='miopen_find_eval_result',
                                       check_str='evaluated')
      elif 'miopen_perf_eval_result' in fin_json:
        status = process_fdb_w_kernels(session,
                                       fin_json,
                                       copy.deepcopy(context),
                                       dbt,
                                       context['fdb_attr'],
                                       pending,
                                       result_str='miopen_perf_eval_result',
                                       check_str='evaluated')

      success, result_str = get_fin_result(status)
      failed_job = not success

      if failed_job:
        if job.retries >= (MAX_ERRORED_JOB_RETRIES - 1):
          LOGGER.warning('max job retries exhausted, setting to errored')
          set_job_state(session, job, dbt, 'errored', result=result_str)
        else:
          LOGGER.warning('resetting job state to %s, incrementing retries',
                         orig_state)
          set_job_state(session,
                        job,
                        dbt,
                        orig_state,
                        increment_retries=True,
                        result=result_str)
      else:
        LOGGER.info("\n\n Setting job state to evaluated")
        set_job_state(session, job, dbt, 'evaluated', result=result_str)
        clean_cache_table(dbt, job)
    except (OperationalError, IntegrityError) as err:
      LOGGER.warning('FinBuild: Unable to update Database %s', err)
      session.rollback()
      failed_job = True

  return True


def set_job_state(session, job, dbt, state, increment_retries=False, result=""):
  """Interface function to update job state for builder/evaluator
  job_set_attr: List[str]"""

  LOGGER.info('Setting job id %s state to %s', job.id, state)
  job_set_attr = ['state', 'gpu_id']
  job.state = state
  if result:
    job_set_attr.append('result')
    job.result = result
  if increment_retries:
    job_set_attr.append('retries')
    job.retries += 1

  #pylint: disable=duplicate-code
  if '_start' in state:
    job_set_attr.append('cache_loc')
    cache: str = '~/.cache/miopen_'
    blurr: str = ''.join(
        random.choice(string.ascii_lowercase) for i in range(10))
    cache_loc: str = cache + blurr
    job.cache_loc = cache_loc
  #pylint: enable=duplicate-code

  query: str = gen_update_query(job, job_set_attr, dbt.job_table.__tablename__)

  def callback() -> bool:
    session.execute(query)
    session.commit()
    return True

  assert session_retry(session, callback, lambda x: x(), LOGGER)
  return True


#pylint: disable=too-many-locals
def tune(library, job_batch_size=1000):
  """tuning loop to spin out celery tasks"""

  worker_type = get_worker_type(library.args)
  machines = load_machines(library.args)
  q_name = None
  if worker_type == 'fin_build_worker':
    q_name = f"compile_q_session_{library.dbt.session_id}"
  else:
    q_name = f"eval_q_session_{library.dbt.session_id}"

  stop_active_workers()
  if not launch_celery_worker(library, q_name, machines):
    return False

  global DBT  #pylint: disable=global-variable-undefined
  global result_queue  #pylint: disable=global-variable-undefined
  global result_queue_lock  #pylint: disable=global-variable-undefined

  DBT = MIOpenDBTables(session_id=library.args.session_id,
                       config_type=library.args.config_type)

  fdb_attr = [column.name for column in inspect(DBT.find_db_table).c]
  fdb_attr.remove("insert_ts")
  fdb_attr.remove("update_ts")

  result_queue = mpQueue()
  result_queue_lock = Lock()

  f_vals = library.get_f_vals(Machine(local_machine=True), range(0))
  kwargs = library.get_kwargs(0, f_vals, tuning=True)

  res_set = ResultSet([])

  while True:
    try:
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

          entries = library.compose_work_objs_fin(session, job_list,
                                                  library.dbt)
          serialized_jobs = serialize_chunk(entries)

          for job, config in serialized_jobs:
            context = {
                'job': job,
                'config': config,
                'worker_type': worker_type,
                'arch': library.dbt.session.arch,
                'num_cu': library.dbt.session.num_cu,
                'kwargs': kwargs,
                'fdb_attr': fdb_attr
            }
            #enqueuing to celery queue
            res_set.add(hardware_pick.apply_async((context,), queue=q_name))

      if not job_list:
        if not res_set:
          return False
        LOGGER.info('All tasks added to queue')
        break
      LOGGER.info('TEST')
    except KeyboardInterrupt as err:
      LOGGER.error('%s', err)
      #dump celery queue

  LOGGER.info('Started drain process')
  #start draining result_queue in subprocess
  drain_process = Process(target=drain_queue, args=[worker_type, DBT])
  drain_process.start()

  LOGGER.info('Gathering async results in callback function, blocking')
  _ = res_set.join(callback=result_callback)

  #terminate result_queue drain process with special queue token (NONE,NONE)
  result_queue.put([None, None])

  drain_process.join()
  #CTRL C needs to drain the redis queue and results_queue

  return True


def drain_queue(worker_type, dbt):
  """Drain results queue"""
  LOGGER.info('Draining queue')
  while True:
    try:
      fin_json, context = result_queue.get(True, 1)
      LOGGER.info('Parsing: %s', fin_json)
      LOGGER.info('Parsing context: %s', context)
      if fin_json is None and context is None:
        LOGGER.info('Reached end of results queue')
        break
      if worker_type == 'fin_build_worker':
        process_fin_builder_results(fin_json, context, dbt)
      else:
        LOGGER.info("\n\n Processing eval results")
        process_fin_evaluator_results(fin_json, context, dbt)
    except queue.Empty as exc:
      LOGGER.warning(exc)
      LOGGER.info('Sleeping for 2 sec, waiting on results from celery')
      time.sleep(2)

  return True
