#!/usr/bin/env python3
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
"""MIOpen class that holds MIOpen specifig  tuning functionality"""

import sys

from tuna.mituna_interface import MITunaInterface
from tuna.miopen.utils.helper import print_solvers
from tuna.parse_args import TunaArgs, setup_arg_parser, args_check
from tuna.miopen.db.mixin_tables import FinStep
from tuna.miopen.db.get_db_tables import get_miopen_tables
from tuna.miopen.utils.metadata import MIOPEN_ALG_LIST
from tuna.miopen.worker.fin_class import FinClass
from tuna.miopen.worker.fin_builder import FinBuilder
from tuna.miopen.worker.fin_eval import FinEvaluator
#from tuna.worker_interface import WorkerInterface
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


class MIOpen(MITunaInterface):
  """Class to support MIOpen specific tuning functionality"""

  def __init__(self):
    super().__init__(library=Library.MIOPEN)
    self.args = None

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

    if self.args.fin_steps:
      if 'miopen_find_compile' in self.args.fin_steps \
      or 'miopen_perf_compile' in self.args.fin_steps:
        kwargs['fetch_state'] = ['new']
        worker = FinBuilder(**kwargs)
      elif 'miopen_find_eval' in self.args.fin_steps or 'miopen_perf_eval' in self.args.fin_steps:
        kwargs['fetch_state'] = ['compiled']
        worker = FinEvaluator(**kwargs)
      else:
        raise ValueError('Unsupported fin step')
      worker.start()
      worker_lst.append(worker)
      return True
    if self.args.update_applicability:
      kwargs['fin_steps'] = ['applicability']
      worker = FinClass(**kwargs)
      worker.start()
      worker_lst.append(worker)
      return True

    #worker = WorkerInterface(**kwargs)
    worker = FinClass(**kwargs)
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
    self.parse_args()
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

  def get_kwargs(self, gpu_idx, f_vals):
    """! Helper function to set up kwargs for worker instances
      @param gpu_idx Unique ID of the GPU
      @param f_vals Dict containing runtime information
      @param args The command line arguments
    """
    if self.args.config_type is None:
      self.args.config_type = ConfigType.convolution

    kwargs = super().get_kwargs(gpu_idx, f_vals)
    kwargs['fin_steps'] = self.args.fin_steps
    kwargs['dynamic_solvers_only'] = self.args.dynamic_solvers_only
    kwargs['config_type'] = self.args.config_type
    kwargs['reset_interval'] = self.args.reset_interval

    return kwargs
