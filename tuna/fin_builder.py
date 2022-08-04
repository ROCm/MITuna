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
"""Builder class implements the worker interface. The purpose of this class is to run fin
jobs in compile mode"""
import json

from sqlalchemy.exc import OperationalError, DataError, IntegrityError

from tuna.worker_interface import WorkerInterface
from tuna.dbBase.sql_alchemy import DbSession
from tuna.fin_utils import fin_job


class FinBuilder(WorkerInterface):
  """ The Builder class implementes the worker class. Its purpose is to compile jobs. It picks up
  new jobs and when completed, sets the state to compiled. """

  def get_fin_input(self):
    """Create the input dict for fin, serialize to json and write to machine
       Returns the filename on machine"""
    # convert self.job and self.config to a json string
    fjob = fin_job(self.fin_steps, self.dynamic_solvers_only, self.job,
                   self.config, self.dbt)

    fjob = [fjob]

    fin_input = self.machine.write_file(json.dumps(fjob, indent=2).encode(),
                                        is_temp=True)
    return fin_input

  def compose_job_cache_entrys(self, session, pdb_obj):
    """Compose new pdb kernel cache entry from fin input"""
    for kern_obj in pdb_obj['kernel_objects']:
      kernel_obj = self.dbt.fin_cache_table()
      kernel_obj.kernel_name = kern_obj['kernel_file']
      kernel_obj.kernel_args = kern_obj['comp_options']
      kernel_obj.kernel_blob = bytes(kern_obj['blob'], 'utf-8')
      kernel_obj.kernel_hash = kern_obj['md5_sum']
      kernel_obj.uncompressed_size = kern_obj['uncompressed_size']
      kernel_obj.solver_id = self.solver_id_map[pdb_obj['solver_name']]
      kernel_obj.job_id = self.job.id

      session.add(kernel_obj)
    session.commit()

    return True

  def process_pdb_compile(self, session, fin_json):
    """retrieve perf db compile json results"""
    success = True
    if fin_json['miopen_perf_compile_result']:
      for pdb_obj in fin_json['miopen_perf_compile_result']:
        if pdb_obj['perf_compiled']:
          self.compose_job_cache_entrys(session, pdb_obj)
          self.logger.info('Updating pdb job_cache for job_id=%s', self.job.id)
    else:
      success = False

    return success

  def step(self):
    """Main functionality of the builder class. It picks up jobs in new state and compiles them"""
    if not self.get_job("new", "compile_start", True):
      return False

    # JD: while fin can exec multiple jobs at a time, that makes error detection difficult
    self.logger.info('Acquired new job: job_id=%s', self.job.id)
    self.set_job_state('compiling')
    fin_json = self.run_fin_cmd()

    failed_job = True
    if fin_json:
      failed_job = False
      with DbSession() as session:
        try:
          if 'miopen_find_compile_result' in fin_json:
            failed_job = not self.process_fdb_compile(session, fin_json)

          elif 'miopen_perf_compile_result' in fin_json:
            failed_job = not self.process_pdb_compile(session, fin_json)

        except (OperationalError, IntegrityError) as err:
          self.logger.warning('FinBuild: Unable to update Database %s', err)
          session.rollback()
          failed_job = True
        except DataError as err:
          self.logger.warning(
              'FinBuild: Invalid data, likely large workspace. DB Error: %s',
              err)
          session.rollback()
          failed_job = True

    if failed_job:
      self.set_job_state('errored')
    else:
      self.set_job_state('compiled')
    return True
