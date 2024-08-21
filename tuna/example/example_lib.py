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
from tuna.utils.machine_utility import load_machines
from tuna.machine import Machine

from tuna.libraries import Library
from tuna.utils.db_utility import create_tables, gen_select_objs
from tuna.example.example_tables import get_tables
from tuna.example.example_worker import ExampleWorker
from tuna.example.session import SessionExample
from tuna.example.tables import ExampleDBTables
from tuna.libraries import Operation

Q_NAME = None


class Example(MITunaInterface):
  """Class to support an example of 'romcinfo' run"""

  def __init__(self):
    super().__init__(library=Library.EXAMPLE)
    self.args: argparse.Namespace = None
    self.operation = None
    self.set_state = None

  def parse_args(self) -> None:
    # pylint: disable=too-many-statements
    """Function to parse arguments"""
    parser: argparse.ArgumentParser
    parser = setup_arg_parser('Example library integrated with MITuna', [
        TunaArgs.ARCH, TunaArgs.NUM_CU, TunaArgs.VERSION, TunaArgs.SESSION_ID,
        TunaArgs.MACHINES, TunaArgs.REMOTE_MACHINE, TunaArgs.LABEL,
        TunaArgs.RESTART_MACHINE, TunaArgs.DOCKER_NAME, TunaArgs.ENQUEUE_ONLY,
        TunaArgs.SHUTDOWN_WORKERS
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
    if self.args.execute and self.args.enqueue_only:
      parser.error('--operation and --enqueue_only are mutually exclusive')

    self.dbt = ExampleDBTables(session_id=self.args.session_id)
    self.update_operation()

  def update_operation(self):
    """Set worker operation type"""
    if not self.args.execute:
      self.operation = Operation.COMPILE
      self.fetch_state.add('new')
      self.set_state = 'running'

  def has_tunable_operation(self):
    """Check if tunable operation is set"""
    if self.args is None:
      self.parse_args()
    return self.operation is not None


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

  def get_kwargs(self,
                 gpu_idx: int,
                 f_vals: Dict[str, Any],
                 tuning=False) -> Dict[str, Any]:
    """! Helper function to set up kwargs for worker instances
      @param gpu_idx Unique ID of the GPU
      @param f_vals Dict containing process specific runtime information
    """
    kwargs: Dict[str, Any] = super().get_kwargs(gpu_idx, f_vals, tuning)

    return kwargs

  def get_job_list(self, session, find_state=None, claim_num=None):
    """Get list of jobs"""
    job_list = gen_select_objs(session, self.get_job_attr(),
                               self.dbt.job_table.__tablename__,
                               "WHERE state='new'")
    return job_list

  def serialize_jobs(self, session, batch_jobs):
    """Return list of serialize jobs"""
    return [elem.to_dict() for elem in batch_jobs]

  def build_context(self, serialized_jobs):
    """Build context list for enqueue job"""
    context_list = []
    kwargs = self.get_context_items()
    for job in serialized_jobs:
      context = {
          'job': job,
          'operation': self.operation,
          'arch': self.dbt.session.arch,
          'num_cu': self.dbt.session.num_cu,
          'kwargs': kwargs,
      }
      context_list.append(context)

    return context_list

  def celery_enqueue_call(self, context, q_name, task_id=False):
    """Wrapper function for celery enqueue func"""
    Q_NAME = q_name  #pylint: disable=import-outside-toplevel,unused-variable,invalid-name,redefined-outer-name
    from tuna.example.celery_tuning.celery_tasks import celery_enqueue  #pylint: disable=import-outside-toplevel

    return celery_enqueue.apply_async((context,), queue=q_name, reply_to=q_name)

  def process_compile_results(self, session, fin_json, context):
    """Process result from fin_build worker"""
    self.logger.info('Pocessing compile results')
    self.logger.info(fin_json)

  def process_eval_results(self, session, fin_json, context):
    """Process fin_json result"""
    self.logger.info('Pocessing eval results')
    self.logger.info(fin_json)
