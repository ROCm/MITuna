#!/usr/bin/env python3
###############################################################################
#
# MIT License
#
# Copyright (c) 2022 Advanced Micro Devices, Inc.
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
"""Module that represents the WorkerInterface class interface"""
from multiprocessing import Process, Lock
try:
  import queue
except ImportError:
  import Queue as queue
import logging
import os
from datetime import datetime
import socket
import random
import string
from time import sleep
from sqlalchemy.exc import IntegrityError, OperationalError, NoInspectionAvailable
from sqlalchemy.inspection import inspect

from tuna.dbBase.sql_alchemy import DbSession
from tuna.abort import chk_abort_file
from tuna.miopen.utils.metadata import TUNA_LOG_DIR
from tuna.miopen.utils.metadata import NUM_SQL_RETRIES
from tuna.tables_interface import DBTablesInterface
from tuna.utils.db_utility import session_retry
from tuna.utils.db_utility import gen_select_objs, gen_update_query, has_attr_set
from tuna.utils.db_utility import connect_db
from tuna.utils.utility import SimpleDict

MAX_JOB_RETRIES = 10
LOG_TIMEOUT = 10 * 60.0  # in seconds


class WorkerInterface(Process):
  """ Interface class extended by Builder and Evaluator. The purpose of this class is to define
  common functionalities. """

  # pylint: disable=too-many-instance-attributes
  # pylint: disable=too-many-public-methods
  # pylint: disable=too-many-statements

  def __init__(self, **kwargs):
    """Constructor"""
    super().__init__()

    allowed_keys = set([
        'machine', 'gpu_id', 'num_procs', 'barred', 'bar_lock', 'envmt',
        'reset_interval', 'job_queue', 'job_queue_lock', 'result_queue',
        'result_queue_lock', 'label', 'fetch_state', 'end_jobs',
        'dynamic_solvers_only', 'session_id'
    ])
    self.__dict__.update((key, None) for key in allowed_keys)

    #system vars
    self.machine = None
    #multiprocess vars
    self.gpu_id = None
    self.num_procs = None
    self.barred = None
    self.bar_lock = Lock()
    self.job_queue = None
    self.job_queue_lock = Lock()
    self.result_queue = None
    self.result_queue_lock = Lock()
    self.end_jobs = None
    #job detail vars
    self.envmt = []
    self.fetch_state = ['new']
    self.label = None
    self.dynamic_solvers_only = False
    self.session_id = None

    self.__dict__.update(
        (key, value) for key, value in kwargs.items() if key in allowed_keys)

    #initialize tables
    self.set_db_tables()

    self.hostname = self.machine.hostname
    self.claim_num = self.num_procs.value
    self.last_reset = datetime.now()

    dir_name = os.path.join(TUNA_LOG_DIR,
                            type(self).__name__,
                            f"{self.hostname}_{self.machine.port}p")
    if not os.path.exists(dir_name):
      os.makedirs(dir_name)
    logger_name = os.path.join(dir_name, str(self.gpu_id))
    self.set_logger(logger_name)
    connect_db()

    self.job = SimpleDict()
    try:
      self.job_attr = [column.name for column in inspect(self.dbt.job_table).c]
      self.job_attr.remove("insert_ts")
      self.job_attr.remove("update_ts")
    except NoInspectionAvailable as error:
      self.logger.warning("Ignoring error for init_session: %s", error)

    #call machine.connect and machine.set_logger in run (inside the subprocess)
    #also set cnx here in case WorkerInterface exec_command etc called directly
    self.cnx = self.machine.connect(chk_abort_file)

  def set_logger(self, logger_name):
    """Build logger with given name"""
    # JD: This needs to be moved to logger.py
    log_level = os.environ.get('TUNA_LOGLEVEL', None)
    lgr = logging.getLogger(logger_name)
    log_file = os.path.join(TUNA_LOG_DIR, logger_name + ".log")
    fmt = logging.Formatter(
        '%(lineno)d - %(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setFormatter(fmt)
    file_handler.setLevel(log_level.upper() if log_level else logging.INFO)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    stream_handler.setLevel(logging.INFO)
    lgr.addHandler(file_handler)
    lgr.addHandler(stream_handler)
    lgr.setLevel(log_level.upper() if log_level else logging.DEBUG)
    self.logger = lgr

  def set_db_tables(self):
    """Initialize tables"""
    self.dbt = DBTablesInterface(session_id=self.session_id)

  def reset_machine(self):
    """Function to reset machhine"""
    self.machine.restart_server()
    self.last_reset = datetime.now()

  def compose_work_objs(self, session, conds):
    """default job description"""
    cond_str = ' AND '.join(conds)
    if cond_str:
      cond_str = f"WHERE {cond_str}"
    cond_str += f" ORDER BY retries ASC LIMIT {self.claim_num} FOR UPDATE"
    entries = gen_select_objs(session, self.job_attr,
                              self.dbt.job_table.__tablename__, cond_str)

    return entries

  def get_job_objs(self, session, find_state):
    """Helper function to compose query"""
    conds = [f"session={self.dbt.session.id}", "valid=1"]

    if self.label:
      conds.append(f"reason='{self.label}'")

    conds.append(f"retries<{MAX_JOB_RETRIES}")
    conds.append(f"state='{find_state}'")

    entries = self.compose_work_objs(session, conds)

    return entries

  def queue_end_reset(self):
    """resets end queue flag"""
    with self.bar_lock:
      self.end_jobs.value = 0

  def check_jobs_found(self, job_rows, find_state, imply_end):
    """check for end of jobs"""
    if not job_rows:
      # we are done
      self.logger.warning('No %s jobs found, session %s', find_state,
                          self.session_id)
      if imply_end:
        self.logger.warning("set end")
        self.end_jobs.value = 1
      return False
    return True

  def get_job_from_tuple(self, job_tuple):
    """find job table in a job tuple"""
    if has_attr_set(job_tuple, self.job_attr):
      return job_tuple

    for tble in job_tuple:
      if has_attr_set(tble, self.job_attr):
        return tble

    return None

  def get_job_tables(self, job_rows):
    """find job tables in query results"""
    if has_attr_set(job_rows[0], self.job_attr):
      job_tables = job_rows
    else:
      job_i = 0
      for i, tble in enumerate(job_rows[0]):
        if has_attr_set(tble, self.job_attr):
          job_i = i
          break
      job_tables = [row[job_i] for row in job_rows]

    return job_tables

  def refresh_query_objects(self, session, rows):
    """refresh objects in query rows"""
    for obj_tuple in rows:
      try:
        for entry in obj_tuple:
          session.refresh(entry)
      except TypeError:
        session.refresh(obj_tuple)

  def job_queue_push(self, job_rows):
    """load job_queue with info for job ids"""
    for job_tuple in job_rows:
      self.job_queue.put(job_tuple)
      job = self.get_job_from_tuple(job_tuple)
      self.logger.info("Put job %s %s %s", job.id, job.state, job.reason)

  def job_queue_pop(self):
    """load job from top of job queue"""
    self.job = self.job_queue.get(True, 1)
    self.logger.info("Got job %s %s %s", self.job.id, self.job.state,
                     self.job.reason)

  #pylint: disable=too-many-branches
  def get_job(self, find_state, set_state, imply_end):
    """Interface function to get new job for builder/evaluator"""
    for idx in range(NUM_SQL_RETRIES):
      try:
        with self.job_queue_lock:
          if imply_end and self.end_jobs.value > 0:
            self.logger.warning('No %s jobs found, skip query', find_state)
            return False
          if self.job_queue.empty():
            with DbSession() as session:
              job_rows = self.get_job_objs(session, find_state)

              if not self.check_jobs_found(job_rows, find_state, imply_end):
                return False

              job_tables = self.get_job_tables(job_rows)
              ids = [row.id for row in job_tables]
              self.logger.info("%s jobs %s", find_state, ids)
              for job in job_tables:
                job.state = set_state

                job_set_attr = ['state']
                query = gen_update_query(job, job_set_attr,
                                         self.dbt.job_table.__tablename__)
                session.execute(query)

              session.commit()
              self.job_queue_push(job_rows)

          #also in job_queue_lock
          self.job_queue_pop()

          #note for a compile job gpu_id is an index 0 tuna process number, not a gpu
          self.job.gpu_id = self.gpu_id

        return True
      except OperationalError as error:
        session.rollback()
        self.logger.warning('%s, Db contention, sleeping ...', error)
        sleep(random.randint(1, 30))
      except IntegrityError as error:
        session.rollback()
        self.logger.warning(
            'Attempt %s to update job (host = %s, worker = %s) failed (%s), retrying ... ',
            idx, self.hostname, self.gpu_id, error)
        sleep(5)
      except queue.Empty:
        self.logger.warning('Shared job queue empty, retrying ... ')

    self.logger.error(
        '%s retries exhausted to update job status (host = %s, worker = %s), exiting ... ',
        NUM_SQL_RETRIES, self.hostname, self.gpu_id)
    return False

  # JD: This should take a session obj as an input to remove the creation of an extraneous session
  def set_job_state(self, state, increment_retries=False, result=None):
    """Interface function to update job state for builder/evaluator"""
    self.logger.info('Setting job id %s state to %s', self.job.id, state)
    with DbSession() as session:
      self.job.state = state
      if result:
        self.job.result = result
      if increment_retries:
        self.job.retries += 1

      if '_start' in state:
        cache = '~/.cache/miopen_'
        blurr = ''.join(
            random.choice(string.ascii_lowercase) for i in range(10))
        cache_loc = cache + blurr
        self.job.cache_loc = cache_loc

      job_set_attr = ['state', 'result', 'retries', 'cache_loc', 'gpu_id']
      query = gen_update_query(self.job, job_set_attr,
                                self.dbt.job_table.__tablename__)

      def callback():
        session.execute(query)
        session.commit()
        return True

      return session_retry(session, callback,
                    lambda x: x(), self.logger)


  def exec_command(self, cmd):
    """execute on native machine"""
    ret_code, out, err = self.cnx.exec_command(cmd, timeout=LOG_TIMEOUT)
    if err is not None and hasattr(err, 'channel'):
      self.logger.info(err)
      err.channel.settimeout(LOG_TIMEOUT)
    return ret_code, out, err

  def exec_docker_cmd(self, cmd):
    """forward command execution to machine method"""
    ret_code, out, err = self.machine.exec_command(cmd, timeout=LOG_TIMEOUT)
    if out:
      out = out.read().strip()
    if not out and err:
      self.logger.info('Error executing docker cmd: %s \n err: %s', cmd,
                       err.read())

    if err is not None and hasattr(err, 'channel'):
      err.channel.settimeout(LOG_TIMEOUT)
      self.logger.info(err)
    return ret_code, out, err

  def get_miopen_v(self):
    """Interface function to get new branch hash"""
    _, out, _ = self.exec_docker_cmd(
        "cat /opt/rocm/miopen/include/miopen/version.h "
        "| grep MIOPEN_VERSION_TWEAK | cut -d ' ' -f 3")
    self.logger.info('Got branch commit hash: %s', out)
    return out

  def get_rocm_v(self):
    """Interface function to get rocm version info"""
    _, out, _ = self.exec_docker_cmd("cat /opt/rocm/.info/version")
    self.logger.info('Got rocm version: %s', out)
    return out

  def check_env(self):
    """Checking that presumed rocm/miopen_v corresponds to the env rocm/miopen_v"""
    env_rocm_v = self.get_rocm_v()
    if self.dbt.session.rocm_v != env_rocm_v:
      raise ValueError(
          f'session rocm_v {self.dbt.session.rocm_v} does not match env rocm_v {env_rocm_v}'
      )
    env_miopen_v = self.get_miopen_v()
    if self.dbt.session.miopen_v != env_miopen_v:
      raise ValueError(
          f'session miopen_v {self.dbt.session.miopen_v} does not match env miopen_v {env_miopen_v}'
      )

    return True

  def set_barrier(self, funct, with_timeout):
    """Setting time barrier for Process to define execution timeout"""
    if self.barred.value == 0:
      # this is the first proc to reach the barrier
      with self.bar_lock:
        self.barred.value += 1
      self.logger.info('Waiting for other instances to pause')
      wait_cnt = 0
      timeout = False
      while self.barred.value < self.num_procs.value:
        sleep(10)
        if with_timeout and self.barred.value == 1:
          wait_cnt += 1
          timeout = True
          if wait_cnt > 180:
            break
      if timeout:
        self.logger.warning(
            'Timed out waiting for hung process, proceeding ... ')
      else:
        self.logger.info('Finished waiting for instances to pause')
      funct()
      with self.bar_lock:
        self.barred.value = 0
      return True

    return False

  def check_wait_barrier(self):
    """Checking time barrier"""
    self.logger.info('Checking barrier')
    if self.barred.value != 0:
      self.logger.info('Blocked procs found')
      self.logger.info('Current barrier count: %s', self.barred.value)
      with self.bar_lock:
        self.barred.value += 1
      self.logger.warning('Waiting for processes to finish')
      while self.barred.value != 0:
        sleep(60)
      self.logger.warning('Finished waiting for processes')
      return True
    return False

  def reset_job_state(self):
    """Helper function to reset job state during signal interrupt"""
    #also filter pending states eg compiled_pend
    if self.job and self.job.state in ("compile_start", "compiling",
                                       "eval_start", "evaluating"):
      self.logger.warning('resetting job state to %s', self.fetch_state[0])
      if "new" in self.fetch_state:
        self.set_job_state("new")
      elif "compiled" in self.fetch_state:
        self.set_job_state("compiled")

    while not self.job_queue.empty():
      try:
        self.job_queue_pop()
        if "new" in self.fetch_state:
          self.set_job_state("new")
        elif "compiled" in self.fetch_state:
          self.set_job_state("compiled")

      except queue.Empty:
        break

  def run(self):
    """Main run function of WorkerInterface Process"""

    self.machine.set_logger(self.logger)
    try:
      self.cnx = self.machine.connect(chk_abort_file)

      while True:
        self.check_wait_barrier()

        if chk_abort_file(self.machine.id, self.logger, self.machine.arch):
          with self.bar_lock:
            self.num_procs.value -= 1
          return False

        # re-establish node connection
        usage = None
        try:
          usage = self.machine.getusedspace()
        except (socket.timeout, socket.error):
          usage = None
        if not usage:
          self.set_barrier(self.reset_machine, True)
          continue
        if usage > 90:
          # JD: Tell prometheus I am out of disk space
          self.logger.warning('Used space overflow detected')
          self.set_barrier(lambda: (), True)
          continue
        # the step member is defined in the derived class
        ret = self.step()  # pylint: disable=no-member
        self.logger.info("proc %s step %s", self.gpu_id, ret)
        if not ret:
          self.logger.warning('No more steps, quiting...')
          with self.bar_lock:
            self.num_procs.value -= 1
          return True
    except KeyboardInterrupt as err:
      self.logger.error('%s', err)
      self.reset_job_state()
      with self.bar_lock:
        self.num_procs.value -= 1
      return False

    with self.bar_lock:
      self.num_procs.value -= 1

    return True

  def run_command(self, cmd):
    """Run cmd and return ret_code"""
    for i in range(MAX_JOB_RETRIES):
      ret_code, out, err = self.exec_docker_cmd(cmd)

      if ret_code != 0:
        self.logger.error('Error executing command: %s', ' '.join(cmd))
        if err:
          err_str = err.read()
          self.logger.error('%s : %s', ret_code, err_str)
          if "disk I/O error" in err_str:
            self.logger.error('fin retry : %u', i)
            sleep(random.randint(1, 10))
          else:
            break
        else:
          self.logger.error('err code : %s', ret_code)
          break
      else:
        break

    if ret_code != 0:
      ret_code = None

    return ret_code, out
