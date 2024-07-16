#!/usr/bin/env python3
###############################################################################
#
# MIT License
#
# Copyright (c) 2024 Advanced Micro Devices, Inc.
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
import json
import os
import sys
import copy

sys.path.append("../tuna")
sys.path.append("tuna")

from tuna.mituna_interface import MITunaInterface
from tuna.worker_interface import WorkerInterface
from utils import GoFishArgs, add_test_session
from tuna.miopen.miopen_lib import MIOpen
from tuna.utils.machine_utility import load_machines

this_path = os.path.dirname(__file__)


def test_mituna_interface():

  miopen = MIOpen()
  miopen.args = GoFishArgs()
  mituna = MITunaInterface()
  miopen.args.session_id = add_test_session(label=miopen.args.label)
  machine_lst = load_machines(miopen.args)
  machine = machine_lst[0]
  worker = WorkerInterface(**{
      'machine': machine,
      'session_id': miopen.args.session_id
  })

  try:
    foo = mituna.check_docker(worker, 'DoesNotExist')
  except Exception as exp:
    assert type(exp) == ValueError
