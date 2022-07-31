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
import json
from datetime import datetime
import socket
import random
import string
from time import sleep
from sqlalchemy import func as sqlalchemy_func
from sqlalchemy.exc import IntegrityError, OperationalError  #pylint: disable=wrong-import-order

from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.db_utility import get_id_solvers
from tuna.abort import chk_abort_file
from tuna.fin_utils import compose_config_obj
from tuna.metadata import TUNA_LOG_DIR, TUNA_DOCKER_NAME, PREC_TO_CMD
from tuna.metadata import TABLE_COLS_FUSION_MAP, TABLE_COLS_CONV_MAP, INVERS_DIR_MAP
from tuna.metadata import ENV_SLVGRP_MAP, SLV_ENV_MAP
from tuna.metadata import FIND_ONLY_EXCEPTION
from tuna.metadata import get_solver_ids, TENSOR_PRECISION
from tuna.tables import DBTables
from tuna.db_tables import connect_db
from tuna.config_type import ConfigType

MAX_JOB_RETRIES = 10
NUM_SQL_RETRIES = 10

TABLE_COLS_CONV_INVMAP = {}
for clarg, cnvparam in TABLE_COLS_CONV_MAP.items():
  if not cnvparam[0] in TABLE_COLS_CONV_INVMAP:
    TABLE_COLS_CONV_INVMAP[cnvparam[0]] = clarg
  elif len(clarg) > len(TABLE_COLS_CONV_INVMAP[cnvparam[0]]):
    TABLE_COLS_CONV_INVMAP[cnvparam[0]] = clarg

TABLE_COLS_FUSION_INVMAP = {}
for clarg, cnvparam in TABLE_COLS_FUSION_MAP.items():
  if not cnvparam[0] in TABLE_COLS_FUSION_INVMAP:
    TABLE_COLS_FUSION_INVMAP[cnvparam[0]] = clarg
  elif len(clarg) > len(TABLE_COLS_FUSION_INVMAP[cnvparam[0]]):
    TABLE_COLS_FUSION_INVMAP[cnvparam[0]] = clarg

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
        'reset_interval', 'fin_steps', 'fin_infile', 'fin_outfile', 'job_queue',
        'queue_lock', 'label', 'fetch_state', 'docker_name', 'bin_cache',
        'end_jobs', 'config_type', 'dynamic_solvers_only', 'session_id'
    ])
    self.__dict__.update((key, None) for key in allowed_keys)

    #for pylint
    self.machine = None
    self.gpu_id = None
    self.num_procs = self.barred = None
    self.bar_lock = Lock()
    self.envmt = []
    self.fin_steps = []
    self.fin_infile = None
    self.fin_outfile = None
    self.job_queue = None
    self.queue_lock = Lock()
    self.is_fdb = False
    self.find_db = None
    self.fetch_state = ['new']
    self.compile_only = False
    self.docker_name = TUNA_DOCKER_NAME
    self.gpu = None
    self.bin_cache = False
    self.label = None
    self.end_jobs = None
    self.solver_id_map, _ = get_solver_ids()
    self.id_solver_map, _ = get_id_solvers()
    self.dynamic_solvers_only = False
    self.config_type = ConfigType.convolution if self.config_type is None else self.config_type
    self.config_dict = None
    self.session_id = None

    self.__dict__.update(
        (key, value) for key, value in kwargs.items() if key in allowed_keys)

    self.dbt = DBTables(session_id=self.session_id,
                        config_type=self.config_type)

    self.miopen_user_db_path = "/tmp/miopenpdb/thread-{}/config/miopen".format(
        self.gpu_id)
    self.envmt.append(
        "MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopenpdb/thread-{}/cache".format(
            self.gpu_id))
    self.envmt.append("MIOPEN_USER_DB_PATH={}".format(self.miopen_user_db_path))

    self.hostname = self.machine.hostname
    self.poll_retries = 0
    self.job = None
    self.config = None
    self.solver = None
    self.cmd_iter = 1
    self.claim_num = self.num_procs.value
    self.last_reset = datetime.now()

    dir_name = os.path.join(TUNA_LOG_DIR,
                            type(self).__name__,
                            "{}_{}p".format(self.hostname, self.machine.port))
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

  #@staticmethod
  def check_status(self, err):
    """Function to check err status"""
    if err is not None and hasattr(err,
                                   'channel') and err.channel.exit_status > 0:
      self.logger.warning(err)
      status = False
    else:  # -1 means the command is still running
      status = True

    return status

  def reset_machine(self):
    """Function to reset machhine"""
    self.machine.restart_server()
    self.last_reset = datetime.now()

  def process_log_line(self, stdout):
    """Parse log from run command"""
    timeout = False
    error_cfg = False
    abort_cfg = False
    error_bad_param = False
    self.compile_only = False

    for line in stdout:
      try:
        if chk_abort_file(self.machine.id, self.logger, self.machine.arch):
          with self.bar_lock:
            self.num_procs.value -= 1
          break
        decoded_line = line.strip()  # lines.strip().decode()
        self.logger.info(decoded_line)
        low_line = decoded_line.lower()
        if low_line.find('error') != -1 and not self.compile_only:
          #ingore search failed error from miopen
          if 'search failed' in low_line:
            continue
          # miopen throws an error to escape after compiling when using MIOPEN_COMPILE_AND_RUN=0
          err1 = 'search skipped' in low_line
          # miopen also throws an error when MIOPEN_DEVICE_ARCH is used
          err2 = 'escaping launching kernel' in low_line
          # error thrown as a result of MIOPEN_DEBUG_COMPILE_ONLY
          err3 = 'miopen_debug_compile_only is enabled, escaping' in low_line
          if err1 or err2 or err3:
            self.compile_only = True
            error_cfg = False
          else:
            self.logger.error('Parser found error: %s', low_line)
            error_cfg = True

          # when miopen doesn't search for the specified solver, it will throw bad param
          if 'incorrect param' in decoded_line:
            error_bad_param = True
        if low_line.find('aborted') != -1:
          abort_cfg = True

      except (socket.timeout, socket.error):
        timeout = True
        self.logger.warning('Socket error, aborted')
        break
    if stdout is None:
      abort_cfg = True

    return timeout, error_cfg, abort_cfg, error_bad_param

  def handle_errors_or_complete(self, error_bad_param, status, timeout,
                                error_cfg, abort_cfg, job_solver):
    """Function to update job state"""
    success = False
    if error_bad_param:
      self.logger.warning('job id %s: solver %s had incorrect parameters',
                          self.job.id, job_solver)
      self.set_job_state('bad_param')
    elif not status:
      # the command failed to run properly
      self.logger.warning('job id %s: MIOpen Driver failed to run properly',
                          self.job.id)
      self.set_job_state('error_status')
    elif timeout:
      # write to value indicating this thing has hanged and wait for it to reach num_procs - 1 ,
      # then restart
      # then reopen the ssh, then continue
      # update the job_id status in the database to new since the job failed
      self.logger.error(
          'job id %s: Timeout while waiting for command to finish', self.job.id)
      self.set_job_state('timeout')
      self.set_barrier(self.reset_machine, True)
    elif error_cfg:
      self.logger.warning('job id %s errored', self.job.id)
      self.set_job_state('errored')
    elif abort_cfg:
      self.logger.warning('job id %s aborted', self.job.id)
      self.set_job_state('aborted')
    else:
      success = True

    return success

  def compose_query(self, find_state, session):
    """Helper function to compose query"""
    query = session.query(self.dbt.job_table, self.dbt.config_table)\
                          .filter(self.dbt.job_table.session == self.dbt.session.id)\
                          .filter(self.dbt.job_table.valid == 1)\
                          .filter(self.dbt.config_table.valid == 1)

    if self.label:
      query = query.filter(self.dbt.job_table.reason == self.label)
    if self.fin_steps:
      query = query.filter(
          self.dbt.job_table.fin_step.like('%' + self.fin_steps[0] + '%'))
    else:
      query = query.filter(self.dbt.job_table.fin_step == 'not_fin')
    query = query.filter(self.dbt.job_table.retries < MAX_JOB_RETRIES)\
      .filter(self.dbt.job_table.state == find_state)\
      .filter(self.dbt.config_table.id == self.dbt.job_table.config)

    query = query.order_by(self.dbt.job_table.retries.asc()).limit(
        self.claim_num).with_for_update()

    return query

  def get_fdb_entry(self, session, solver):
    """ Get FindDb entry from db """
    fdb_entry = self.dbt.find_db_table()
    fdb_entry.config = self.config.id
    fdb_entry.solver = solver
    fdb_entry.session = self.dbt.session.id
    fdb_entry.opencl = False
    fdb_entry.logger = self.logger
    fdb_entry.session = self.dbt.session.id
    fdb_query = fdb_entry.get_query(session, self.dbt.find_db_table,
                                    self.dbt.solver_app, self.dbt.session.id)
    obj = fdb_query.first()
    return obj, fdb_entry

  def update_fdb_entry(self, session, solver):
    """ Add a new entry to fdb if there isnt one already """
    obj, fdb_entry = self.get_fdb_entry(session, solver)
    if obj:  # existing entry in db
      # This can be removed if we implement the delete orphan cascade
      for blob in obj.blobs:
        session.delete(blob)
      fdb_entry = obj
    else:
      # Insert the above entry
      session.add(fdb_entry)
    return fdb_entry

  def compose_fdb_entry(self, session, fin_json, fdb_obj):
    """Compose a FindDB table entry from fin_output"""
    fdb_entry = self.update_fdb_entry(
        session, self.solver_id_map[fdb_obj['solver_name']])
    fdb_entry.fdb_key = fin_json['db_key']
    fdb_entry.kernel_time = -1
    fdb_entry.alg_lib = fdb_obj['algorithm']
    fdb_entry.workspace_sz = -1
    fdb_entry.session = self.dbt.session.id
    return fdb_entry

  def compose_kernel_entry(self, fdb_obj, fdb_entry):
    """Compose a new Kernel Cache entry from fin input"""
    fdb_entry.valid = True
    fdb_entry.workspace_sz = fdb_obj['workspace']
    # Now we have the ID, lets add the binary cache objects
    fdb_entry.blobs = []
    for kern_obj in fdb_obj['kernel_objects']:
      kernel_obj = self.dbt.kernel_cache()
      kernel_obj.conv_find_db_key = fdb_entry.id
      kernel_obj.kernel_name = kern_obj['kernel_file']
      kernel_obj.kernel_args = kern_obj['comp_options']
      kernel_obj.kernel_blob = bytes(kern_obj['blob'], 'utf-8')
      kernel_obj.kernel_hash = kern_obj['md5_sum']
      kernel_obj.uncompressed_size = kern_obj['uncompressed_size']
      fdb_entry.blobs.append(kernel_obj)
    return True

  def process_fdb_compile(self,
                          session,
                          fin_json,
                          result_str='miopen_find_compile_result',
                          check_str='find_compiled'):
    """retrieve find db compile json results"""
    success = False
    for fdb_obj in fin_json[result_str]:
      if fdb_obj[check_str]:
        fdb_entry = self.compose_fdb_entry(session, fin_json, fdb_obj)
        if fdb_obj['reason'] == 'Success':
          success = self.compose_kernel_entry(fdb_obj, fdb_entry)
          session.add(fdb_entry)
          self.logger.info('Updating find Db(Build) for job_id=%s', self.job.id)
        else:
          # JD: add info about reason to the logs table
          fdb_entry.valid = False
      else:
        self.logger.warning("Failed find_db compile, cfg_id: %s, obj: %s",
                            fin_json['config_tuna_id'], fdb_obj)

    try:
      session.commit()
    except OperationalError as err:
      self.logger.warning('FinEval: Unable to update Database: %s', err)
      success = False

    return success

  def update_pdb_config(self, session, layout, data_type, bias):
    """ update and retrieve perf_config entry from mysql """
    perf_config_table = self.dbt.perf_config_table

    perf_config_dict = {
        'layout': layout,
        'data_type': data_type,
        'bias': bias,
        'config': self.config.id,
        'session': self.dbt.session.id
    }

    self.logger.info('Updating %s for job_id=%s',
                     perf_config_table.__tablename__, self.job.id)
    res = session.query(perf_config_table).filter_by(**perf_config_dict).all()
    if not res:
      session.add(perf_config_table(**perf_config_dict))
      session.commit()

    perf_config_entry = session.query(perf_config_table).filter_by(
        **perf_config_dict).one()
    return perf_config_entry

  def update_pdb_entry(self, session, solver, layout, data_type, bias, params):
    """ update and retrieve perf_db entry from mysql """
    perf_table = self.dbt.perf_db_table

    perf_config_entry = self.update_pdb_config(session, layout, data_type, bias)

    perf_db_dict = {
        'solver': solver,
        'miopen_config': perf_config_entry.id,
        'session': self.dbt.session.id
    }
    update_dict = {'params': params, 'session': self.dbt.session.id}
    self.logger.info('Updating %s for job_id=%s', perf_table.__tablename__,
                     self.job.id)
    num_rows = session.query(perf_table).filter_by(
        **perf_db_dict).update(update_dict)
    perf_db_dict.update(update_dict)
    if num_rows == 0:
      self.logger.info('insert %s for job_id=%s', perf_db_dict, self.job.id)
      session.add(perf_table(**perf_db_dict))
    else:
      self.logger.info('%u update %s for job_id=%s', num_rows, perf_db_dict,
                       self.job.id)

    session.commit()

    query = session.query(perf_table).filter_by(**perf_db_dict)
    perf_entry = query.one()

    return perf_config_entry, perf_entry

  def queue_end_reset(self):
    """resets end queue flag"""
    with self.bar_lock:
      self.end_jobs.value = 0

  def load_job_queue(self, session, ids):
    """load job_queue with info for job ids"""
    job_cfgs = session.query(self.dbt.job_table, self.dbt.config_table)\
      .filter(self.dbt.job_table.valid == 1)\
      .filter(self.dbt.job_table.session == self.dbt.session.id)\
      .filter(self.dbt.config_table.id == self.dbt.job_table.config)\
      .filter(self.dbt.job_table.id.in_(ids)).all()
    if len(ids) != len(job_cfgs):
      raise Exception(
          'Failed to load job queue. #ids: {} - #job_cgfs: {}'.format(
              len(ids), len(job_cfgs)))
    for job, config in job_cfgs:
      if job.solver:
        query = session.query(self.dbt.solver_table)\
            .filter(self.dbt.solver_table.session == self.dbt.session.id)\
            .filter(self.dbt.solver_table.solver == job.solver)
        solver = query.one()
      else:
        query = session.query(self.dbt.solver_app, self.dbt.solver_table)\
            .filter(self.dbt.solver_app.session == self.dbt.session.id)\
            .filter(self.dbt.solver_app.applicable == 1)\
            .filter(self.dbt.solver_table.tunable == 1)\
            .filter(self.dbt.solver_app.config == job.config)\
            .filter(self.dbt.solver_app.solver == self.dbt.solver_table.id)\
            .filter(self.dbt.solver_table.tunable == 1)

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
              query = self.compose_query(find_state, session)
              job_cfgs = query.all()

              if not job_cfgs:
                # we are done
                self.logger.warning('No %s jobs found, fin_step: %s',
                                    find_state, self.fin_steps)
                if imply_end:
                  self.logger.warning("set end")
                  self.end_jobs.value = 1
                return False

              ids = tuple([str(job_row.id) for job_row, _ in job_cfgs])
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
          self.config_dict = compose_config_obj(self.config)
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
  def set_job_state(self, state, increment_retries=False):
    """Interface function to update job state for builder/evaluator"""
    self.logger.info('Setting job id %s state to %s', self.job.id, state)
    for idx in range(NUM_SQL_RETRIES):
      with DbSession() as session:
        try:
          if state in ["running", "compiling", "evaluating"]:
            session.query(self.dbt.job_table).filter(
                self.dbt.job_table.id == self.job.id).update({
                    self.dbt.job_table.state: state,
                })
          else:
            if increment_retries:
              session.query(self.dbt.job_table).filter(
                  self.dbt.job_table.id == self.job.id).update({
                      self.dbt.job_table.state: state,
                      self.dbt.job_table.retries: self.dbt.job_table.retries + 1
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
                      self.dbt.job_table.cache_loc: cache_loc
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

  def get_branch_hash(self):
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

  @staticmethod
  def compose_lcl_envmt(solver):
    """Setting up local_envmt var"""
    # JD: Move HIP_VISIBLE_DEVICES here
    # pylint: disable=too-many-nested-blocks
    lcl_envmt = []
    solver_id_map, _ = get_solver_ids()
    if solver not in FIND_ONLY_EXCEPTION:
      lcl_envmt.append("MIOPEN_DEBUG_FIND_ONLY_SOLVER={}".format(
          solver_id_map[solver]))
      for key, env_var in FIND_ONLY_EXCEPTION.items():
        lcl_envmt.append("{}=0".format(env_var))
    else:
      for key, sol_group in ENV_SLVGRP_MAP.items():
        if solver not in sol_group:
          lcl_envmt.append("{}=0".format(key))
        else:
          for item in sol_group:
            if item != solver and item in SLV_ENV_MAP:
              if solver not in SLV_ENV_MAP or SLV_ENV_MAP[item] != SLV_ENV_MAP[
                  solver]:
                cnstr = "{}=0".format(SLV_ENV_MAP[item])
                if cnstr not in lcl_envmt:
                  lcl_envmt.append(cnstr)
    return lcl_envmt

  def run_fin_cmd(self):
    """Run a fin command after generating the JSON"""
    fin_output = self.machine.make_temp_file()
    cmd = []

    env_str = " ".join(self.envmt)
    cmd.append(env_str)
    cmd.extend(
        ['/opt/rocm/bin/fin', '-i',
         self.get_fin_input(), '-o', fin_output])  # pylint: disable=no-member

    for i in range(MAX_JOB_RETRIES):
      ret_code, _, err = self.exec_docker_cmd(cmd)

      if ret_code != 0:
        self.logger.error('Error executing command: %s', ' '.join(cmd))
        if err:
          err_str = err.read()
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

    if ret_code != 0:
      return None

    # load the output json file and strip the env
    fin_json = json.loads(self.machine.read_file(fin_output))[1:]
    assert len(fin_json) == 1
    # JD: if we implement multiple jobs per fin launch, this would be a loop
    fin_json = fin_json[0]
    return fin_json

  def run_driver_cmd(self):
    """Definition of running the MIOpen driver cmd"""

    sub_cmd = PREC_TO_CMD[self.config_type][self.config.input_t.data_type]

    bash_cmd = 'MIOpenDriver {} -V 0 -i 1'.format(sub_cmd)

    driver_args = self.config_dict
    if "direction" in driver_args:
      driver_args['direction'] = INVERS_DIR_MAP[driver_args['direction']]
    for field, val in driver_args.items():
      if val is None:
        continue
      if sub_cmd in TENSOR_PRECISION.keys():
        if field in TABLE_COLS_CONV_INVMAP.keys():
          arg_name = TABLE_COLS_CONV_INVMAP[field]
          bash_cmd += " -{} {}".format(arg_name, val)
      elif sub_cmd in ['CBAInfer', 'CBAInferfp16']:
        if field in TABLE_COLS_FUSION_INVMAP.keys():
          arg_name = TABLE_COLS_FUSION_INVMAP[field]
          bash_cmd += " -{} {}".format(arg_name, val)

    lcl_envmt = self.envmt[:]

    # solver = self.job.solver if self.job.solver and not self.job.solver == '' else None
    if self.job.solver:  # None and empty string are both false
      self.logger.info('Solver specified, filter using MIOpen env vars: %s',
                       self.job.solver)
      lcl_envmt.extend(self.compose_lcl_envmt(self.job.solver))

    # create environment string for the command to execute,
    # remote ssh is rejecting the env setting using dicts
    export_all = ["{}".format(x) for x in lcl_envmt]
    env_str = " ".join(export_all)

    bash_cmd = bash_cmd + ' 2>&1 '
    # p = os.path.join('/home',self.user, 'MLOpen')

    cmd = "{env} {wrk}".format(env=env_str, wrk=bash_cmd)

    self.logger.warning("Machine: %s, GPU ID: %s, Executing: %s", self.hostname,
                        self.gpu_id, cmd)

    return self.exec_docker_cmd(cmd)

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

  def get_compile_jobs(self):
    """Checking num compile jobs left to determine
    when the evaluator should stop waiting for jobs to compile"""
    with DbSession() as session:
      try:
        query = session.query(sqlalchemy_func.count(self.dbt.job_table.id))\
            .filter(self.dbt.job_table.valid == 1)\
            .filter(self.dbt.job_table.session == self.dbt.session.id)\
            .filter(self.dbt.job_table.state.in_(('new', 'started', 'compile_start', 'compiling',
                                                  'compiled')))
        if self.label:
          query = query.filter(self.dbt.job_table.reason == self.label)
        if self.machine.arch:
          query = query.filter(self.dbt.job_table.arch == self.machine.arch)
        if self.machine.num_cu:
          query = query.filter(self.dbt.job_table.num_cu == self.machine.num_cu)
        if self.fin_steps:
          query = query.filter(
              self.dbt.job_table.fin_step.like('%' + self.fin_steps[0] + '%'))
        else:
          query = query.filter(self.dbt.job_table.fin_step == 'not_fin')
        compile_jobs = query.one()[0]
      except IntegrityError as error:
        session.rollback()
        self.logger.warning('Attempt to get #compile jobs failed')
        self.logger.warning(error)
    return compile_jobs

  def reset_job_state(self):
    """Helper function to reset job state during signal interrupt"""
    if self.job and self.job.state != 'compiled' and self.job.state != 'evaluated':
      self.logger.warning('resetting job state to %s', self.fetch_state[0])
      if "new" in self.fetch_state:
        self.set_job_state("new")
      if "compiled" in self.fetch_state:
        self.set_job_state("compiled")

    while not self.job_queue.empty():
      try:
        self.job, self.config, self.solver = self.job_queue.get(True, 1)
        if self.job.state == "compile_start":
          self.set_job_state("new")
        if self.job.state == "eval_start":
          if self.is_fdb:
            self.set_job_state("new")
          else:
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
        if not ret and (self.poll_retries > 0 and self.poll_retries < 120):
          pass
        elif not ret and (self.poll_retries == 0 or self.poll_retries >= 120):
          if self.poll_retries >= 120:
            self.logger.warning(
                'Max poll retries number(120) reached, quiting...')
            return False
          self.logger.warning('No more steps, quiting...')
          return True
    except KeyboardInterrupt as err:
      self.logger.error('%s', err)
      self.reset_job_state()
      return False

    return True
