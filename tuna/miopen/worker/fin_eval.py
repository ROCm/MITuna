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
"""Fin Evaluator class implements the worker interface. The purpose of this class
is to run fin commands in benchmarking mode"""
import json

from typing import List, Dict

from tuna.miopen.worker.fin_class import FinClass
from tuna.miopen.worker.fin_utils import fin_job
from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.db_utility import gen_select_objs
from tuna.utils.db_utility import session_retry


class FinEvaluator(FinClass):
  """ The Evaluator class implements the worker class. Its purpose is to run benchmarking jobs
  and when completed sets the state of the job to evaluated. """

  def __init__(self, **kwargs):
    super().__init__(**kwargs)
    if self.gpu_id != -1:
      self.envmt.append(f"HIP_VISIBLE_DEVICES={self.gpu_id}")

  def check_gpu(self):
    """Function to check gpu heartbeat"""
    for _ in range(5):
      if self.machine.chk_gpu_status(self.gpu_id):
        return True
    self.logger.warning('GPU: %s not visible in clinfo', self.gpu_id)
    self.set_job_state('compiled',
                       increment_retries=True,
                       result=f"GPU {self.gpu_id} not visible")
    return False

  def fin_pdb_input(self, _fjob):
    """prepare perf db command input for fin"""
    fjob = _fjob.copy()
    with DbSession() as session:
      perf_compile_res = []

      # pylint: disable=comparison-with-callable
      query = session.query(self.dbt.solver_app).filter(
          self.dbt.solver_app.session == self.dbt.session.id,
          self.dbt.solver_app.config == self.job.config,
          self.dbt.solver_app.applicable == 1)
      # pylint: enable=comparison-with-callable

      res = session_retry(session, query.all, lambda x: x(), self.logger)
      for slv_entry in res:
        slv_name = self.id_solver_map[slv_entry.solver]
        if not self.job.solver or slv_name == self.job.solver:
          compile_entry = {
              'solver_name': slv_name,
              'perf_compiled': False,
              'kernel_objects': []
          }
          perf_compile_res.append(compile_entry)

      solvers = [x['solver_name'] for x in perf_compile_res]

      query = session.query(self.dbt.fin_cache_table).filter(
          self.dbt.fin_cache_table.job_id == self.job.id)

      res = session_retry(session, query.all, lambda x: x(), self.logger)
      for cache_entry in res:
        slv_name = self.id_solver_map[cache_entry.solver_id]
        #if job solver is defined limit entries to that solver
        if not self.job.solver or slv_name == self.job.solver:
          compile_entry = perf_compile_res[solvers.index(slv_name)]
          compile_entry['perf_compiled'] = True

          compile_entry['kernel_objects'].append({
              'blob': cache_entry.kernel_blob.decode('utf-8'),
              'comp_options': cache_entry.kernel_args,
              'kernel_file': cache_entry.kernel_name,
              'md5_sum': cache_entry.kernel_hash,
              'uncompressed_size': cache_entry.uncompressed_size
          })

      assert perf_compile_res
      fjob['miopen_perf_compile_result'] = perf_compile_res
    return [fjob]

  def fin_fdb_input(self, _fjob: Dict) -> List[Dict]:
    """prepare find db command input for fin"""
    fjob = _fjob.copy()
    with DbSession() as session:
      find_compile_res = []

      # pylint: disable=comparison-with-callable
      query = session.query(self.dbt.solver_app).filter(
          self.dbt.solver_app.session == self.dbt.session.id,
          self.dbt.solver_app.config == self.job.config,
          self.dbt.solver_app.applicable == 1)
      # pylint: enable=comparison-with-callable

      res = session_retry(session, query.all, lambda x: x(), self.logger)
      for slv_entry in res:
        slv_name = self.id_solver_map[slv_entry.solver]
        if not self.job.solver or slv_name == self.job.solver:
          compile_entry = {
              'solver_name': slv_name,
              'find_compiled': False,
              'kernel_objects': []
          }
          find_compile_res.append(compile_entry)

      solvers = [x['solver_name'] for x in find_compile_res]

      fdb_entry = self.dbt.find_db_table()
      fdb_entry.num_cu = self.dbt.session.num_cu
      fdb_entry.config = self.config.id
      fdb_entry.arch = self.dbt.session.arch
      fdb_entry.opencl = False
      fdb_entry.session = self.dbt.session.id
      fdb_entry.logger = self.logger
      fdb_query = fdb_entry.get_query(session, self.dbt.find_db_table,
                                      self.dbt.session.id)
      # JD: The solvers which throw on GetSolution are marked with
      # negative workspace
      fdb_query = fdb_query.filter(self.dbt.find_db_table.workspace_sz != -1,
                                   self.dbt.find_db_table.valid == 1)

      res = session_retry(session, fdb_query.all, lambda x: x(), self.logger)

      for fdb_rec in res:
        slv_name = self.id_solver_map[fdb_rec.solver]
        if not self.job.solver or slv_name == self.job.solver:
          compile_entry = find_compile_res[solvers.index(slv_name)]
          compile_entry['find_compiled'] = True


          kern_attr = ['kernel_blob', 'kernel_args', 'kernel_name', 'kernel_hash', 'uncompressed_size']
          kern_cond = f"where valid=1 and kernel_group = {fdb_rec.kernel_group}"
          res = gen_select_objs(session, kern_attr,
                                    self.dbt.kernel_cache.__tablename__,
                                    kern_cond)

          #blobs = session.query(self.dbt.kernel_cache).filter(
          #    self.dbt.kernel_cache.kernel_group == fdb_rec.kernel_group)
          #res = session_retry(session, blobs.all, lambda x: x(), self.logger)
          for obj in res:
            compile_entry['kernel_objects'].append({
                'blob': obj.kernel_blob.decode('utf-8'),
                'comp_options': obj.kernel_args,
                'kernel_file': obj.kernel_name,
                'md5_sum': obj.kernel_hash,
                'uncompressed_size': obj.uncompressed_size
            })

      assert find_compile_res
      fjob['miopen_find_compile_result'] = find_compile_res
    return [fjob]

  def get_fin_input(self):
    """ Populate the input for fin and write to a tempfile on machine
    """
    steps = ['alloc_buf', 'fill_buf', self.fin_steps[0]]
    fjob = fin_job(steps, self.dynamic_solvers_only, self.job, self.config,
                   self.dbt)

    try:
      if self.fin_steps[0] == 'miopen_perf_eval':
        fjob = self.fin_pdb_input(fjob)
      elif self.fin_steps[0] == 'miopen_find_eval':
        fjob = self.fin_fdb_input(fjob)
    except (AssertionError, ValueError) as err:
      self.logger.error('Unable to get compiled objects for job %s : %s',
                        self.job.id, err)
      raise AssertionError from err

    return self.machine.write_file(json.dumps(fjob, indent=2).encode(),
                                   is_temp=True)

  def get_job(self, find_state, set_state, imply_end):
    """Polling to see if job available"""
    self.logger.info('find job: %s', find_state)

    if not super().get_job(find_state, set_state, imply_end):
      return False
    return True

  def check_env(self) -> bool:
    """Check the GPU on the machine matches the GPU specified in session table"""
    if super().check_env():
      if self.dbt.session.arch != self.machine.arch or \
              self.dbt.session.num_cu != self.machine.num_cu:
        self.logger.error(
            'Session arch/num_cu (%s/%s) does not match env arch/num_cu (%s/%s)',
            self.dbt.session.arch, self.dbt.session.num_cu, self.machine.arch,
            self.machine.num_cu)
        return False
    else:
      return False

    return True

  def step(self):
    """Function that defined the evaluator specific functionality which implies picking up jobs
    to benchmark and updating DB with evaluator specific state"""

    if not self.init_check_env():
      return False

    fin_json = None
    try:
      fin_json = self.run_fin_cmd()
    except AssertionError:
      self.logger.error('Error building Fin input, job(%s)', self.job.id)

    return fin_json
