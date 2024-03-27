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
  #ignore -to handle queue ImportError in python3
  import Queue as queue  #type: ignore

import logging
import os
from datetime import datetime
import socket
import random
import string
from io import StringIO
from time import sleep
from typing import List, Tuple, Union, Set, Callable, Optional, Any, Dict
from sqlalchemy.exc import IntegrityError, OperationalError, NoInspectionAvailable
from sqlalchemy.inspection import inspect

from tuna.dbBase.sql_alchemy import DbSession
from tuna.machine import Machine

from tuna.abort import chk_abort_file
from tuna.utils.metadata import TUNA_LOG_DIR, NUM_SQL_RETRIES, MAX_JOB_RETRIES, LOG_TIMEOUT
from tuna.tables_interface import DBTablesInterface
from tuna.utils.db_utility import session_retry
from tuna.utils.db_utility import gen_select_objs, gen_update_query, has_attr_set, connect_db
from tuna.connection import Connection
from tuna.utils.utility import SimpleDict
from tuna.utils.logger import set_usr_logger
from tuna.db.tuna_tables import JobMixin


class WorkerInterface(Process):
  """ Interface class extended by Builder and Evaluator. The purpose of this class is to define
  common functionalities. """

  # pylint: disable=too-many-instance-attributes
  # pylint: disable=too-many-public-methods
  # pylint: disable=too-many-statements

  def __init__(self, **kwargs):
    """Constructor"""
    super().__init__()

    allowed_keys: Set[str] = set([
        'machine', 'gpu_id', 'num_procs', 'barred', 'bar_lock', 'envmt',
        'reset_interval', 'job_queue', 'job_queue_lock', 'result_queue',
        'result_queue_lock', 'label', 'fetch_state', 'end_jobs', 'session_id',
        'job', 'config'
    ])

    self.reset_interval: bool = None
    #system vars
    #self.machine: Machine = Machine(local_machine=True)
    self.machine: Machine = None
    #multiprocess vars
    self.gpu_id: int = None
    self.num_procs = None
    self.barred = None
    self.bar_lock = Lock()
    self.job_queue = None
    self.job_queue_lock = Lock()
    self.result_queue = None
    self.result_queue_lock = Lock()
    self.end_jobs = None
    #job detail vars
    self.envmt: List = []
    self.fetch_state = set()
    #self.fetch_state.add('new')
    self.label: str = None
    self.session_id: int = None
    self.worker_type = "generic_worker"
    self.job: SimpleDict = None
    self.config: dict = None

    for key, value in kwargs.items():
      if key in allowed_keys:
        setattr(self, key, value)

    self.logger: logging.Logger

    #initialize tables
    self.set_db_tables()

    self.hostname: str = self.machine.hostname
    #self.claim_num: int = self.num_procs.value * 3
    self.claim_num: int = 1
    self.last_reset: datetime = datetime.now()

    dir_name: str = os.path.join(TUNA_LOG_DIR,
                                 type(self).__name__,
                                 f"{self.hostname}_{self.machine.port}p")
    try:
      if not os.path.exists(dir_name):
        os.makedirs(dir_name)
    except FileExistsError:
      pass

    logger_name: str = os.path.join(dir_name, str(self.gpu_id))
    self.logger = set_usr_logger(logger_name)

    connect_db()

    try:
      self.job_attr: List[str] = [
          column.name for column in inspect(self.dbt.job_table).c
      ]
      self.job_attr.remove("insert_ts")
      self.job_attr.remove("update_ts")
    except NoInspectionAvailable as error:
      self.logger.warning("Ignoring error for init_session: %s", error)

    #call machine.connect and machine.set_logger in run (inside the subprocess)
    #also set cnx here in case WorkerInterface exec_command etc called directly
    self.cnx: Connection = self.machine.connect(chk_abort_file)

  def step(self) -> Optional[Dict[Any, Any]]:  #type: ignore[override]
    """Regular run loop operation, to be overloaded in class specialization """
    raise NotImplementedError("Not implemented")

  def set_db_tables(self):
    """Initialize tables"""
    self.dbt: DBTablesInterface = DBTablesInterface(session_id=self.session_id)

  def reset_machine(self) -> None:
    """Function to reset machhine"""
    self.machine.restart_server()
    self.last_reset = datetime.now()

  #deprecated
  def compose_work_objs(self, session: DbSession,
                        conds: List[str]) -> List[Tuple[SimpleDict, ...]]:
    """Query a job list for update"""
    cond_str = ' AND '.join(conds)
    if cond_str:
      cond_str = f"WHERE {cond_str}"
    cond_str += f" ORDER BY retries,config ASC LIMIT {self.claim_num} FOR UPDATE"
    #try once without waiting for lock
    no_lock = cond_str + " SKIP LOCKED"
    entries = gen_select_objs(session, self.job_attr,
                              self.dbt.job_table.__tablename__, no_lock)
    if not entries:
      entries = gen_select_objs(session, self.job_attr,
                                self.dbt.job_table.__tablename__, cond_str)

    return [(job,) for job in entries]

  #deprecated
  def get_job_objs(self, session: DbSession,
                   find_state: str) -> List[Tuple[SimpleDict, ...]]:
    """Get list of job objects"""
    entries: List[Tuple[SimpleDict, ...]]
    conds: List[str] = [f"session={self.dbt.session.id}", "valid=1"]

    if self.label:
      conds.append(f"reason='{self.label}'")

    conds.append(f"retries<{MAX_JOB_RETRIES}")
    conds.append("state in (" + str(find_state) + ")")

    entries = self.compose_work_objs(session, conds)
    return entries

  #deprecated
  def queue_end_reset(self) -> None:
    """resets end queue flag"""
    with self.bar_lock:
      self.end_jobs.value = 0

  #deprecated
  def check_jobs_found(self, job_rows: List[SimpleDict], find_state: str,
                       imply_end: bool) -> bool:
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

  #deprecated
  def get_job_from_tuple(
      self, job_tuple: Tuple[SimpleDict, ...]) -> Optional[SimpleDict]:
    """find job table in a job tuple"""
    tble: SimpleDict
    if has_attr_set(job_tuple, self.job_attr):
      return job_tuple

    for tble in job_tuple:
      if has_attr_set(tble, self.job_attr):
        return tble
    return None

  #deprecated
  def get_job_tables(
      self, job_rows: List[Tuple[SimpleDict, ...]]) -> List[SimpleDict]:
    """find job tables in query results"""
    #pylint:disable=duplicate-code
    if has_attr_set(job_rows[0], self.job_attr):
      job_tables: List[SimpleDict] = job_rows
    else:
      job_i: int = 0
      tble: SimpleDict
      for i, tble in enumerate(job_rows[0]):
        if has_attr_set(tble, self.job_attr):
          job_i = i
          break
      job_tables = [row[job_i] for row in job_rows]
    return job_tables

  #deprecated
  def job_queue_push(self, job_rows: List[Tuple[SimpleDict, ...]]) -> None:
    """load job_queue with info for job ids"""
    job: SimpleDict
    job_tuple: Tuple[SimpleDict, ...]
    for job_tuple in job_rows:
      self.job_queue.put(job_tuple)
      job = self.get_job_from_tuple(job_tuple)
      self.logger.info("Put job %s %s %s", job.id, job.state, job.reason)

  #deprecated
  def job_queue_pop(self) -> None:
    """load job from top of job queue"""
    self.job = self.job_queue.get(True, 1)[0]
    self.logger.info("Got job %s %s %s", self.job.id, self.job.state,
                     self.job.reason)

  #deprecated
  #pylint: disable=too-many-branches
  def get_job(self, find_state: str, set_state: str, imply_end: bool) -> bool:
    """Interface function to get new job for builder/evaluator"""
    job_rows: List[Tuple[SimpleDict, ...]]
    job_tables: List[SimpleDict]
    job_set_attr: List[str]
    session: DbSession
    ids: list
    row: SimpleDict

    for idx in range(NUM_SQL_RETRIES):
      try:
        with self.job_queue_lock:
          if self.job_queue.empty():
            if imply_end and self.end_jobs.value > 0:
              self.logger.warning('No %s jobs found, skip query', find_state)
              return False

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
                query: str = gen_update_query(job, job_set_attr,
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

  def set_job(self, job: JobMixin):
    """Set worker job"""
    self.job = job
    self.job.gpu_id = self.gpu_id

  #TODO_: This should take a session obj as an input to remove the creation of an extraneous
  # session
  def set_job_state(self,
                    state: str,
                    increment_retries: bool = False,
                    result: Union[str, None] = None) -> None:
    """Interface function to update job state for builder/evaluator"""
    job_set_attr: List[str]

    self.logger.info('Setting job id %s state to %s', self.job.id, state)
    with DbSession() as session:
      job_set_attr = ['state', 'gpu_id']
      self.job.state = state
      if result:
        job_set_attr.append('result')
        self.job.result = result
      if increment_retries:
        job_set_attr.append('retries')
        self.job.retries += 1

      if '_start' in state:
        job_set_attr.append('cache_loc')
        cache: str = '~/.cache/miopen_'
        blurr: str = ''.join(
            random.choice(string.ascii_lowercase) for i in range(10))
        cache_loc: str = cache + blurr
        self.job.cache_loc = cache_loc

      query: str = gen_update_query(self.job, job_set_attr,
                                    self.dbt.job_table.__tablename__)

      def callback() -> bool:
        session.execute(query)
        session.commit()
        return True

      assert session_retry(session, callback, lambda x: x(), self.logger)

  def exec_command(self, cmd: str) -> Tuple[int, str, StringIO]:
    """execute on native machine"""
    ret_code: int
    out: StringIO
    err: StringIO
    strout: str = str()

    ret_code, out, err = self.cnx.exec_command(cmd, timeout=LOG_TIMEOUT)
    if out:
      strout = out.read().strip()
    if (ret_code != 0 or not out) and err:
      self.logger.info('Error executing cmd: %s \n code: %u err: %s', cmd,
                       ret_code, err.read())

    return ret_code, strout, err

  def exec_docker_cmd(self, cmd: str) -> Tuple[int, str, StringIO]:
    """forward command execution to machine method"""
    ret_code: int
    out: StringIO
    err: StringIO
    strout: str = str()

    ret_code, out, err = self.machine.exec_command(cmd, timeout=LOG_TIMEOUT)
    if out:
      strout = out.read().strip()
    if (ret_code != 0 or not out) and err:
      self.logger.info('Error executing cmd: %s \n code: %u err: %s', cmd,
                       ret_code, err.read())

    return ret_code, strout, err

  def get_rocm_v(self) -> str:
    """Interface function to get rocm version info"""
    rocm_ver: str
    _, rocm_ver, _ = self.exec_docker_cmd("cat /opt/rocm/.info/version")
    self.logger.info('Got rocm version: %s', rocm_ver)
    return rocm_ver

  def check_env(self) -> bool:
    """Checking that presumed rocm/miopen_v corresponds to the env rocm/miopen_v"""
    env_rocm_v: str = self.get_rocm_v()
    if self.dbt.session.rocm_v != env_rocm_v:
      raise ValueError(
          f'session rocm_v {self.dbt.session.rocm_v} does not match env rocm_v {env_rocm_v}'
      )
    return True

  def set_barrier(self, funct: Callable, with_timeout: bool) -> bool:
    """Setting time barrier for Process to define execution timeout"""
    if self.barred.value == 0:
      # this is the first proc to reach the barrier
      with self.bar_lock:
        self.barred.value += 1
      self.logger.info('Waiting for other instances to pause')
      wait_cnt: int = 0
      timeout: bool = False
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

  def check_wait_barrier(self) -> bool:
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

  def reset_job_state(self) -> None:
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

  def run(self) -> dict:  #type: ignore
    """
    Main run function of WorkerInterface Process
    #type: ignore[override] - parent class returns None type.
    """

    ret = None
    self.machine.set_logger(self.logger)
    usage: float
    try:
      self.cnx = self.machine.connect(chk_abort_file)

      while True:
        #self.check_wait_barrier()

        if chk_abort_file(self.machine.id, self.logger, self.machine.arch):
          #with self.bar_lock:
          #  self.num_procs.value -= 1
          return None  #type: ignore

        # re-establish node connection
        usage = 0
        try:
          usage = self.machine.getusedspace()
        except (socket.timeout, socket.error):
          usage = 0
        if not usage:
          self.set_barrier(self.reset_machine, True)
          continue
        if usage > 90:
          self.logger.warning('Used space overflow detected')
          self.set_barrier(lambda: (), True)
          continue
        # the step member is defined in the derived class
        ret = self.step()
        self.logger.info("proc %s step %s", self.gpu_id, ret)
        #if not ret:
        #  self.logger.warning('Tuna worker did not return a value...')
        return ret  #type: ignore
        #  return True
        #with self.bar_lock:
        #  self.num_procs.value -= 1
        #return True
    except KeyboardInterrupt as err:
      self.logger.error('%s', err)
      self.reset_job_state()
      #with self.bar_lock:
      #  self.num_procs.value -= 1

    #with self.bar_lock:
    #  self.num_procs.value -= 1

    return ret  #type: ignore

  def run_command(self, cmd: str) -> Tuple[int, str]:
    """Run cmd and return ret_code"""
    ret_code: int
    out: str
    err: StringIO
    for i in range(MAX_JOB_RETRIES):
      ret_code, out, err = self.exec_docker_cmd(cmd)

      if ret_code != 0:
        self.logger.error('Error executing command: %s', ' '.join(cmd))
        if err:
          err_str: str = err.read()
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
    return ret_code, out
