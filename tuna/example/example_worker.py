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
from typing import Dict, Any, List
from tuna.worker_interface import WorkerInterface
from tuna.example.tables import ExampleDBTables


class ExampleWorker(WorkerInterface):
  """ The Example class implements the worker class. Its purpose is to run a command
  and return the output."""

  def __init__(self, **kwargs: Dict[str, Any]) -> None:
    """Constructor"""
    self.dbt: ExampleDBTables = None
    super().__init__(**kwargs)
    self.set_db_tables()

  def set_db_tables(self) -> None:
    """Initialize tables"""
    self.dbt = ExampleDBTables(session_id=self.session_id)

  def step(self) -> bool:
    """Function to execute custom command and return result for tuning"""

    cmd_output = self.run_cmd()

    return cmd_output

  def run_cmd(self) -> str:
    """Run the actual workload"""
    cmd: List = []
    out: str

    env_str: str = " ".join(self.envmt)
    cmd.append(env_str)
    cmd.append(' /opt/rocm/bin/rocminfo')

    _, out = super().run_command(cmd)

    return out
