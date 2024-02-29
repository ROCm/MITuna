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
from tuna.utils.utility import serialize_chunk, SimpleDict
from tuna.utils.db_utility import has_attr_set, get_db_obj_by_id, gen_insert_query, session_retry
from tuna.utils.db_utility import gen_update_query
from tuna.celery_app.celery import hardware_pick, app
from tuna.machine import Machine
from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.miopen_utility import load_machines
from tuna.miopen.utils.json_to_sql import process_fdb_w_kernels, process_pdb_compile
from tuna.miopen.db.tables import MIOpenDBTables
from tuna.miopen.worker.fin_utils import get_fin_result
from tuna.miopen.db.solver import get_solver_ids

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
  if app.control.inspect().active() is not None:
    app.control.shutdown()

  return True


def result_callback(task_id, value):
  """Function callback for celery async jobs to store resutls"""
  #_ = app.AsyncResult(task_id).get()
  LOGGER.info('task id %s : done', task_id)
  LOGGER.info('fin_json : %s', value[0])
  LOGGER.info('context : %s', value[1])
  result_queue.put([value[0], value[1]])


def close_job(session, job):
  """Setting final job state"""
  if worker_type == 'fin_builder':
    set_job_state(session, job, DBT, 'compiled')
  else:
    set_job_state(session, job, DBT, 'evaluated')


def __result_queue_commit(session, close_job):  #pylint: disable=redefined-outer-name
  """commit the result queue and set mark job complete"""
  while not result_queue.empty():
    obj_list = []
    res_list = result_queue.get(True, 1)
    res_job = res_list[1][0]
    for _, obj in res_list:
      obj_list.append(obj)

    LOGGER.info("commit pending job %s, #objects: %s", res_job.id,
                len(obj_list))
    status = session_retry(session, __add_sql_objs,
                           lambda x: x(session, obj_list, FDB_ATTR, DBT),
                           LOGGER)
    if not status:
      LOGGER.error("Failed commit pending job %s", res_job.id)
      return False

    job = get_db_obj_by_id(res_job['id'], DBT.find_db_table.__tablename__)

    close_job(session, job)

  return True


def __add_sql_objs(session, obj_list, fdb_attr, dbt):
  """add sql objects to the table"""
  for obj in obj_list:
    if isinstance(obj, SimpleDict):
      if has_attr_set(obj, fdb_attr):
        query = gen_insert_query(obj, fdb_attr, dbt.find_db_table.__tablename__)
        session.execute(query)
      else:
        return False
    else:
      session.add(obj)
  session.commit()
  return True


def result_queue_drain():
  """check for lock and commit the result queue"""
  if result_queue_lock.acquire(block=False):
    with DbSession() as session:
      __result_queue_commit(session, close_job)
    result_queue_lock.release()
    return True
  return False


def reset_started_jobs(session, job_dict, fetch_state):  #pylint: disable=unused-argument
  """finish committing result queue"""
  print(job_dict)
  job = get_db_obj_by_id(job_dict, DBT.job_table)
  LOGGER.info(job)
  LOGGER.info(fetch_state)
  #reset_job_state(session, job, fetch_state)
  #result_queue_drain()


def reset_job_state(session, job, fetch_state):
  """Helper function to reset job state during signal interrupt"""
  #also filter pending states eg compiled_pend
  if job and job['state'] in ("compile_start", "compiling", "eval_start",
                              "evaluating"):
    LOGGER.warning('resetting job state to %s', fetch_state)
    if "new" in fetch_state:
      set_job_state(session, job, DBT, 'new', False, "")
    elif "compiled" in fetch_state:
      set_job_state(session, job, DBT, 'compiled', False, "")


def process_fin_builder_results(fin_json, context):
  """Process result from fin_build worker"""
  LOGGER.info('Processing fin_builder result')
  print(context)
  print(context['config']['id'])
  config = get_db_obj_by_id(context['config']['id'], DBT.config_table)
  print(config)
  job = get_db_obj_by_id(context['job']['id'], DBT.job_table)
  kwargs = context['kwargs'].copy()
  pending = []

  failed_job = True
  result_str = ''
  failed_job = False
  with DbSession() as session:
    try:
      set_job_state(session, job, DBT, 'compiled')
      if 'miopen_find_compile_result' in fin_json:
        print('miopen f compile')
        status = process_fdb_w_kernels(session, fin_json,
                                       copy.deepcopy(context), DBT, FDB_ATTR,
                                       SOLVER_ID_MAP, pending)

      elif 'miopen_perf_compile_result' in fin_json:
        print('miopen pdb compile')
        status = process_pdb_compile(session, fin_json, job, config, kwargs,
                                     DBT, FDB_ATTR, SOLVER_ID_MAP)

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
      set_job_state(session, job, DBT, 'errored', False, result=result_str)
    else:
      set_job_state(session, job, DBT, 'compiled', False, result=result_str)

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


def process_fin_evaluator_results():
  """Process result from fin_eval worker"""
  return True


#pylint: disable=too-many-locals
def tune(library, job_batch_size=1000):
  """tuning loop to spin out celery tasks"""

  stop_active_workers()
  if not launch_celery_worker(library):
    return False

  global DBT  #pylint: disable=global-variable-undefined
  global FDB_ATTR  #pylint: disable=global-variable-undefined
  global SOLVER_ID_MAP  #pylint: disable=global-variable-undefined
  global result_queue  #pylint: disable=global-variable-undefined
  global result_queue_lock  #pylint: disable=global-variable-undefined
  global worker_type  #pylint: disable=global-variable-undefined

  DBT = MIOpenDBTables(session_id=library.args.session_id,
                       config_type=library.args.config_type)

  FDB_ATTR = [column.name for column in inspect(DBT.find_db_table).c]
  FDB_ATTR.remove("insert_ts")
  FDB_ATTR.remove("update_ts")

  SOLVER_ID_MAP = get_solver_ids()
  result_queue = mpQueue()
  result_queue_lock = Lock()
  worker_type = library.worker_type

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
                'worker_type': library.worker_type,
                'arch': library.dbt.session.arch,
                'num_cu': library.dbt.session.num_cu,
                'kwargs': kwargs
            }
            #enqueuing to celery queue
            res_set.add(hardware_pick.apply_async((context,), queue="celery"))

      if not job_list:
        if not res_set:
          return False
        LOGGER.info('All tasks added to queue')
        break
      LOGGER.info('TEST')
    except KeyboardInterrupt as err:
      LOGGER.error('%s', err)
      reset_started_jobs(session, job, library.fetch_state)

  LOGGER.info('Started drain process')
  #start draining result_queue in subprocess
  drain_process = Process(target=drain_queue)
  drain_process.start()

  LOGGER.info('Gathering async results in callback function')
  _ = res_set.join(callback=result_callback)

  #terminate result_queue drain process with special queue token (NONE,NONE)
  result_queue.put([None, None])

  drain_process.join()

  return True


def drain_queue():
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
        process_fin_builder_results(fin_json, context)
    except queue.Empty as exc:
      LOGGER.warning(exc)
      LOGGER.info('Sleeping for 2 sec, waiting on results from celery')
      time.sleep(2)

  return True
