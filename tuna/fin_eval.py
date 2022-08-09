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
from time import sleep
import json

from sqlalchemy.exc import OperationalError

from tuna.worker_interface import WorkerInterface
from tuna.fin_utils import fin_job
from tuna.dbBase.sql_alchemy import DbSession

MAX_ERRORED_JOB_RETRIES = 3


class FinEvaluator(WorkerInterface):
  """ The Evaluator class implements the worker class. Its purpose is to run benchmarking jobs
  and when completed sets the state of the job to evaluated. """

  def get_job(self, find_state, set_state, imply_end):
    """Polling to see if job available"""
    self.logger.info('find job: %s', find_state)
    if not super().get_job(find_state, set_state, self.label):
      with self.bar_lock:
        self.num_procs.value -= 1
      return False
    return True

  def check_gpu(self):
    """Function to check gpu heartbeat"""
    for _ in range(5):
      if self.machine.chk_gpu_status(self.gpu_id):
        return
      self.logger.warning(
          'Unable to detect GPU: %s, sleeping for %s seconds before retry',
          self.gpu_id, 30)
      sleep(30)
    self.logger.warning('GPU: %s not visible in clinfo', self.gpu_id)
    self.set_job_state('compiled', increment_retries=True)
    self.set_barrier(self.reset_machine, True)

  def fin_pdb_input(self, _fjob):
    """prepare perf db command input for fin"""
    fjob = _fjob.copy()
    with DbSession() as session:
      perf_compile_res = []

      query = session.query(self.dbt.solver_app).filter(
          self.dbt.solver_app.session == self.dbt.session.id,
          self.dbt.solver_app.config == self.job.config,
          self.dbt.solver_app.arch == self.dbt.session.arch,
          self.dbt.solver_app.num_cu == self.dbt.session.num_cu,
          self.dbt.solver_app.applicable == 1)
      for slv_entry in query.all():
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
      for cache_entry in query.all():
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
    fjob = [fjob]
    return fjob

  def fin_fdb_input(self, _fjob):
    """prepare find db command input for fin"""
    fjob = _fjob.copy()
    with DbSession() as session:
      fdb_entry = self.dbt.find_db_table()
      fdb_entry.num_cu = self.dbt.session.num_cu
      fdb_entry.config = self.config.id
      fdb_entry.arch = self.dbt.session.arch
      fdb_entry.opencl = False
      fdb_entry.session = self.dbt.session.id
      fdb_entry.logger = self.logger
      fdb_query = fdb_entry.get_query(session, self.dbt.find_db_table,
                                      self.dbt.solver_app, self.dbt.session.id)
      # JD: The solvers which throw on GetSolution are marked with
      # negative workspace
      fdb_query = fdb_query.filter(self.dbt.find_db_table.workspace_sz != -1,
                                   self.dbt.find_db_table.valid == 1)

      find_compile_res = []
      # Enumerate all solvers for this config
      for fdb_rec in fdb_query.all():
        slv_name = self.id_solver_map[fdb_rec.solver]
        if not self.job.solver or slv_name == self.job.solver:
          compile_entry = {
              'algorithm': fdb_rec.alg_lib,
              'find_compiled': True,
              'solver_name': slv_name,
              'workspace': fdb_rec.workspace_sz
          }
          kernel_objects = []
          for obj in fdb_rec.blobs:
            kernel_objects.append({
                'blob': obj.kernel_blob.decode('utf-8'),
                'comp_options': obj.kernel_args,
                'kernel_file': obj.kernel_name,
                'md5_sum': obj.kernel_hash,
                'uncompressed_size': obj.uncompressed_size
            })
          compile_entry['kernel_objects'] = kernel_objects
          find_compile_res.append(compile_entry)

      assert find_compile_res
      fjob['miopen_find_compile_result'] = find_compile_res
    fjob = [fjob]
    return fjob

  def get_fin_input(self):
    """ Populate the input for fin and write to a tempfile on machine
    """
    steps = ['alloc_buf', self.fin_steps[0]]
    fjob = fin_job(steps, self.dynamic_solvers_only, self.job, self.config,
                   self.dbt)

    try:
      if self.fin_steps[0] == 'miopen_perf_eval':
        fjob = self.fin_pdb_input(fjob)
      elif self.fin_steps[0] == 'miopen_find_eval':
        fjob = self.fin_fdb_input(fjob)
    except AssertionError as err:
      self.logger.error('Unable to get compiled objects for job %s : %s',
                        self.job.id, err)
      raise AssertionError

    return self.machine.write_file(json.dumps(fjob, indent=2).encode(),
                                   is_temp=True)

  def process_fdb_eval(self, fin_json, result_str='miopen_find_eval_result'):
    """process find db eval json results"""
    failed_job = False
    for fdb_obj in fin_json[result_str]:
      self.logger.info('Processing object: %s', fdb_obj)
      with DbSession() as session:
        if fdb_obj['evaluated']:
          obj, _ = self.get_fdb_entry(
              session, self.solver_id_map[fdb_obj['solver_name']])
          if not obj:
            self.logger.info(
                'Unable to find fdb entry for config: %s, solver: %s, '\
                'arch: %s, num_cu: %s, direction: %s',
                self.config.id, self.solver_id_map[fdb_obj['solver_name']],
                self.dbt.session.arch, self.dbt.session.num_cu, self.config.direction)
            raise ValueError("Unable to query find db entry")
          fdb_entry = obj
          fdb_entry.alg_lib = fdb_obj['algorithm']
          fdb_entry.kernel_time = fdb_obj['time']
          # workspace
          fdb_entry.workspace_sz = fdb_obj['workspace']
          fdb_entry.session = self.dbt.session.id
        else:
          self.logger.warning("Not evaluated: job(%s), solver(%s), %s",
                              self.job.id, fdb_obj['solver_name'],
                              fdb_obj['reason'])

        self.logger.info('Updating find db(Eval) for job_id=%s', self.job.id)
        try:
          session.commit()
        except OperationalError as err:
          self.logger.warning('FinEval: Unable to update Database: %s', err)
          failed_job = True

    return failed_job

  def process_pdb_eval(self, fin_json):
    """process perf db eval json results"""
    failed_job = False
    for pdb_obj in fin_json['miopen_perf_eval_result']:
      self.logger.info('Processing object: %s', pdb_obj)
      with DbSession() as session:
        if pdb_obj['evaluated'] and pdb_obj['tunable']:
          try:
            solver = self.solver_id_map[pdb_obj['solver_name']]
            layout = pdb_obj['layout']
            data_type = pdb_obj['data_type']
            bias = pdb_obj['bias']
            params = pdb_obj['params']
            #call also updates perf_db+perf_config tables
            _, _ = self.update_pdb_entry(session, solver, layout, data_type,
                                         bias, params)

          except OperationalError as err:
            self.logger.warning('FinEval: Unable to update Database: %s', err)
            failed_job = True

    return failed_job

  def clean_cache_table(self):
    """Remove the fin cache kernel entries for this job"""
    with DbSession() as session:
      try:
        old_cache = session.query(self.dbt.fin_cache_table)\
            .filter(self.dbt.fin_cache_table.job_id == self.job.id)
        old_cache.delete()
        session.commit()
      except OperationalError as err:
        session.rollback()
        self.logger.warning('FinEval: Unable to clean %s: %s',
                            self.dbt.fin_cache_table.__tablename__, err)

  def step(self):
    """Function that defined the evaluator specific functionality which implies picking up jobs
    to benchmark and updating DB with evaluator specific state"""
    ret = self.get_job("compiled", "eval_start", True)
    if not ret:
      return False
    orig_state = 'compiled'
    self.logger.info('Acquired new job: job_id=%s', self.job.id)
    self.set_job_state('evaluating')
    try:
      fin_json = self.run_fin_cmd()
    except AssertionError as err:
      self.set_job_state('errored')
      self.logger.warning('Unable to launch job %s : %s', self.job.id, err)
      return True

    failed_job = True
    if fin_json:
      if 'miopen_find_eval_result' in fin_json:
        failed_job = self.process_fdb_eval(fin_json)

      elif 'miopen_perf_eval_result' in fin_json:
        failed_job = self.process_pdb_eval(fin_json)
        #also update fdb
        if not failed_job:
          with DbSession() as session:
            failed_job = not self.process_fdb_compile(
                session,
                fin_json,
                result_str='miopen_perf_eval_result',
                check_str='evaluated')
        if not failed_job:
          failed_job = self.process_fdb_eval(
              fin_json, result_str='miopen_perf_eval_result')

    if failed_job:
      self.check_gpu()
      if self.job.retries == (MAX_ERRORED_JOB_RETRIES - 1):
        self.logger.warning('max job retries exhausted, setting to errored')
        self.set_job_state('errored')
      else:
        self.logger.warning('resetting job state to %s, incrementing retries',
                            orig_state)
        self.set_job_state(orig_state, increment_retries=True)
    else:
      self.set_job_state('evaluated')
      self.clean_cache_table()

    return True
