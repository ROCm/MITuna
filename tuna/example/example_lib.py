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
"""Example library, integrated with MITuna, runs 'rocminfo' cmd"""

import sys
import argparse

from typing import Dict, Any, List, Optional
from tuna.mituna_interface import MITunaInterface
from tuna.parse_args import TunaArgs, setup_arg_parser, args_check
from tuna.utils.miopen_utility import load_machines
from tuna.machine import Machine

from tuna.libraries import Library
from tuna.utils.db_utility import create_tables
from tuna.example.example_tables import get_tables
from tuna.example.example_worker import ExampleWorker
from tuna.example.session import SessionExample


class Example(MITunaInterface):
  """Class to support an example of 'romcinfo' run"""

  def __init__(self):
    super().__init__(library=Library.EXAMPLE)
    self.args: argparse.Namespace = None

  def parse_args(self) -> None:
    # pylint: disable=too-many-statements
    """Function to parse arguments"""
    parser: argparse.ArgumentParser
    parser = setup_arg_parser('Example library integrated with MITuna', [
        TunaArgs.ARCH, TunaArgs.NUM_CU, TunaArgs.VERSION, TunaArgs.SESSION_ID,
        TunaArgs.MACHINES, TunaArgs.REMOTE_MACHINE, TunaArgs.LABEL,
        TunaArgs.RESTART_MACHINE, TunaArgs.DOCKER_NAME
    ])
    group: argparse._MutuallyExclusiveGroup = parser.add_mutually_exclusive_group(
    )
    group.add_argument('--add_tables',
                       dest='add_tables',
                       action='store_true',
                       help='Add Example library specific tables')

    group.add_argument(
        '-e',
        '--execute',
        dest='execute',
        action='store_true',
        help='Run jobs from the job tables based on arch, num_cu and session_id'
    )

    group.add_argument('--init_session',
                       action='store_true',
                       dest='init_session',
                       help='Set up a new tuning session.')

    self.args = parser.parse_args()
    if len(sys.argv) == 1:
      parser.print_help()
      sys.exit(-1)

    args_check(self.args, parser)

  def launch_worker(self, gpu_idx: int, f_vals: Dict[str, Any], \
                    worker_lst: List[ExampleWorker]) -> bool:
    """! Function to launch worker
      @param gpu_idx Unique ID of the GPU
      @param f_vals Dict containing runtime information
      @param worker_lst List containing worker instances
      @return Boolean value
    """

    kwargs: Dict[str, Any] = self.get_kwargs(gpu_idx, f_vals)
    worker: ExampleWorker = ExampleWorker(**kwargs)
    if self.args.init_session:
      SessionExample().add_new_session(self.args, worker)
      return False

    worker.start()
    worker_lst.append(worker)
    return True

  def compose_worker_list(self, machines) -> Optional[List[ExampleWorker]]:
    # pylint: disable=too-many-branches
    """! Helper function to compose worker_list
      @param machines list of available machine objects
      @returns list of worker objects
    """
    worker_lst: List[ExampleWorker] = []
    for machine in machines:
      if self.args.restart_machine:
        machine.restart_server(wait=False)
        continue

      #determine number of processes by compute capacity
      # pylint: disable=duplicate-code
      worker_ids: List = super().get_num_procs(machine)
      if len(worker_ids) == 0:
        return None

      f_vals: Dict[str, Any] = super().get_f_vals(machine, worker_ids)

      for gpu_idx in worker_ids:
        self.logger.info('launch mid %u, proc %u', machine.id, gpu_idx)
        if not self.launch_worker(gpu_idx, f_vals, worker_lst):
          break

    return worker_lst

  def add_tables(self) -> bool:
    """Generates the library specific schema to the connected SQL server."""
    ret_t: bool = create_tables(get_tables())
    self.logger.info('DB creation successful: %s', ret_t)

    return True

  def run(self) -> Optional[List[ExampleWorker]]:
    # pylint: disable=duplicate-code
    """Main run function of example_lib"""
    res: Optional[List[ExampleWorker]]
    self.parse_args()
    if self.args.add_tables:
      self.add_tables()
      return None
    machines: List[Machine] = load_machines(self.args)
    res = self.compose_worker_list(machines)
    return res

  def get_envmt(self) -> List[str]:
    # pylint: disable=unused-argument
    """! Function to construct environment var
    """
    envmt: List[str] = []
    return envmt

  def get_kwargs(self, gpu_idx: int, f_vals: Dict[str, Any]) -> Dict[str, Any]:
    """! Helper function to set up kwargs for worker instances
      @param gpu_idx Unique ID of the GPU
      @param f_vals Dict containing process specific runtime information
    """
    kwargs: Dict[str, Any] = super().get_kwargs(gpu_idx, f_vals)

    return kwargs
