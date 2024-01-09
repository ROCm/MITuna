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
"""Builder class implements the worker interface. The purpose of this class is to run the
rocminfo command"""
from time import sleep
import random

from typing import Dict, Any, Optional, List
from tuna.worker_interface import WorkerInterface
from tuna.example.tables import ExampleDBTables


class ExampleWorker(WorkerInterface):
  """ The Example class implements the worker class. Its purpose is to run a command. It picks up
  new jobs and when completed, sets the state to completed. """

  def __init__(self, **kwargs: Dict[str, Any]) -> None:
    """Constructor"""
    self.dbt: ExampleDBTables = None
    super().__init__(**kwargs)
    self.set_db_tables()

  def set_db_tables(self) -> None:
    """Initialize tables"""
    self.dbt = ExampleDBTables(session_id=self.session_id)

  def step(self) -> bool:
    """Main functionality of the worker class. It picks up jobs in new state and executes them"""

    if not self.get_job({"new"}, "running", False):
      #Sleep in case of DB contention
      sleep(random.randint(1, 10))
      return False

    failed_job: bool = False
    self.logger.info('Acquired new job: job_id=%s', self.job.id)
    self.set_job_state('running')
    cmd_output: Optional[str] = None
    err_str: str = ''
    try:
      cmd_output = self.run_cmd()
    except ValueError as verr:
      self.logger.info(verr)
      failed_job = True
      err_str = str(verr)

    if failed_job:
      self.set_job_state('errored', result=err_str)
    else:
      self.set_job_state('completed', result=cmd_output)

    return True

  def run_cmd(self) -> str:
    """Run the actual workload"""
    cmd: List = []
    out: str

    env_str: str = " ".join(self.envmt)
    cmd.append(env_str)
    cmd.append(' /opt/rocm/bin/rocminfo')

    _, out = super().run_command(cmd)

    return out
