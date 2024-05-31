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
import copy
import random
import string
import asyncio
import threading
from datetime import timedelta
from multiprocessing import Queue as mpQueue, Process, Value
import json
from sqlalchemy.exc import OperationalError, DataError, IntegrityError
from sqlalchemy.inspection import inspect
import kombu
import aioredis

from tuna.utils.logger import setup_logger
from tuna.utils.utility import serialize_chunk, SimpleDict
from tuna.utils.db_utility import session_retry
from tuna.utils.db_utility import gen_update_query
from tuna.machine import Machine
from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.miopen_utility import load_machines
from tuna.miopen.utils.json_to_sql import process_fdb_w_kernels, process_pdb_compile
from tuna.miopen.utils.json_to_sql import clean_cache_table, get_worker_type
from tuna.miopen.db.tables import MIOpenDBTables
from tuna.miopen.worker.fin_utils import get_fin_result
from tuna.miopen.db.solver import get_solver_ids
from tuna.celery_app.celery_workers import launch_celery_worker
from tuna.miopen.celery_tuning.celery_tasks import celery_enqueue
from tuna.celery_app.celery_app import stop_active_workers, purge_queue, app
from tuna.celery_app.celery_app import TUNA_CELERY_BROKER, TUNA_REDIS_PORT

LOGGER: logging.Logger = setup_logger('tuning')
MAX_ERRORED_JOB_RETRIES = 3
result_queue = mpQueue()
job_counter_lock = threading.Lock()


def process_fin_builder_results(session, fin_json, context, dbt):
  """Process result from fin_build worker"""
  LOGGER.info('Processing fin_builder result')
  job = SimpleDict(**context['job'])
  pending = []
  solver_id_map = get_solver_ids()

  failed_job = False
  result_str = ''
  status = None
  try:
    if fin_json:
      if 'miopen_find_compile_result' in fin_json:
        status = process_fdb_w_kernels(session, fin_json,
                                       copy.deepcopy(context), dbt,
                                       context['fdb_attr'], pending)

      elif 'miopen_perf_compile_result' in fin_json:
        status = process_pdb_compile(session, fin_json, job, dbt, solver_id_map)

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


def process_fin_evaluator_results(session, fin_json, context, dbt):
  """Process fin_json result"""
  LOGGER.info('Processing fin_eval result')
  job = SimpleDict(**context['job'])
  failed_job = True
  result_str = ''
  pending = []
  orig_state = 'compiled'

  try:
    if fin_json:
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
      if job.retries >= (MAX_ERRORED_JOB_RETRIES - 1):  #pylint: disable=no-member
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
    set_job_state(session, job, dbt, 'errored', result=result_str)
    #failed_job = True

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


def get_worker_granularity(library):
  """Check how many celery workers we need"""
  worker_granularity = None
  worker_granularity = get_worker_type(library.args)
  if 'miopen_find_compile' in library.args.fin_steps \
  or 'miopen_perf_compile' in library.args.fin_steps:
    worker_granularity = 'worker_per_node'
  elif 'miopen_find_eval' in library.args.fin_steps or 'miopen_perf_eval' in library.args.fin_steps:
    worker_granularity = 'worker_per_gpu'

  return worker_granularity


def get_q_name(library):
  """Compose queue name"""
  worker_type = get_worker_type(library.args)
  q_name = None
  if worker_type == 'fin_build_worker':
    q_name = f"compile_q_session_{library.dbt.session_id}"
  else:
    q_name = f"eval_q_session_{library.dbt.session_id}"

  return q_name


def prep_tuning(library):
  """Prep env for tuning start"""
  worker_type = get_worker_type(library.args)
  machines = load_machines(library.args)
  q_name = get_q_name(library)
  purge_queue([q_name])
  cmd = None
  subp_list = []
  if worker_type == 'fin_build_worker':
    cmd = f"celery -A tuna.celery_app.celery_app worker -l info -E -n tuna_HOSTNAME_sess_{library.args.session_id} -Q {q_name}"  #pylint: disable=line-too-long
  else:
    cmd = f"celery -A tuna.celery_app.celery_app worker -l info -E -c 1 -n tuna_HOSTNAME_sess_{library.args.session_id}_gpu_id_GPUID -Q {q_name}"  #pylint: disable=line-too-long

  if not library.args.enqueue_only:
    try:
      subp_list = launch_celery_worker(machines,
                                       get_worker_granularity(library), cmd,
                                       True)
      if not subp_list:
        raise ValueError('Could not launch celery worker')
      #LOGGER.info('Launched supbproc pids: (%s)', ', '.join([str(subp.pid) for subp in subp_list]))
    except kombu.exceptions.OperationalError as k_err:
      LOGGER.error('Redis error ocurred: %s', k_err)
      return False

  global DBT  #pylint: disable=global-variable-undefined
  DBT = MIOpenDBTables(session_id=library.args.session_id,
                       config_type=library.args.config_type)

  fdb_attr = [column.name for column in inspect(DBT.find_db_table).c]
  fdb_attr.remove("insert_ts")
  fdb_attr.remove("update_ts")

  f_vals = library.get_f_vals(Machine(local_machine=True),
                              range(0),
                              tuning=True)
  kwargs = library.get_kwargs(0, f_vals, tuning=True)

  return worker_type, kwargs, fdb_attr, q_name, subp_list


#pylint: disable=too-many-locals
def tune(library, job_batch_size=1000):
  """tuning loop to spin out celery tasks"""

  if library.args.shutdown_workers:
    LOGGER.info('Shutting down all celery workers')
    stop_active_workers()
    return True

  try:
    LOGGER.info('Launching celery workers')
    worker_type, kwargs, fdb_attr, q_name, subp_list = prep_tuning(library)
    LOGGER.info('Done launching celery workers')
  except ValueError as verr:
    LOGGER.error(verr)
    return False

  try:
    #if enqueue_only is False, we only launch the workers
    if not library.args.enqueue_only:
      for subp in subp_list:
        subp.wait()
      return True
  except KeyboardInterrupt:
    for subp in subp_list:
      subp.kill()
    return False

  #res_set = ResultSet([])
  start = time.time()
  worker_type = get_worker_type(library.args)

  db_name = os.environ['TUNA_DB_NAME']
  prefix = f"d_{db_name}_sess_{library.args.session_id}"
  app.conf.get('result_backend_transport_options',
               {}).update({"global_keyprefix": prefix})
  with DbSession() as session:
    job_list = library.get_jobs(session,
                                library.fetch_state,
                                library.set_state,
                                library.args.session_id,
                                no_update=True)
  job_counter = Value('i', len(job_list))
  LOGGER.info('Job counter: %s', job_counter.value)
  if job_counter.value == 0:
    LOGGER.info('No new jobs found')
    return False

  try:
    enqueue_proc = Process(
        target=enqueue_jobs,
        args=[library, job_batch_size, worker_type, kwargs, fdb_attr, q_name])
    #Start enqueue proc
    enqueue_proc.start()
    #start async consume thread, blocking
    asyncio.run(consume(job_counter, worker_type, DBT))
    enqueue_proc.join()

  except (KeyboardInterrupt, Exception):  #pylint: disable=broad-exception-caught
    LOGGER.error('Keyboard interrupt caught, draining results queue')
    purge_queue([q_name])
    library.cancel_consumer(q_name)
    reset_job_state(library.args.session_id, worker_type, DBT)

  library.cancel_consumer(q_name)
  end = time.time()
  LOGGER.info("Took {:0>8} to tune".format(str(timedelta(seconds=end - start))))  #pylint: disable=consider-using-f-string

  return True


def reset_job_state(sess_id, worker_type, dbt):
  """Resetting job state for jobs in flight"""
  temp_obj = SimpleDict()
  temp_obj.id = sess_id  #pylint: disable=invalid-name
  attribs = ['state']
  temp_obj.state = 1
  state = None

  LOGGER.info('Resetting job state in DB for in flight jobs')

  if worker_type == 'fin_build_worker':
    state = 'compile_start'
  elif worker_type == 'fin_eval_worker':
    state = 'eval_start'

  query = gen_update_query(temp_obj,
                           attribs,
                           dbt.job_table.__tablename__,
                           state=state)
  with DbSession() as session:

    def callback() -> bool:
      session.execute(query)
      session.commit()
      return True

    assert session_retry(session, callback, lambda x: x(), LOGGER)
    return True

  return False


def enqueue_jobs(library, job_batch_size, worker_type, kwargs, fdb_attr,
                 q_name):
  """Enqueue celery jobs"""
  with DbSession() as session:
    while True:
      job_list = []
      #get all the jobs from mySQL
      job_list = library.get_jobs(session, library.fetch_state,
                                  library.set_state, library.args.session_id,
                                  job_batch_size)

      for i in range(0, len(job_list), job_batch_size):
        batch_jobs = job_list[i:min(i + job_batch_size, len(job_list))]
        entries = library.compose_work_objs_fin(session, batch_jobs,
                                                library.dbt)
        serialized_jobs = serialize_chunk(entries)
        #build context for each celery task
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

          #calling celery task, enqueuing to celery queue
          celery_enqueue.apply_async((context,), queue=q_name, reply_to=q_name)

      if not job_list:
        LOGGER.info('All tasks added to queue')
        break


async def consume(job_counter, worker_type, dbt):
  """Retrieve celery results from redis db"""
  redis = await aioredis.from_url(
      f"redis://{TUNA_CELERY_BROKER}:{TUNA_REDIS_PORT}/15")
  LOGGER.info('Connected to redis')
  while job_counter.value > 0:
    cursor = "0"
    keys = []
    while cursor != 0:
      cursor, results = await redis.scan(cursor, match='*'
                                        )  # update with the celery pattern
      keys.extend(results)
    LOGGER.info('Found %s results', len(results))
    for key in keys:
      try:
        data = await redis.get(key)
        if data:
          await parse_result(data.decode('utf-8'), worker_type, dbt)
          await redis.delete(key)
          with job_counter_lock:
            job_counter.value = job_counter.value - 1
      except aioredis.exceptions.ResponseError as red_err:
        LOGGER.error(red_err)
        LOGGER.info(key.decode('utf-8'))

    LOGGER.info('Processed results')
    await asyncio.sleep(1)
  LOGGER.info('Job counter reached 0')
  await redis.close()


async def parse_result(data, worker_type, dbt):
  """Function callback for celery async jobs to store results"""
  data = json.loads(data)
  LOGGER.info(data)

  with DbSession() as session:
    fin_json = data['result']['ret']
    context = data['result']['context']
    LOGGER.info('Parsing: %s', fin_json)
    LOGGER.info('Parsing context: %s', context)
    if worker_type == 'fin_build_worker':
      process_fin_builder_results(session, fin_json, context, dbt)
    elif worker_type == 'fin_eval_worker':
      process_fin_evaluator_results(session, fin_json, context, dbt)
    else:
      raise ValueError('Unsupported worker_type')
