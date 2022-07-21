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
"""Builder class implements the worker interface. The purpose of this class is to run MIOpenDriver
jobs in compile mode"""
import sys
from datetime import datetime
from time import sleep
from sqlalchemy.exc import OperationalError

from tuna.dbBase.sql_alchemy import DbSession
from tuna.worker_interface import WorkerInterface, NUM_SQL_RETRIES
from tuna.metadata import KCACHE_DIR
from tuna.utils.utility import arch2targetid


class Builder(WorkerInterface):
  """ The Builder class implementes the worker class. Its purpose is to compile jobs. It picks up
  new jobs and when completed, sets the state to compiled. """

  #pylint: disable=no-member

  def __init__(self, **kwargs):
    #for pylint
    self.envmt = []
    super().__init__(**kwargs)

    self.envmt.append("MIOPEN_FIND_ENFORCE=4")

  def get_job(self, find_state, set_state, imply_end):
    """Polling to see if job available"""
    ret = False
    #end_jobs==0 new jobs available for arch affinity
    if self.end_jobs.value == 0:
      ret = super().get_job(find_state, set_state, True)
    #make this atomic
    with self.bar_lock:
      #end_jobs==1 no jobs for arch affinity, still jobs for other archs
      if self.end_jobs.value == 1:
        ret = super().get_job(find_state, set_state, False)
        if not ret:
          #end_jobs==2 no jobs for any arch
          self.end_jobs.value = 2

    if not ret:
      self.logger.warning('No new jobs found, quiting .. ')
      with self.bar_lock:
        self.num_procs.value -= 1
      return False

    return True

  def handle_errors_or_complete(self, error_bad_param, status, timeout,
                                error_cfg, abort_cfg, job_solver):
    """Function to update job state"""
    success = super().handle_errors_or_complete(error_bad_param, status,
                                                timeout, error_cfg, abort_cfg,
                                                job_solver)

    if success:
      # update the job_id status in the database to finished
      self.logger.info('Setting job id %s state to compiled', self.job.id)
      self.set_job_state('compiled')

    return success

  def kcache_insert(self, cache_dir, cache_name):
    """upload kernel object to mysql db"""
    cache_path = "{}/{}".format(cache_dir, cache_name)
    kernel_blob = self.machine.read_file(cache_path, byteread=True)
    self.logger.info("generated cache file %s : %s", cache_path,
                     sys.getsizeof(kernel_blob))
    with DbSession() as session:
      query = session.query(self.dbt.cache_table).filter(
          self.dbt.cache_table.job_id == self.job.id)
      res = query.all()

      for idx in range(NUM_SQL_RETRIES):
        try:
          if res:
            query.update(
                {
                    self.dbt.cache_table.kernel_blob: bytes(kernel_blob),
                    self.dbt.cache_table.cache_name: cache_name
                },
                synchronize_session='fetch')
          else:
            cache_obj = self.dbt.cache_table(job_id=self.job.id,
                                             kernel_blob=kernel_blob,
                                             cache_name=cache_name)
            session.add(cache_obj)
          session.commit()
          return True
        except OperationalError as error:
          self.logger.warning(
              'Attempt %s to store kernel for job %s failed (%s), retrying ... ',
              idx, self.job.id, error)
          session.rollback()
          sleep(5)

    return False

  def step(self):
    """Main functionality of the builder class. It picks up jobs in new state and compiles them"""
    if not self.get_job("new", 'compile_start', True):
      return False

    if not self.solver.tunable:
      self.set_job_state('not_tunable')
      return True

    self.logger.info('Acquired new job: job_id=%s', self.job.id)

    #builder needs to compile to architecture per job
    env_sav = self.envmt[:]
    cache_dir = "{}/{}".format(KCACHE_DIR, self.job.id)
    self.envmt.append("MIOPEN_CUSTOM_CACHE_DIR={}".format(cache_dir))
    self.envmt.append("MIOPEN_DEVICE_CU={}".format(self.dbt.session.num_cu))
    self.envmt.append("MIOPEN_DEVICE_ARCH={}".format(
        arch2targetid(self.dbt.session.arch)))

    self.set_job_state('compiling')
    _, stdout, _ = self.run_driver_cmd()

    self.envmt = env_sav

    timeout, error_cfg, abort_cfg, error_bad_param = self.process_log_line(
        stdout)
    error_cfg = False
    error_bad_param = False
    abort_cfg = False

    #assert that ukdb file was generated in this step (compilation was a success)
    chk_ret, chk_out, err = self.exec_command(
        "ls {} | grep ukdb".format(cache_dir))
    if chk_ret != 0:
      self.logger.warning("Kernel cache failed to generate in directory %s/",
                          cache_dir)
      self.logger.warning("Error: %s", err)
      self.logger.warning("Out: %s", chk_out.read())
      error_cfg = True
    else:
      cache_name = chk_out.readline().strip()
      if not self.kcache_insert(cache_dir, cache_name):
        error_cfg = True

    status = True
    self.handle_errors_or_complete(error_bad_param, status, timeout, error_cfg,
                                   abort_cfg, self.job.solver)

    #if job has been running for longer than the reset interval, we reboot
    if self.reset_interval and ((datetime.now() - self.last_reset).seconds >
                                60 * 60 * self.reset_interval):
      self.set_barrier(self.reset_machine, True)
    return True
