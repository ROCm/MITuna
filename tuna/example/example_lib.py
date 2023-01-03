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
from multiprocessing import Value

from tuna.mituna_interface import MITunaInterface
from tuna.helper import print_solvers
from tuna.parse_args import TunaArgs, setup_arg_parser
from tuna.miopen.miopen_tables import FinStep
from tuna.metadata import MIOPEN_ALG_LIST
from tuna.worker_interface import WorkerInterface
from tuna.miopen.session import Session
from tuna.utils.utility import get_env_vars, compose_f_vals, get_kwargs
from tuna.utils.miopen_utility import load_machines
from tuna.libraries import Library
from tuna.example.db_tables import create_tables
from tuna.example.example_tables import get_tables


class Example(MITunaInterface):
  """Class to support MIOpen specific tuning functionality"""

  def __init__(self):
    super().__init__(library=Library.EXAMPLE)
    self.args = None

  def parse_args(self):
    # pylint: disable=too-many-statements
    """Function to parse arguments"""
    parser = setup_arg_parser(
        'Run Performance Tuning on a certain architecture', [
            TunaArgs.ARCH, TunaArgs.NUM_CU, TunaArgs.VERSION,
            TunaArgs.CONFIG_TYPE, TunaArgs.SESSION_ID
        ])

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

    return args

  def launch_worker(self, gpu_idx, f_vals, worker_lst, args):
    """! Function to launch worker
      @param gpu_idx Unique ID of the GPU
      @param f_vals Dict containing runtime information
      @param worker_lst List containing worker instances
      @param args The command line arguments
      @retturn ret Boolean value
    """
    worker = WorkerInterface(**kwargs)
    if args.execute_cmd:
      self.logger.info(args.execute_cmd)
      _, _, _ = worker.exec_command(args.execute_cmd + " 2>&1 ")
    return True

  def compose_worker_list(self, res, args):
    # pylint: disable=too-many-branches
    """! Helper function to compose worker_list
      @param res DB query return item containg available machines
      @param args The command line arguments
    """
    worker_lst = []
    for machine in res:
      if args.restart_machine:
        machine.restart_server(wait=False)
        continue

      #determine number of processes by compute capacity
      env = get_env_vars()
      if env['slurm_cpus'] > 0:
        num_procs = int(env['slurm_cpus'])
      else:
        # JD: This sould be the responsibility of the machine class
        num_procs = int(machine.get_num_cpus() * .6)
      worker_ids = range(num_procs)

      if len(worker_ids) == 0:
        self.logger.error('num_procs must be bigger than zero to launch worker')
        self.logger.error('Cannot launch worker on machine: %s', machine.id)
        return None

      f_vals = compose_f_vals(args, machine)
      f_vals["num_procs"] = Value('i', len(worker_ids))

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

  def add_tables(self):
    ret_t = create_tables(get_tables())
    self.logger.info('DB creation successful: %s', ret_t)

    return True
