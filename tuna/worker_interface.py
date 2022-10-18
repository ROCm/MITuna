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
from sqlalchemy.exc import IntegrityError, OperationalError  #pylint: disable=wrong-import-order

from tuna.dbBase.sql_alchemy import DbSession
from tuna.abort import chk_abort_file
from tuna.metadata import TUNA_LOG_DIR, TUNA_DOCKER_NAME
from tuna.metadata import NUM_SQL_RETRIES
from tuna.tables import DBTables
from tuna.db_tables import connect_db

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
        'reset_interval', 'job_queue', 'queue_lock', 'label',
        'fetch_state', 'docker_name', 'end_jobs',
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
    self.queue_lock = Lock()
    self.end_jobs = None
    #job detail vars
    self.envmt = []
    self.fetch_state = ['new']
    self.docker_name = TUNA_DOCKER_NAME
    self.label = None
    self.dynamic_solvers_only = False
    self.session_id = None

    self.__dict__.update(
        (key, value) for key, value in kwargs.items() if key in allowed_keys)

    self.set_db_tables()

    #add cache directories
    self.envmt.append(
        f"MIOPEN_USER_DB_PATH=/tmp/miopenpdb/thread-{self.gpu_id}/config/miopen"
    )
    self.envmt.append(
        f"MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopenpdb/thread-{self.gpu_id}/cache")

    self.hostname = self.machine.hostname
    self.job = None
    self.config = None
    self.solver = None
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
    self.dbt = DBTables(session_id=self.session_id)

  def reset_machine(self):
    """Function to reset machhine"""
    self.machine.restart_server()
    self.last_reset = datetime.now()

  def compose_work_query(self, session, job_query):
    """default job description"""
    return job_query

  def compose_job_query(self, find_state, session):
    """Helper function to compose query"""
    query = session.query(self.dbt.job_table)\
                          .filter(self.dbt.job_table.session == self.dbt.session.id)\
                          .filter(self.dbt.job_table.valid == 1)

    if self.label:
      query = query.filter(self.dbt.job_table.reason == self.label)

    query = query.filter(self.dbt.job_table.retries < MAX_JOB_RETRIES)\
      .filter(self.dbt.job_table.state == find_state)

    query = self.compose_work_query(session, query)

    query = query.order_by(self.dbt.job_table.retries.asc()).limit(
        self.claim_num).with_for_update()

    return query

  def queue_end_reset(self):
    """resets end queue flag"""
    with self.bar_lock:
      self.end_jobs.value = 0

  def load_job_queue(self, session, ids):
    """load job_queue with info for job ids"""
    # pylint: disable=comparison-with-callable
    job_cfgs = session.query(self.dbt.job_table, self.dbt.config_table)\
      .filter(self.dbt.job_table.valid == 1)\
      .filter(self.dbt.job_table.session == self.dbt.session.id)\
      .filter(self.dbt.config_table.id == self.dbt.job_table.config)\
      .filter(self.dbt.job_table.id.in_(ids)).all()
    # pylint: enable=comparison-with-callable

    if len(ids) != len(job_cfgs):
      raise Exception(
          f'Failed to load job queue. #ids: {len(ids)} - #job_cgfs: {len(job_cfgs)}'
      )
    for job, config in job_cfgs:
      if job.solver:
        query = session.query(self.dbt.solver_table)\
            .filter(self.dbt.solver_table.solver == job.solver)
        solver = query.one()
      else:
        query = session.query(self.dbt.solver_app, self.dbt.solver_table)

        # pylint: disable=comparison-with-callable
        query = query.filter(self.dbt.solver_app.session == self.dbt.session.id)\
                     .filter(self.dbt.solver_app.applicable == 1)\
                     .filter(self.dbt.solver_table.tunable == 1)\
                     .filter(self.dbt.solver_app.config == job.config)\
                     .filter(self.dbt.solver_app.solver == self.dbt.solver_table.id)\
                     .filter(self.dbt.solver_table.tunable == 1)
        # pylint: enable=comparison-with-callable

        app_solver_desc = query.all()
        ids = [solver.id for _, solver in app_solver_desc]

        solver = self.dbt.solver_table()
        if ids:
          solver.tunable = 1
        else:
          self.logger.warning(
              "No applicable & tunable solvers found: id %s, solver %s, config %s",
              job.id, job.solver, job.config)
          solver.tunable = 0

      self.job_queue.put((job, config, solver))
      self.logger.info("Put job %s %s %s", job.id, job.state, job.reason)

  def check_jobs_found(job_cfgs, find_state, imply_end):
    """check for end of jobs"""
    if not job_cfgs:
      # we are done
      self.logger.warning(
          'No %s jobs found, session %s', find_state,
          self.session_id)
      if imply_end:
        self.logger.warning("set end")
        self.end_jobs.value = 1
      return False
    return True

  def get_job_ids(self, job_rows):
    """find job table in query results and return ids"""
    for tble in job_rows:
      if type(tble) == list):
        if type(tble[0]) == type(self.dbt.job_table)
          ids = tuple((str(job.id) for job in tble))
          return ids;
      elif type(tble) == type(self.dbt.job_table)
        ids = tuple((str(job.id) for job in job_rows))
        return ids;

    ids = []
    return ids

  #pylint: disable=too-many-branches
  def get_job(self, find_state, set_state, imply_end):
    """Interface function to get new job for builder/evaluator"""
    for idx in range(NUM_SQL_RETRIES):
      try:
        with self.queue_lock:
          if imply_end and self.end_jobs.value > 0:
            self.logger.warning('No %s jobs found, skip query', find_state)
            return False
          if self.job_queue.empty():
            ids = ()
            with DbSession() as session:
              query = self.compose_job_query(find_state, session)
              job_rows = query.all()

              if not self.check_jobs_found(job_rows, find_state, imply_end):
                return False

              ids = self.get_job_ids(job_rows)
              self.logger.info("%s jobs %s", find_state, ids)
              if set_state == "eval_start":
                session.query(self.dbt.job_table).filter(
                    self.dbt.job_table.id.in_(ids)).update(
                        {
                            self.dbt.job_table.state: set_state,
                            self.dbt.job_table.eval_mid: self.machine.id,
                            self.dbt.job_table.gpu_id: self.gpu_id
                        },
                        synchronize_session='fetch')
              else:
                #note for a compile job gpu_id is an index 0 tuna process number, not a gpu
                session.query(self.dbt.job_table).filter(
                    self.dbt.job_table.id.in_(ids)).update(
                        {
                            self.dbt.job_table.state: set_state,
                            self.dbt.job_table.machine_id: self.machine.id,
                            self.dbt.job_table.gpu_id: self.gpu_id
                        },
                        synchronize_session='fetch')
              session.commit()

              self.load_job_queue(session, ids)

          #also in queue_lock
          self.job, self.config, self.solver = self.job_queue.get(True, 1)
          self.logger.info("Got job %s %s %s", self.job.id, self.job.state,
                           self.job.reason)

        return True
      except OperationalError as error:
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
  def set_job_state(self, state, increment_retries=False, result=''):
    """Interface function to update job state for builder/evaluator"""
    self.logger.info('Setting job id %s state to %s', self.job.id, state)
    for idx in range(NUM_SQL_RETRIES):
      with DbSession() as session:
        try:
          if state in ["running", "compiling", "evaluating"]:
            session.query(self.dbt.job_table).filter(
                self.dbt.job_table.id == self.job.id).update({
                    self.dbt.job_table.state: state,
                    self.dbt.job_table.result: result
                })
          else:
            if increment_retries:
              session.query(self.dbt.job_table).filter(
                  self.dbt.job_table.id == self.job.id).update({
                      self.dbt.job_table.state:
                          state,
                      self.dbt.job_table.retries:
                          self.dbt.job_table.retries + 1,
                      self.dbt.job_table.result:
                          result
                  })
            else:
              # JD: When would this happen ?
              # also this is a side-effect, not cool
              cache = '~/.cache/miopen_'
              blurr = ''.join(
                  random.choice(string.ascii_lowercase) for i in range(10))
              cache_loc = cache + blurr
              session.query(self.dbt.job_table).filter(
                  self.dbt.job_table.id == self.job.id).update({
                      self.dbt.job_table.state: state,
                      self.dbt.job_table.cache_loc: cache_loc,
                      self.dbt.job_table.result: result
                  })
          session.commit()
          return True
        except OperationalError as error:
          self.logger.warning('%s, Db contention, attempt %s, sleeping ...',
                              error, idx)
          sleep(random.randint(1, 30))
        except IntegrityError as error:
          session.rollback()
          self.logger.warning(
              'Attempt to update job state (job_id = %s) failed', self.job.id)
          self.logger.warning(error)
          return False

    self.logger.error(
        '%s retries exhausted to update job status (host = %s, worker = %s), exiting ... ',
        NUM_SQL_RETRIES, self.hostname, self.gpu_id)
    return False

  def exec_command(self, cmd):
    """execute on native machine"""
    ret_code, out, err = self.cnx.exec_command(cmd, timeout=LOG_TIMEOUT)
    if err is not None and hasattr(err, 'channel'):
      self.logger.info(err)
      err.channel.settimeout(LOG_TIMEOUT)
    return ret_code, out, err

  def exec_docker_cmd(self, cmd):
    """forward command execution to machine method"""
    ret_code, out, err = self.machine.exec_command(cmd,
                                                   docker_name=self.docker_name,
                                                   timeout=LOG_TIMEOUT)
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
          f'session rocm_v {self.dbt.session.rocm_v} does not match env rocm_v {env_rocm_v}'
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
    if self.job and self.job.state != 'compiled' and self.job.state != 'evaluated':
      self.logger.warning('resetting job state to %s', self.fetch_state[0])
      if "new" in self.fetch_state:
        self.set_job_state("new")
      elif "compiled" in self.fetch_state:
        self.set_job_state("compiled")

    while not self.job_queue.empty():
      try:
        self.job, self.config, self.solver = self.job_queue.get(True, 1)
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
          return True
    except KeyboardInterrupt as err:
      self.logger.error('%s', err)
      self.reset_job_state()
      return False

    return True
