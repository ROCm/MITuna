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
import os
import sys
import socket
from multiprocessing import Value, Lock, Queue

sys.path.append("../tuna")
sys.path.append("tuna")

this_path = os.path.dirname(__file__)

from tuna.machine import Machine
from tuna.dbBase.sql_alchemy import DbSession
from tuna.worker_interface import WorkerInterface
from tuna.miopen.utils.session_utils import get_session_t
from utils import DummyArgs


def test_add_session():
  res = None

  num_gpus = Value('i', 1)
  v = Value('i', 0)
  e = Value('i', 0)
  docker_name = 'Dummy-Docker'
  hostname = socket.gethostname()
  machine = Machine(hostname=hostname, local_machine=True)

  kwargs = {
      'machine': machine,
      'gpu_id': 0,
      'num_procs': num_gpus,
      'barred': v,
      'bar_lock': Lock(),
      'envmt': ["MIOPEN_LOG_LEVEL=7"],
      'reset_interval': False,
      'app_test': False,
      'label': 'testing_add_session',
      'fin_steps': ['miopen_find_eval'],
      'use_tuner': False,
      'job_queue': Queue(),
      'queue_lock': Lock(),
      'fetch_state': ['compiled'],
      'end_jobs': e,
  }

  args = DummyArgs()
  args.add_session = True
  args.arch = 'gfx908'
  args.num_cu = 120
  args.reason = "testing_add_session"
  args.ticket = "JIRA-Dummy-123"
  args.label = "my_dummy_label"
  args.docker_name = docker_name
  args.solver_id = 1

  worker = WorkerInterface(**kwargs)
  sess_id = get_session_t().add_new_session(args, worker)
  print(f"session id: {sess_id}")
  assert (sess_id)

  with DbSession() as session:
    res = session.query(Session).filter(Session.id == sess_id).one()
    assert (res)
    assert (res.reason == "my_dummy_label")
    assert (res.rocm_v)
    assert (res.miopen_v)
    assert (res.docker == docker_name)
