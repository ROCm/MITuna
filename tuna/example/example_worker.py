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

from tuna.worker_interface import WorkerInterface


class ExampleWorker(WorkerInterface):
  """ The Example class implementes the worker class. Its purpose is to run a command. It picks up
  new jobs and when completed, sets the state to compiled. """

  def close_job(self):
    """mark a job complete"""
    self.set_job_state('compiled')

  def step(self):
    """Main functionality of the builder class. It picks up jobs in new state and compiles them"""

    if not self.get_job("new", "compile_start", True):
      sleep(random.randint(1, 10))
      return False

    self.logger.info('Acquired new job: job_id=%s', self.job.id)
    self.set_job_state('compiling')
    cmd_output = self.run_cmd()

    failed_job = True
    result_str = ''
    if cmd_output:
      failed_job = False

    if failed_job:
      self.set_job_state('errored', result=result_str)
    else:
      self.set_job_state('compiled', result=result_str)
    return True

  def run_cmd(self):
    """Run a command"""
    cmd = []

    env_str = " ".join(self.envmt)
    cmd.append(env_str)
    cmd.append(' /opt/rocm/bin/rocminfo')

    _, out = super().run_command(cmd)

    return out
