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
"""MIOpen class that holds MIOpen specifig  tuning functionality"""

import sys
from typing import List, Tuple

from sqlalchemy.inspection import inspect
from sqlalchemy.exc import NoInspectionAvailable
from tuna.mituna_interface import MITunaInterface
from tuna.miopen.utils.helper import print_solvers
from tuna.parse_args import TunaArgs, setup_arg_parser, args_check
from tuna.dbBase.sql_alchemy import DbSession
from tuna.tables_interface import DBTablesInterface
from tuna.utils.utility import SimpleDict
from tuna.utils.db_utility import gen_select_objs, has_attr_set, get_class_by_tablename
from tuna.miopen.db.miopen_tables import FinStep, get_miopen_tables
from tuna.miopen.utils.metadata import MIOPEN_ALG_LIST
from tuna.miopen.worker.fin_class import FinClass
#from tuna.miopen.worker.fin_builder import FinBuilder
#from tuna.miopen.worker.fin_eval import FinEvaluator
from tuna.worker_interface import WorkerInterface
from tuna.miopen.db.session import Session
from tuna.utils.miopen_utility import load_machines
from tuna.libraries import Library
from tuna.miopen.subcmd.import_configs import run_import_configs
from tuna.miopen.subcmd.load_job import run_load_job
from tuna.miopen.subcmd.export_db import run_export_db
from tuna.miopen.subcmd.update_golden import run_update_golden
from tuna.miopen.parse_miopen_args import get_import_cfg_parser
from tuna.miopen.parse_miopen_args import get_load_job_parser
from tuna.miopen.parse_miopen_args import get_export_db_parser
from tuna.miopen.parse_miopen_args import get_update_golden_parser
from tuna.miopen.db.build_schema import create_tables, recreate_triggers
from tuna.miopen.db.triggers import drop_miopen_triggers, get_miopen_triggers
from tuna.miopen.utils.config_type import ConfigType
from tuna.miopen.db.tables import MIOpenDBTables


class MIOpen(MITunaInterface):
  """Class to support MIOpen specific tuning functionality"""

  def __init__(self):
    super().__init__(library=Library.MIOPEN)
    self.args = None
    self.parse_args()

  def parse_args(self):
    # pylint: disable=too-many-statements
    """Function to parse arguments"""
    parser = setup_arg_parser(
        'Run Performance Tuning on a certain architecture', [
            TunaArgs.ARCH, TunaArgs.NUM_CU, TunaArgs.VERSION,
            TunaArgs.CONFIG_TYPE, TunaArgs.SESSION_ID, TunaArgs.MACHINES,
            TunaArgs.REMOTE_MACHINE, TunaArgs.LABEL, TunaArgs.RESTART_MACHINE,
            TunaArgs.DOCKER_NAME
        ])
    parser.add_argument(
        '--find_mode',
        dest='find_mode',
        type=int,
        default=1,
        help='Set the MIOPEN_FIND_MODE environment variable for MIOpen',
        choices=['1', '3'])
    parser.add_argument('--ticket',
                        dest='ticket',
                        type=str,
                        default=None,
                        help='Specify tuning ticket number')
    parser.add_argument(
        '--solver_id',
        type=int,
        dest='solver_id',
        default=None,
        help='Specify solver_id. Use --list_solvers to see options')
    parser.add_argument('--dynamic_solvers_only',
                        dest='dynamic_solvers_only',
                        action='store_true',
                        default=False,
                        help='Only tune dynamic solvers.')
    parser.add_argument(
        '-B',
        '--blacklist',
        dest='blacklist',
        type=str,
        default=None,
        help='MIOpen blacklist algorithm, if multiple then comma separate')
    parser.add_argument('-i',
                        '--reset_interval',
                        type=int,
                        dest='reset_interval',
                        required=False,
                        help='Restart interval for job in hours.')
    parser.add_argument(
        '--gpu_lim',
        dest='gpu_lim',
        type=int,
        default=None,
        help='Limit the number of gpu workers created by Tuna, index from 0')

    subcommands = parser.add_subcommands(required=False)
    subcommands.add_subcommand('import_configs',
                               get_import_cfg_parser(),
                               required=False)

    subcommands.add_subcommand('load_job',
                               get_load_job_parser(),
                               required=False)

    subcommands.add_subcommand('export_db',
                               get_export_db_parser(),
                               required=False)

    subcommands.add_subcommand('update_golden',
                               get_update_golden_parser(),
                               required=False)

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--add_tables',
                       dest='add_tables',
                       action='store_true',
                       help='Add MIOpen library specific tables')

    group.add_argument('--init_session',
                       action='store_true',
                       dest='init_session',
                       help='Set up a new tuning session.')
    group.add_argument(
        '--fin_steps',
        type=str,
        dest='fin_steps',
        help='Specify fin steps. Multiple steps should be comma separated.')
    group.add_argument('--list_solvers',
                       action='store_true',
                       dest='list_solvers',
                       help='List of solvers from the solver table')

    # JD: implement the following two using fin_steps
    group.add_argument('--update_solvers',
                       dest='update_solvers',
                       action='store_true',
                       help='Update the list of solvers in the database')
    group.add_argument('--update_applicability',
                       dest='update_applicability',
                       action='store_true',
                       help='Update the applicability table in the database')
    group.add_argument('-s',
                       '--status',
                       dest='check_status',
                       action='store_true',
                       default=False,
                       help='Check the status of machines')

    group.add_argument('-e',
                       '--exec',
                       dest='execute_cmd',
                       type=str,
                       default=None,
                       help='execute on each machine')

    self.args = parser.parse_args()

    if self.args.config_type is None:
      self.args.config_type = ConfigType.convolution

    #overwritte common lib args with subcommand args value
    if self.args.subcommand is not None:
      self.overwrite_common_args()

    if len(sys.argv) == 1:
      parser.print_help()
      sys.exit(-1)

    if self.args.list_solvers:
      print_solvers()
      raise ValueError('Printing solvers...')

    if self.args.fin_steps and self.args.subcommand != 'load_job':
      self.check_fin_args(parser)

    if self.args.find_mode is None and not (self.args.check_status or
                                            self.args.restart_machine or
                                            self.args.execute_cmd):
      parser.error('find_mode must be specified for a tuning run')

    if self.args.blacklist:
      self.check_blacklist(parser)

    args_check(self.args, parser)

    fin_session_steps = [
        'miopen_find_compile', 'miopen_find_eval', 'miopen_perf_compile',
        'miopen_perf_eval', 'get_applicability', 'find_compile', 'find_eval'
    ]
    has_fin = False
    if self.args.fin_steps:
      has_fin = all(x in fin_session_steps for x in self.args.fin_steps)

    if (self.args.update_applicability or has_fin) and not self.args.session_id:
      parser.error("session_id must be specified with this operation")

    self.dbt = MIOpenDBTables(session_id=self.args.session_id,
                              config_type=self.args.config_type)
    self.update_worker_type()

  def overwrite_common_args(self):
    """Overwrite common MIOpen_lib args with subcommand args"""
    if self.args.subcommand is not None:
      subc_dict = vars(self.args.get(self.args.subcommand))
      for sub_key in subc_dict:
        if sub_key in vars(self.args):
          self.args[sub_key] = subc_dict.get(sub_key)

  def check_fin_args(self, parser):
    """! Helper function for fin args
       @param parser The command line argument parser
        """
    valid_fin_steps = list(k for k in FinStep.__members__)
    if ',' in self.args.fin_steps:
      parser.error('Multiple fin_steps currently not supported')
    f_steps = self.args.fin_steps.split(',')
    self.args.fin_steps = f_steps
    for step in self.args.fin_steps:
      if step not in valid_fin_steps:
        parser.error(f"Supported fin steps are: {valid_fin_steps}")
    assert len(self.args.fin_steps) == 1

  def check_blacklist(self, parser):
    """! Helper function
       @param parser The command line argument parser
    """
    self.args.blacklist = self.args.blacklist.split(',')
    for sol in self.args.blacklist:
      if sol not in MIOPEN_ALG_LIST:
        parser.error("Incorrect blacklist value")

  def do_fin_work(self, gpu, f_vals):
    """! Helper function to execute job independendent fin work
      @param gpu Unique ID of the GPU
      @param f_vals Dict containing runtime information
    """
    kwargs = self.get_kwargs(gpu, f_vals)
    fin_worker = FinClass(**kwargs)

    if self.args.update_solvers:
      if not fin_worker.get_solvers():
        self.logger.error('No solvers returned from Fin class')

    return True

  def launch_worker(self, gpu_idx, f_vals, worker_lst):
    """! Function to launch worker
      @param gpu_idx Unique ID of the GPU
      @param f_vals Dict containing runtime information
      @param worker_lst List containing worker instances
      @retturn ret Boolean value
    """
    # pylint: disable=too-many-branches
    worker = None
    kwargs = self.get_kwargs(gpu_idx, f_vals)
    if self.args.update_applicability:
      kwargs['fin_steps'] = ['applicability']
      worker = FinClass(**kwargs)
      worker.start()
      worker_lst.append(worker)
      return True

    worker = WorkerInterface(**kwargs)
    ret = False
    if self.args.check_status:
      if not super().check_status(worker, f_vals["b_first"], gpu_idx,
                                  f_vals["machine"], self.args.docker_name):
        ret = True
    elif self.args.init_session:
      Session().add_new_session(self.args, worker)
    elif self.args.execute_cmd:
      # JD: Move the worker.exec_command to machine
      self.logger.info(self.args.execute_cmd)
      _, _, _ = worker.exec_command(self.args.execute_cmd + " 2>&1 ")

    return ret

  def compose_worker_list(self, machines):
    # pylint: disable=too-many-branches
    """! Helper function to compose worker_list
      @param res DB query return item containg available machines
      @param args The command line arguments
    """
    worker_lst = []
    fin_work_done = False
    for machine in machines:
      if self.args.restart_machine:
        machine.restart_server(wait=False)
        continue

      #fin_steps should only contain one step
      worker_ids = None
      if self.args.fin_steps and 'eval' in self.args.fin_steps[0]:
        worker_ids = machine.get_avail_gpus()
        if self.args.gpu_lim and self.args.gpu_lim < len(worker_ids):
          worker_ids = range(self.args.gpu_lim)
      else:
        worker_ids = super().get_num_procs(machine)

      if len(worker_ids) == 0:
        return None

      f_vals = super().get_f_vals(machine, worker_ids)

      if (self.args.update_solvers) and not fin_work_done:
        self.do_fin_work(0, f_vals)
        fin_work_done = True
        break

      for gpu_idx in worker_ids:
        self.logger.info('launch mid %u, proc %u', machine.id, gpu_idx)
        if not self.launch_worker(gpu_idx, f_vals, worker_lst):
          break

    return worker_lst

  def add_tables(self):
    ret_t = create_tables(get_miopen_tables())
    self.logger.info('DB creation successful: %s', ret_t)
    recreate_triggers(drop_miopen_triggers(), get_miopen_triggers())
    return True

  def run(self):
    # pylint: disable=duplicate-code
    """Main function to launch library"""
    res = None
    #self.parse_args()
    if self.args.add_tables:
      self.add_tables()
      return None

    if self.args.subcommand is not None and self.args.subcommand == 'import_configs':
      run_import_configs(self.args.import_configs, self.logger)
      return None

    if self.args.subcommand is not None and self.args.subcommand == 'load_job':
      run_load_job(self.args.load_job, self.logger)
      return None

    if self.args.subcommand is not None and self.args.subcommand == 'export_db':
      run_export_db(self.args.export_db, self.logger)
      return None

    if self.args.subcommand is not None and self.args.subcommand == 'update_golden':
      run_update_golden(self.args.update_golden, self.logger)
      return None

    machines = load_machines(self.args)
    res = self.compose_worker_list(machines)
    return res

  def get_envmt(self):
    """! Function to construct environment var
    """
    envmt = ["MIOPEN_LOG_LEVEL=4"]

    envmt.append("MIOPEN_SQLITE_KERN_CACHE=ON")
    envmt.append("MIOPEN_DEBUG_IMPLICIT_GEMM_FIND_ALL_SOLUTIONS=1")

    if self.args.find_mode:
      envmt.append(f"MIOPEN_FIND_MODE={self.args.find_mode}")

    if self.args.blacklist:
      bk_str = ", ".join([f"{arg}=0" for arg in self.args.blacklist])
      for bk_var in bk_str.split(','):
        envmt.append(bk_var)

    return envmt

  def get_kwargs(self, gpu_idx, f_vals, tuning=False):
    """! Helper function to set up kwargs for worker instances
      @param gpu_idx Unique ID of the GPU
      @param f_vals Dict containing runtime information
      @param args The command line arguments
    """
    kwargs = super().get_kwargs(gpu_idx, f_vals, tuning)
    kwargs['fin_steps'] = self.args.fin_steps
    kwargs['dynamic_solvers_only'] = self.args.dynamic_solvers_only
    kwargs['config_type'] = self.args.config_type
    kwargs['reset_interval'] = self.args.reset_interval

    return kwargs

  def get_jobs(self, find_state: str) -> bool:
    """Interface function to get jobs based on session and find_state"""
    job_rows: List[Tuple[SimpleDict, ...]]
    ids: list
    row: SimpleDict
    job_attr: List[str]
    try:
      job_attr = [column.name for column in inspect(self.dbt.job_table).c]
      job_attr.remove("insert_ts")
      job_attr.remove("update_ts")
    except NoInspectionAvailable as error:
      self.logger.warning("Ignoring error for init_session: %s", error)

    with DbSession() as session:
      job_rows = self.get_job_objs(session, find_state, self.args.label,
                                   self.dbt, job_attr, self.args.fin_steps)

      if not self.check_jobs_found(job_rows, find_state, self.args.session_id):
        return False

      ids = [row[0].id for row in job_rows]
      self.logger.info("%s jobs %s", find_state, ids)

    return job_rows

  def get_job_objs(self,
                   session: DbSession,
                   find_state: str,
                   label: str,
                   dbt: DBTablesInterface,
                   job_attr: List[str],
                   fin_steps: List[str] = None) -> List[Tuple[SimpleDict, ...]]:
    """Get list of job objects"""
    entries: List[Tuple[SimpleDict, ...]]
    conds: List[str] = [f"session={dbt.session.id}", "valid=1"]

    if label:
      conds.append(f"reason='{label}'")

    conds.append(f"retries<{self.max_job_retries}")
    conds.append(f"state='{find_state}'")

    entries = self.compose_work_objs(session, conds, dbt, job_attr, fin_steps)
    return entries

  def compose_work_objs(
      self,
      session: DbSession,
      conds: List[str],
      dbt: DBTablesInterface,
      job_attr: List[str],
      fin_steps: List[str] = None) -> List[Tuple[SimpleDict, SimpleDict]]:
    """Query a job list for update"""
    ret = []
    if fin_steps:
      conds.append(f"fin_step like '%{fin_steps[0]}%'")
    else:
      conds.append("fin_step='not_fin'")

    cond_str = ' AND '.join(conds)
    if cond_str:
      cond_str = f"WHERE {cond_str}"
    cond_str += " ORDER BY retries,config ASC"
    #try once without waiting for lock
    job_entries = gen_select_objs(session, job_attr,
                                  dbt.job_table.__tablename__, cond_str)

    entries = [(job,) for job in job_entries]
    if fin_steps:
      ret = self.compose_work_objs_fin(session, entries, dbt)
    else:
      ret = entries

    return ret

  def compose_work_objs_fin(self, session, job_entries, dbt):
    """Return jobs for fin work"""
    ret = []

    cfg_rel = {
        key: {
            'key': list(val.local_columns)[0].name,
            'ftble': str(list(val.remote_side)[0]).split('.', maxsplit=1)[0],
            'fkey': str(list(val.remote_side)[0]).split('.')[1]
        } for key, val in inspect(dbt.config_table).relationships.items()
    }

    if job_entries:
      id_str = ','.join([str(job[0].config) for job in job_entries])
      cfg_cond_str = f"where valid=1 and id in ({id_str})"
      cfg_attr = [column.name for column in inspect(dbt.config_table).c]
      cfg_entries = gen_select_objs(session, cfg_attr,
                                    dbt.config_table.__tablename__,
                                    cfg_cond_str)

      cfg_entries = self.attach_tensors(session, cfg_rel, cfg_entries)

      cfg_map = {cfg.id: cfg for cfg in cfg_entries}

      for job in job_entries:
        ret.append((job[0], cfg_map[job[0].config]))

    return ret

  def attach_tensors(self, session, cfg_rel, cfg_entries):
    """attach tensor relationship information to config entries"""
    for key, val in cfg_rel.items():
      rel_attr = [
          column.name
          for column in inspect(get_class_by_tablename(val['ftble'])).c
      ]
      val['fattr'] = rel_attr

    for cfg in cfg_entries:
      for key, val in cfg_rel.items():
        rel_val = getattr(cfg, val['key'])
        rel_cond_str = f"where {val['fkey']}={rel_val}"
        setattr(
            cfg, key,
            gen_select_objs(session, val['fattr'], val['ftble'],
                            rel_cond_str)[0])
    return cfg_entries

  def check_jobs_found(self, job_rows: List[SimpleDict], find_state: str,
                       session_id: int) -> bool:
    """check for end of jobs"""
    if not job_rows:
      # we are done
      self.logger.warning('No %s jobs found, session %s', find_state,
                          session_id)
      return False
    return True

  def get_job_tables(self, job_rows: List[Tuple[SimpleDict, ...]],
                     job_attr: List[str]) -> List[SimpleDict]:
    """find job tables in query results"""
    if has_attr_set(job_rows[0], job_attr):
      job_tables: List[SimpleDict] = job_rows
    else:
      job_i: int = 0
      tble: SimpleDict
      for i, tble in enumerate(job_rows[0]):
        if has_attr_set(tble, job_attr):
          job_i = i
          break
      job_tables = [row[job_i] for row in job_rows]

    return job_tables

  def update_worker_type(self):
    """Update the workers type that this library needs"""
    if self.args.fin_steps:
      if 'miopen_find_compile' in self.args.fin_steps \
      or 'miopen_perf_compile' in self.args.fin_steps:
        self.fetch_state = 'new'
        self.worker_type = "fin_build_worker"
      elif 'miopen_find_eval' in self.args.fin_steps or 'miopen_perf_eval' in self.args.fin_steps:
        self.fetch_state = 'compiled'
        self.worker_type = "fin_eval_worker"

    if self.args.update_applicability:
      self.worker_type = "fin_class_worker"
      self.fetch_state = "new"

  def has_tunable_operation(self):
    """Check if its a tuning loop operation"""
    if self.args.subcommand and "load_job" in self.args.subcommand:
      return False

    tuning_steps = ["miopen_find_compile", "miopen_find_eval"]
    return self.args.fin_steps and any(
        s in self.args.fin_steps for s in tuning_steps)
