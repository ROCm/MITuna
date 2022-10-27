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

import argparse
import sys
from multiprocessing import Value

from tuna.mituna_interface import MITunaInterface
from tuna.helper import print_solvers
from tuna.parse_args import TunaArgs, setup_arg_parser
from tuna.miopen.miopen_tables import FinStep
from tuna.metadata import MIOPEN_ALG_LIST
from tuna.miopen.fin_class import FinClass
from tuna.miopen.fin_builder import FinBuilder
from tuna.miopen.fin_eval import FinEvaluator
from tuna.worker_interface import WorkerInterface
from tuna.miopen.session import Session
from tuna.utils.utility import get_env_vars, compose_f_vals, get_kwargs
from tuna.utils.miopen_utility import load_machines
from tuna.libraries import Library


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
            TunaArgs.CONFIG_TYPE, TunaArgs.SESSION_ID
        ])

    parser.add_argument(
        '--find_mode',
        dest='find_mode',
        type=int,
        default=1,
        help='Set the MIOPEN_FIND_MODE environment variable for MIOpen',
        choices=[1, 3])
    parser.add_argument('--remote_machine',
                        dest='remote_machine',
                        action='store_true',
                        default=False,
                        help='Run the process on a network machine')
    parser.add_argument('-l',
                        '--label',
                        dest='label',
                        type=str,
                        default=None,
                        help='Specify label for jobs')
    parser.add_argument('--ticket',
                        dest='ticket',
                        type=str,
                        default=None,
                        help='Specify tuning ticket number')
    parser.add_argument('--docker_name',
                        dest='docker_name',
                        type=str,
                        default='miopentuna',
                        help='Select a docker to run on. (default miopentuna)')
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
    parser.add_argument('-m',
                        '--machines',
                        dest='machines',
                        type=str,
                        default=None,
                        required=False,
                        help='Specify machine ids to use, comma separated')
    parser.add_argument('-i',
                        '--reset_interval',
                        type=int,
                        dest='reset_interval',
                        required=False,
                        help='Restart interval for job in hours.')

    group = parser.add_mutually_exclusive_group()
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
    group.add_argument('-r',
                       '--restart',
                       dest='restart_machine',
                       action='store_true',
                       default=False,
                       help='Restart machines')
    group.add_argument('-s',
                       '--status',
                       dest='check_status',
                       action='store_true',
                       default=False,
                       help='Check the status of machines')

    group.add_argument('-d',
                       '--docker_exec',
                       dest='execute_docker_cmd',
                       type=str,
                       default=None,
                       help='execute in a docker on each machine')
    group.add_argument('-e',
                       '--exec',
                       dest='execute_cmd',
                       type=str,
                       default=None,
                       help='execute on each machine')

    self.clean_args()
    args = parser.parse_args()
    if len(sys.argv) == 1:
      parser.print_help()
      sys.exit(-1)

    if args.list_solvers:
      print_solvers()
      raise ValueError('Printing solvers...')

    if args.fin_steps:
      self.check_fin_args(args, parser)

    if args.find_mode is None and not (args.check_status or args.restart_machine
                                       or args.execute_cmd or
                                       args.execute_docker_cmd):
      parser.error('find_mode must be specified for a tuning run')

    if args.blacklist:
      self.check_blacklist(args, parser)

    if args.machines is not None:
      args.machines = [int(x) for x in args.machines.split(',')
                      ] if ',' in args.machines else [int(args.machines)]

    args.local_machine = not args.remote_machine

    if args.init_session and not args.label:
      parser.error(
          "When setting up a new tunning session the following must be specified: "\
          "label.")

    fin_session_steps = [
        'miopen_find_compile', 'miopen_find_eval', 'miopen_perf_compile',
        'miopen_perf_eval', 'get_applicability', 'find_compile', 'find_eval'
    ]
    has_fin = False
    if args.fin_steps:
      has_fin = all(x in fin_session_steps for x in args.fin_steps)

    if (args.update_applicability or has_fin) and not args.session_id:
      parser.error("session_id must be specified with this operation")

    return args

  def clean_args(self):
    if 'MIOPEN' in sys.argv:
      sys.argv.remove('MIOPEN')
    if 'miopen' in sys.argv:
      sys.argv.remove('miopen')

  def check_fin_args(self, args, parser):
    """! Helper function for fin args
       @param args The command line arguments
       @param parser The command line argument parser
    """
    valid_fin_steps = list(k for k in FinStep.__members__)
    if ',' in args.fin_steps:
      parser.error('Multiple fin_steps currently not supported')
    f_steps = args.fin_steps.split(',')
    args.fin_steps = f_steps
    for step in args.fin_steps:
      if step not in valid_fin_steps:
        parser.error(f"Supported fin steps are: {valid_fin_steps}")
    assert len(args.fin_steps) == 1

  def check_blacklist(self, args, parser):
    """! Helper function
       @param args The command line arguments
       @param parser The command line argument parser
    """
    args.blacklist = args.blacklist.split(',')
    for sol in args.blacklist:
      if sol not in MIOPEN_ALG_LIST:
        parser.error("Incorrect blacklist value")

  def do_fin_work(self, args, gpu, f_vals):
    """! Helper function to execute job independendent fin work
      @param args The command line arguments
      @param gpu Unique ID of the GPU
      @param f_vals Dict containing runtime information
    """
    kwargs = get_kwargs(gpu, f_vals, args)
    fin_worker = FinClass(**kwargs)

    if args.update_solvers:
      if not fin_worker.get_solvers():
        self.logger.error('No solvers returned from Fin class')

    return True

  def launch_worker(self, gpu_idx, f_vals, worker_lst, args):
    """! Function to launch worker
      @param gpu_idx Unique ID of the GPU
      @param f_vals Dict containing runtime information
      @param worker_lst List containing worker instances
      @param args The command line arguments
      @retturn ret Boolean value
    """
    # pylint: disable=too-many-branches
    worker = None
    kwargs = get_kwargs(gpu_idx, f_vals, args)

    if args.fin_steps:
      if 'miopen_find_compile' in args.fin_steps or 'miopen_perf_compile' in args.fin_steps:
        kwargs['fetch_state'] = ['new']
        worker = FinBuilder(**kwargs)
      elif 'miopen_find_eval' in args.fin_steps or 'miopen_perf_eval' in args.fin_steps:
        kwargs['fetch_state'] = ['compiled']
        worker = FinEvaluator(**kwargs)
      else:
        raise ValueError('Unsupported fin step')
      worker.start()
      worker_lst.append(worker)
      return True
    if args.update_applicability:
      kwargs['fin_steps'] = ['applicability']
      worker = FinClass(**kwargs)
      worker.start()
      worker_lst.append(worker)
      return True

    worker = WorkerInterface(**kwargs)
    ret = False
    if args.check_status:
      if not super().check_status(worker, f_vals["b_first"], gpu_idx,
                                  f_vals["machine"], args.docker_name):
        ret = True
    elif args.init_session:
      Session().add_new_session(args, worker)
    elif args.execute_cmd:
      # JD: Move the worker.exec_command to machine
      self.logger.info(args.execute_cmd)
      _, _, _ = worker.exec_command(args.execute_cmd + " 2>&1 ")
      #log printed by exec_command
    elif args.execute_docker_cmd:
      super().execute_docker(worker, args.execute_docker_cmd, f_vals["machine"])

    return ret

  def compose_worker_list(self, res, args):
    # pylint: disable=too-many-branches
    """! Helper function to compose worker_list
      @param res DB query return item containg available machines
      @param args The command line arguments
    """
    worker_lst = []
    fin_work_done = False
    for machine in res:
      if args.restart_machine:
        machine.restart_server(wait=False)
        continue

      #fin_steps should only contain one step
      if args.fin_steps and 'eval' in args.fin_steps[0]:
        worker_ids = machine.get_avail_gpus()
      else:
        #determine number of processes by compute capacity
        env = get_env_vars()
        if env['slurm_cpus'] > 0:
          num_procs = int(env['slurm_cpus'])
        else:
          # JD: This sould be the responsibility of the machine class
          num_procs = int(machine.get_num_cpus())
        worker_ids = range(num_procs)

      if len(worker_ids) == 0:
        self.logger.error('num_procs must be bigger than zero to launch worker')
        self.logger.error('Cannot launch worker on machine: %s', machine.id)
        return None

      f_vals = compose_f_vals(args, machine)
      f_vals["num_procs"] = Value('i', len(worker_ids))

      if (args.update_solvers) and not fin_work_done:
        self.do_fin_work(args, 0, f_vals)
        fin_work_done = True
        break

      for gpu_idx in worker_ids:
        self.logger.info('launch mid %u, proc %u', machine.id, gpu_idx)
        if not self.launch_worker(gpu_idx, f_vals, worker_lst, args):
          break

    return worker_lst

  def run(self):
    """Main function to launch library"""
    res = None
    self.args = self.parse_args()
    res = load_machines(self.args)
    res = self.compose_worker_list(res, self.args)
    return res
