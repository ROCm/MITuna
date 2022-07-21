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
"""Evaluator class implements the worker interface. The purpose of this class
is to run MIOpenDriver commands in benchmarking mode"""
import os
from datetime import datetime
from time import sleep
import ftplib
from sqlalchemy.exc import OperationalError

from tuna.worker_interface import WorkerInterface
from tuna.dbBase.sql_alchemy import DbSession
from tuna.metadata import (KCACHE_DIR, TUNA_LOG_DIR, MIOPEN_USER_DB_PATH,
                           SQLITE_CONFIG_COLS, CMD_TO_PREC, MIOPEN_DB_VERSION)
from tuna.analyze_parse_db import mysql_to_sqlite_cfg
from tuna.helper import valid_cfg_dims
from tuna.import_db import record_perfdb
from tuna.utils.utility import DotDict

FDB_NUM_RUNS = 100
APPLICABLE_NUM_PROCS = 40

LOG_TIMEOUT = 10 * 60.0  # in seconds


class Evaluator(WorkerInterface):
  """ The Evaluator class implements the worker class. Its purpose is to run benchmarking jobs
  and when completed sets the state of the job to evaluated. """

  #pylint: disable=no-member
  # pylint: disable=too-many-instance-attributes

  def __init__(self, **kwargs):
    self.find_db = None
    self.poll_retries = 0
    self.fetch_state = ['compiled', 'new']
    self.last_fetch_state = 'new'
    super().__init__(**kwargs)

    self.envmt.append("MIOPEN_USER_DB_PATH={}".format(MIOPEN_USER_DB_PATH))

    dir_name = os.path.join(
        TUNA_LOG_DIR, 'evaluator', self.machine.arch,
        "{}cu_{}_{}p".format(self.machine.num_cu, self.hostname,
                             self.machine.port))
    if not os.path.exists(dir_name):
      os.makedirs(dir_name)
    logger_name = os.path.join(dir_name, str(self.gpu_id))
    self.set_logger(logger_name)

  def get_job(self, find_state, set_state, imply_end):
    """Polling to see if job available"""
    found = False
    for start_state in self.fetch_state:
      self.logger.info('find job: %s', start_state)
      if super().get_job(start_state, 'eval_start', True):
        found = True
        self.last_fetch_state = start_state
        break

    if not found:
      compile_jobs_left = self.get_compile_jobs()
      if compile_jobs_left == 0:
        self.logger.warning('No jobs for evaluator, quiting .. ')
        with self.bar_lock:
          self.num_procs.value -= 1
        self.poll_retries = 0
      else:
        with self.queue_lock:
          self.end_jobs.value = 0
        self.logger.info('Waiting on jobs to compile: %s', compile_jobs_left)
        sleep(30)
        #keep trying
        self.poll_retries = 1

    return found

  def handle_errors_or_complete(self, error_bad_param, status, timeout,
                                error_cfg, abort_cfg, job_solver):
    """Function to update job state"""
    success = True
    if not self.machine.chk_gpu_status(self.gpu_id):
      self.logger.warning('GPU: %s not visible in clinfo', self.gpu_id)
      self.set_job_state(self.last_fetch_state, increment_retries=True)
      self.set_barrier(self.reset_machine, True)
      success = False

    if success:
      success = super().handle_errors_or_complete(error_bad_param, status,
                                                  timeout, error_cfg, abort_cfg,
                                                  job_solver)
    if success:
      # update the job_id status in the database to finished
      self.set_job_state('evaluated')
      self.clear_job_cache_entry()

    return success

  def check_gpu(self):
    """Function to check gpu heartbeat"""
    if not self.machine.chk_gpu_status(self.gpu_id):
      self.logger.warning('GPU: %s not visible in clinfo', self.gpu_id)
      self.set_job_state(self.last_fetch_state, increment_retries=True)
      self.set_barrier(self.reset_machine, True)
      return False
    return True

  def kcache_download(self, cache_dir):
    """download kernel object from mysql db"""
    good_tx = False
    with DbSession() as session:
      query = session.query(self.dbt.cache_table).filter(
          self.dbt.cache_table.job_id == self.job.id)
      res = query.all()

      if res:
        cache_obj = res[0]
        self.exec_command('mkdir -p {}'.format(cache_dir))
        file_path = "{}/{}".format(cache_dir, cache_obj.cache_name)
        self.machine.write_file(cache_obj.kernel_blob, file_path)
        ret_code, _, err = self.exec_command("stat {}".format(file_path))
        if ret_code != 0:
          self.logger.warning(err.read())
          self.logger.warning("Failed to download Kernel cache %s", file_path)
        else:
          good_tx = True
      else:
        self.logger.warning("No cache entry for id %s", self.job.id)

    if not good_tx:
      self.set_job_state('transfer_error')

    return good_tx

  def clear_job_cache_entry(self):
    """delete the job_cache entry for this job"""
    good_tx = False
    with DbSession() as session:
      try:
        query = session.query(self.dbt.cache_table).filter(
            self.dbt.cache_table.job_id == self.job.id)
        query.delete()
        session.commit()
        good_tx = True
      except OperationalError as err:
        self.logger.warning(err)
        good_tx = False

    return good_tx

  def get_perf_cfg(self):
    """create a config dict to query sqlite db generated by miopen"""

    iter_obj = self.config_dict

    perf_cfg = {
        key: val
        for key, val in iter_obj.items()
        if key in SQLITE_CONFIG_COLS and
        (iter_obj['spatial_dim'] == 3 or not key.endswith("_d"))
    }

    perf_cfg['data_type'] = CMD_TO_PREC[self.config_dict['cmd']]

    perf_cfg['direction'] = self.config.direction

    perf_cfg = mysql_to_sqlite_cfg(perf_cfg)
    perf_cfg = valid_cfg_dims(perf_cfg)

    return perf_cfg

  def get_miopen_udb(self):
    """locate or download miopen.udb created by perf run"""
    miopen_udb = 'miopen_{}.udb'.format(MIOPEN_DB_VERSION)

    if not self.machine.local_machine:
      files = []
      try:
        ftp = self.machine.connect().open_sftp()
        files = ftp.listdir(MIOPEN_USER_DB_PATH)
      except ftplib.error_perm as resp:
        if str(resp) == "550 No files found":
          self.logger.warning("No files in this directory")
        else:
          raise
    else:
      files = [f for f in os.listdir(MIOPEN_USER_DB_PATH)]

    for fname in files:
      arch = self.dbt.session.arch
      len_arch = len(arch)
      num_cu = "{}".format(self.dbt.session.num_cu)
      if self.dbt.session.num_cu > 64:
        num_cu = "{:x}".format(self.dbt.session.num_cu)
      if arch in fname:
        if num_cu in fname[len_arch:]:
          if fname.endswith('.udb'):
            miopen_udb = fname
            break

    if not self.machine.local_machine:
      remote_path = os.path.join(MIOPEN_USER_DB_PATH, miopen_udb)
      local_path = os.path.expanduser(
          os.path.join('~/tmp', 'partial_perf_db', str(self.machine.id),
                       str(self.gpu_id)))
      os.makedirs(local_path, exist_ok=True)
      local_path = os.path.join(local_path, miopen_udb)
      ftp = self.machine.connect().open_sftp()
      ftp.get(remote_path, local_path)
    else:
      local_path = os.path.join(MIOPEN_USER_DB_PATH, miopen_udb)

    self.logger.info('sqlite db file: %s', local_path)

    return local_path

  def step(self):
    """Function that defined the evaluator specific functionality which implies picking up jobs
    to benchmark and updating DB with evaluator specific state"""
    if not self.machine.chk_gpu_status(self.gpu_id):
      self.logger.warning('GPU: %s not visible in clinfo', self.gpu_id)
      self.set_barrier(self.reset_machine, True)
      return True

    ret = self.get_job('compiled', 'eval_start', True)
    if not ret:
      return False

    if not self.solver.tunable:
      self.set_job_state('not_tunable')
      return True

    cache_dir = "{}/{}".format(KCACHE_DIR, self.job.id)
    self.exec_command('sudo chown -R {0}:{0} {1}'.format(
        self.machine.user, KCACHE_DIR))
    if not self.bin_cache:
      good_tx = self.kcache_download(cache_dir)
      if not good_tx:
        return True

    self.logger.info('Acquired new job: job_id=%s', self.job.id)
    self.poll_retries = 0

    env_sav = self.envmt[:]
    if not self.bin_cache:
      self.envmt.append("MIOPEN_CUSTOM_CACHE_DIR={}".format(cache_dir))

    self.set_job_state('evaluating')
    _, stdout, ret_err = self.run_driver_cmd()

    self.envmt = env_sav

    if not stdout:
      self.logger.warning('Command for job %s did not return, retry.',
                          self.job.id)
      self.set_job_state(self.last_fetch_state, increment_retries=True)
      return True

    if stdout is not None and hasattr(stdout, 'channel'):
      stdout.channel.settimeout(LOG_TIMEOUT)
    timeout, error_cfg, abort_cfg, error_bad_param = self.process_log_line(
        stdout)

    #check this is a run_perf
    if 'compiled' in self.fetch_state:
      context = DotDict({
          'target_file': self.get_miopen_udb(),
          'table_cfg': self.dbt.config_table,
          'table_perf_cfg': self.dbt.perf_config_table,
          'table_perf_db': self.dbt.perf_db_table,
          'session_id': self.session_id
      })
      saved_sql = record_perfdb(context, self.get_perf_cfg())
      if not saved_sql:
        self.logger.error('Failed to save perfdb')
        error_cfg = True

    self.handle_errors_or_complete(error_bad_param, self.check_status(ret_err),
                                   timeout, error_cfg, abort_cfg,
                                   self.job.solver)

    #if job has been running for longer than the reset interval, we reboot
    if self.reset_interval and ((datetime.now() - self.last_reset).seconds >
                                60 * 60 * self.reset_interval):
      self.set_barrier(self.reset_machine, True)
    return True
