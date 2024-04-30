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
import random
import functools
import json

from typing import List, Dict
from sqlalchemy.exc import OperationalError

from tuna.miopen.worker.fin_class import FinClass
from tuna.miopen.worker.fin_utils import fin_job
from tuna.miopen.worker.fin_utils import get_fin_slv_status, get_fin_result
from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.db_utility import session_retry, gen_update_query

MAX_ERRORED_JOB_RETRIES = 3


class FinEvaluator(FinClass):
  """ The Evaluator class implements the worker class. Its purpose is to run benchmarking jobs
  and when completed sets the state of the job to evaluated. """

  def __init__(self, **kwargs):
    super().__init__(**kwargs)
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

          blobs = session.query(self.dbt.kernel_cache).filter(
              self.dbt.kernel_cache.kernel_group == fdb_rec.kernel_group)
          res = session_retry(session, blobs.all, lambda x: x(), self.logger)
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
        return False

      fdb_entry = obj
      fdb_entry.alg_lib = fdb_obj['algorithm']
      fdb_entry.kernel_time = fdb_obj['time']
      fdb_entry.workspace_sz = fdb_obj['workspace']
      fdb_entry.session = self.dbt.session.id
      fdb_entry.params = fdb_obj['params']

      self.logger.info('Updating find db(Eval) for job_id=%s', self.job.id)
      query = gen_update_query(fdb_entry, self.fdb_attr,
                               self.dbt.find_db_table.__tablename__)
      session.execute(query)
      session.commit()
    else:
      self.logger.warning("Not evaluated: job(%s), solver(%s), %s", self.job.id,
                          fdb_obj['solver_name'], fdb_obj['reason'])
      return False

    return True

  def process_fdb_eval(
      self,
      fin_json: Dict,
      result_str: str = 'miopen_find_eval_result') -> List[Dict]:
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
          slv_stat['result'] = fdb_obj['reason']

        status.append(slv_stat)

    return status

  def clean_cache_table(self):
    """Remove the fin cache kernel entries for this job"""
    with DbSession() as session:
      try:
        self.logger.info('Delete kernel cache entries job(%s)', self.job.id)
        job_cache = session.query(self.dbt.fin_cache_table)\
            .filter(self.dbt.fin_cache_table.job_id == self.job.id)
        job_cache.delete()
        invalid_fdb_cache = session.query(self.dbt.kernel_cache)\
            .filter(self.dbt.kernel_cache.valid == 0)
        invalid_fdb_cache.delete()
        session.commit()
      except OperationalError as err:
        session.rollback()
        self.logger.warning('FinEval: Unable to clean %s / %s: %s',
                            self.dbt.fin_cache_table.__tablename__,
                            self.dbt.kernel_cache.__tablename__, err)

  def close_job(self):
    """mark a job complete"""
    self.set_job_state('evaluated')
    self.clean_cache_table()

  def get_job(self, find_state, set_state, imply_end):
    """Polling to see if job available"""
    self.logger.info('find job: %s', find_state)

    if not super().get_job(find_state, set_state, imply_end):
      return False
    return True

  def manage_queue(self):
    """Try to acquire a job, or manage the result queue if no job is available."""
    if not self.get_job("compiled", "eval_start", False):
      if not self.get_job("new", "eval_start", True):
        with self.bar_lock:
          self.num_procs.value -= 1
        while not self.result_queue_drain():
          sleep(random.randint(1, 10))
        return False
    return True

  def check_env(self) -> bool:
    """Interface function to check the miopen env version vs presumed miopen version"""
    if super().check_env():
      if self.dbt.session.arch != self.machine.arch:
        raise ValueError(
            f'session arch {self.dbt.session.arch} does not match machine arch\
            {self.machine.arch}')
      if self.dbt.session.num_cu != self.machine.num_cu:
        raise ValueError(
            f'session num_cu {self.dbt.session.num_cu} does not match machine num_cu\
            {self.machine.num_cu}')
    else:
      return False

    return True

  def step(self):
    """Function that defined the evaluator specific functionality which implies picking up jobs
    to benchmark and updating DB with evaluator specific state"""
    self.pending = []
    self.result_queue_drain()

    if not self.init_check_env():
      return False

    if not self.manage_queue():
      return False

    orig_state = 'compiled'
    self.logger.info('Acquired new job: job_id=%s', self.job.id)
    self.set_job_state('evaluating')
    fin_json = None
    try:
      fin_json = self.run_fin_cmd()
    except AssertionError:
      self.logger.error('Error building Fin input, job(%s)', self.job.id)
      self.set_job_state('errored', result='Error building Fin input')
      return True

    failed_job = True
    result_str = ''
    if fin_json:
      if 'miopen_find_eval_result' in fin_json:
        with DbSession() as session:
          status = self.process_fdb_w_kernels(
              session,
              fin_json,
              result_str='miopen_find_eval_result',
              check_str='evaluated')

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
      if not self.check_gpu():
        return False
      if self.job.retries >= (MAX_ERRORED_JOB_RETRIES - 1):
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
      self.result_queue.put(self.pending)
    else:
      self.set_job_state('evaluated', result=result_str)
      self.clean_cache_table()

    return True
