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
"""Builder class implements the worker interface. The purpose of this class is to run the
tuningRunner.py command"""

import sys
import os
from time import sleep
import random
import functools
import logging
from tenacity import Retrying, stop_after_attempt, before_sleep_log, wait_random

from sqlalchemy.inspection import inspect

from tuna.dbBase.sql_alchemy import DbSession
from tuna.worker_interface import WorkerInterface
from tuna.rocmlir.rocmlir_tables import RocMLIRDBTables
from tuna.utils.db_utility import session_retry, gen_insert_query
from tuna.rocmlir.config_type import ConfigType


class RocMLIRWorker(WorkerInterface):
  """ The RocMLIR class implements the worker class. Its purpose is to run a command. It picks up
  new jobs and when completed, sets the state to completed. """

  def __init__(self, **kwargs):
    """Constructor"""
    self.dbt = None
    self.config_type = kwargs['config_type']
    super().__init__(**kwargs)
    #    self.set_db_tables()
    self.result_attr = [column.name for column in inspect(self.dbt.results).c]
    self.result_attr.remove("insert_ts")
    self.result_attr.remove("update_ts")


# Can either have one of these, or --device below, but no combinations.
#     self.envmt.append(f"ROCR_VISIBLE_DEVICES={self.gpu_id}")
#     self.envmt.append(f"HIP_VISIBLE_DEVICES={self.gpu_id}")

  def set_db_tables(self):
    """Initialize tables"""
    self.dbt = RocMLIRDBTables(session_id=self.session_id, config_type=self.config_type)

  def update_result_table(self, session, result_str):
    """update results table with individual result entry"""
    obj = self.dbt.results()

    arch, num_cu, config, perf_config, tflops = obj.parse(result_str)

    print(f"arch = '{arch}', num_cu = '{num_cu}', config = '{config}', \
          perf_config = '{perf_config}', tflops = {tflops}",
          file=sys.stderr)

    obj.valid = 1
    obj.session = self.dbt.session.id
    obj.arch = arch
    obj.config = self.job.config
    obj.config_str = config
    obj.perf_config = perf_config
    obj.kernel_tflops = tflops

    self.logger.info('Inserting results for job_id=%s', self.job.id)
    query = gen_insert_query(obj, self.result_attr,
                             self.dbt.results.__tablename__)
    session.execute(query)
    session.commit()
    return True

  def process_result(self, result_str: str):
    """process tuning-run results"""
    with DbSession() as session:

      def actuator(func, result_str):
        return func(session, result_str)

      #retry returns false on failure, callback return on success
      ret = session_retry(session, self.update_result_table,
                          functools.partial(actuator, result_str=result_str),
                          self.logger)
      if not ret:
        self.logger.warning('RocMLIR:  Unable to update database')
      return ret

  def output_filename(self):
    """Canonical name for tuningRunner.py output for a job."""
    return f"tuning-results-{self.job.id}.tsv"

  def step(self):
    """Main functionality of the worker class. It picks up jobs in new state and executes them"""

    if not self.get_job("new", "running", False):
      #Sleep in case of DB contention
      sleep(random.randint(1, 10))
      return False

    self.logger.info('Acquired new job: job_id=%s', self.job.id)
    self.set_job_state('running')

    try:
      # Retry three times in the case of unhandled exceptions, logging them.
      for attempt in Retrying(stop=stop_after_attempt(3),
                              reraise=True,
                              wait=wait_random(min=5, max=30),
                              before_sleep=before_sleep_log(
                                  self.logger, logging.DEBUG)):
        with attempt:
          try:
            retcode, cmd_output = self.run_cmd()
          except ValueError as verr:
            self.logger.info(verr)
            self.set_job_state('errored', result=verr)
          else:
            if retcode != 0:
              quoted_output = cmd_output.replace("'", r"\'")
              msg = f"Error code {retcode}, output {quoted_output}"
              self.logger.info(msg)
              self.set_job_state('errored', result=msg)
            else:
              with open(self.output_filename(), 'r',
                        encoding='utf8') as results:
                # https://stackoverflow.com/questions/49902843/avoid-parameter-binding-when-executing-query-with-sqlalchemy
                string = results.read().replace(':', r'\:')
                self.set_job_state('completed', result=string)
                self.process_result(string)
              os.remove(self.output_filename())
    # pylint: disable=broad-exception-caught
    # Not sure what to expect beyond OSError.
    except Exception as exc:
      self.logger.warning(
          'Exception occurred while saving results of job %s:  %s', self.job.id,
          exc)
      self.set_job_state('errored', result=str(exc).replace("'", r"\'"))

    return True

  def run_cmd(self):
    """Run the actual workload"""
    env_str = " ".join(self.envmt)
    with DbSession() as session:
      cft = self.dbt.config_table
      config = session.query(cft).filter(cft.id == self.job.config).all()
      if len(config) > 1:
        raise ValueError(f"More than one config matching ID {self.job.config}")
      config_string = config[0].config_string()
    if self.config_type == ConfigType.convolution:
      special_args = "--operation conv"
    elif self.config_type == ConfigType.gemm:
      special_args = "--operation gemm"
    else:
      raise ValueError(f"Config type {self.config_type} not yet supported.")

    cmd = env_str + f" python3 ./bin/tuningRunner.py -q {special_args} \
                     --config='{config_string}' --mlir-build-dir `pwd` \
                     --output={self.output_filename()} --tflops \
                     --rocmlir_gen_flags='--device={self.gpu_id}'"

    retcode, out = super().run_command(cmd)

    return retcode, out

  def get_mlir_v(self) -> str:
    """Interface function to get mlir version info"""
    _, mlir_hash, _ = self.exec_docker_cmd("git rev-parse HEAD")
    self.logger.info('Got mlir version: %s', mlir_hash)
    return mlir_hash
