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
#Dummy machine class for unit tests
from tuna.metadata import LOG_TIMEOUT
from tuna.machine import Machine


class DummyMachine:

  def __init__(self, _gpu_state):
    self.gpu_state = _gpu_state
    self.json_file = None
    self.port = None
    self.hostname = None
    self.arch = 'gfx908'
    self.num_cu = 120
    self.id = 1
    self.machine = Machine(local_machine=True)

  def set_gpu_state(self, _gpu_state):
    self.gpu_state = _gpu_state

  def chk_gpu_status(self, gpu_id=0):
    return self.gpu_state

  def write_file(self, filename, is_temp=False):
    self.json_file = filename
    return filename

  def restart_server(self, wait=True):
    pass

  def connect(self, abort=None):
    pass

  def exec_command(self, command, docker_name=None, timeout=LOG_TIMEOUT):
    ret_code, out, err = self.machine.exec_command(command, docker_name,
                                                   timeout)
    return ret_code, out, err
