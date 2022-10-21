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
import functools
import json

from sqlalchemy.exc import OperationalError

from tuna.miopen.fin_class import FinClass
from tuna.miopen.fin_utils import fin_job
from tuna.miopen.fin_utils import get_fin_slv_status, get_fin_result
from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.db_utility import session_retry

MAX_ERRORED_JOB_RETRIES = 3


class FinEvaluator(FinClass):
  """ The Evaluator class implements the worker class. Its purpose is to run benchmarking jobs
  and when completed sets the state of the job to evaluated. """

  def __init__(self, **kwargs):
    super().__init__(**kwargs)
    self.envmt.append(f"HIP_VISIBLE_DEVICES={self.gpu_id}")

  def get_job(self, find_state, set_state, imply_end):
    """Polling to see if job available"""
    self.logger.info('find job: %s', find_state)
    if not super().get_job(find_state, set_state, imply_end):
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

      # pylint: disable=comparison-with-callable
      query = session.query(self.dbt.solver_app).filter(
          self.dbt.solver_app.session == self.dbt.session.id,
          self.dbt.solver_app.config == self.job.config,
          self.dbt.solver_app.applicable == 1)
      # pylint: enable=comparison-with-callable

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
                                      self.dbt.session.id)
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
          blobs = session.query(self.dbt.kernel_cache).filter(
              self.dbt.kernel_cache.kernel_group == fdb_rec.kernel_group)
          for obj in blobs.all():
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
      raise AssertionError from err

    return self.machine.write_file(json.dumps(fjob, indent=2).encode(),
                                   is_temp=True)

  def update_fdb_eval_entry(self, session, fdb_obj):
    """update fdb with individual fin json entry"""
    if fdb_obj['evaluated']:
      obj, _ = self.get_fdb_entry(session,
                                  self.solver_id_map[fdb_obj['solver_name']])
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
      fdb_entry.workspace_sz = fdb_obj['workspace']
      fdb_entry.session = self.dbt.session.id
      fdb_entry.params = fdb_obj['params']
    else:
      self.logger.warning("Not evaluated: job(%s), solver(%s), %s", self.job.id,
                          fdb_obj['solver_name'], fdb_obj['reason'])

    self.logger.info('Updating find db(Eval) for job_id=%s', self.job.id)
    session.commit()

    return True

  def process_fdb_eval(self, fin_json, result_str='miopen_find_eval_result'):
    """process find db eval json results"""
    status = []
    fdb_obj = None
    with DbSession() as session:

      def actuator(func, fdb_obj):
        return func(session, fdb_obj)

      for fdb_obj in fin_json[result_str]:
        self.logger.info('Processing object: %s', fdb_obj)
        slv_stat = get_fin_slv_status(fdb_obj, 'evaluated')
        #retry returns false on failure, callback return on success
        ret = session_retry(session, self.update_fdb_eval_entry,
                            functools.partial(actuator, fdb_obj=fdb_obj),
                            self.logger)
        if not ret:
          self.logger.warning('FinEval: Unable to update Database')
          slv_stat['success'] = False
          slv_stat['result'] = 'FinEval: Unable to update Database'

        status.append(slv_stat)

    return status

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

  def reset_job_state(self):
    """finish committing result queue"""
    super().reset_job_state()
    if self.gpu_id == 0:
      with DbSession() as session:
        self.result_queue_commit(session, 'evaluated')

  def step(self):
    """Function that defined the evaluator specific functionality which implies picking up jobs
    to benchmark and updating DB with evaluator specific state"""
    self.pending = False
    if self.gpu_id == 0:
      with DbSession() as session:
        self.result_queue_commit(session, 'evaluated')

    # pylint: disable=duplicate-code
    if self.first_pass:
      self.first_pass = False
      try:
        self.check_env()
      except ValueError as verr:
        self.logger.error(verr)
        return False
    # pylint: enable=duplicate-code

    if not self.get_job("compiled", "eval_start", True):
      if self.gpu_id == 0 and self.num_procs.value > 1:
        #wait to commit results from other processes
        sleep(30)
        return True
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
    result_str = ''
    if fin_json:
      if 'miopen_find_eval_result' in fin_json:
        status = self.process_fdb_eval(fin_json)

      elif 'miopen_perf_eval_result' in fin_json:
        with DbSession() as session:
          status = self.process_fdb_w_kernels(
              session,
              fin_json,
              result_str='miopen_perf_eval_result',
              check_str='evaluated')

      success, result_str = get_fin_result(status)
      failed_job = not success

    if failed_job:
      self.check_gpu()
      if self.job.retries == (MAX_ERRORED_JOB_RETRIES - 1):
        self.logger.warning('max job retries exhausted, setting to errored')
        self.set_job_state('errored', result=result_str)
      else:
        self.logger.warning('resetting job state to %s, incrementing retries',
                            orig_state)
        self.set_job_state(orig_state,
                           increment_retries=True,
                           result=result_str)
    elif self.pending:
      self.set_job_state('evaluated_pend', result=result_str)
      self.clean_cache_table()
    else:
      self.set_job_state('evaluated', result=result_str)
      self.clean_cache_table()

    return True
