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
from multiprocessing import Value, Lock, Queue

sys.path.append("../tuna")
sys.path.append("tuna")

this_path = os.path.dirname(__file__)

from tuna.fin_eval import FinEvaluator
from tuna.sql import DbCursor
from tuna.dbBase.sql_alchemy import DbSession
from dummy_machine import DummyMachine


def test_fin_evaluator():
  res = None

  num_gpus = Value('i', 1)
  v = Value('i', 0)
  e = Value('i', 0)

  kwargs = {
      'machine': DummyMachine(False),
      'gpu_id': 0,
      'num_procs': num_gpus,
      'barred': v,
      'bar_lock': Lock(),
      'envmt': ["MIOPEN_LOG_LEVEL=7"],
      'reset_interval': False,
      'app_test': False,
      'label': 'tuna_pytest_fin_builder',
      'fin_steps': ['miopen_find_eval'],
      'use_tuner': False,
      'job_queue': Queue(),
      'queue_lock': Lock(),
      'fetch_state': ['compiled'],
      'end_jobs': e,
      'session_id': 1
  }

  # test get_job true branch
  fin_eval = FinEvaluator(**kwargs)
  ans = fin_eval.get_job('compiled', 'evaluating', False)
  assert (ans is True)

  with DbCursor() as cur:
    get_num_jobs = "select count(*) from conv_job where state = 'evaluating' and reason = 'tuna_pytest_fin_builder'"
    cur.execute(get_num_jobs)
    res = cur.fetchall()
    assert (res[0][0] == 1)

  # test get_fin_input
  file_name = fin_eval.get_fin_input()
  assert (file_name)

  # test check gpu with "bad" GPU
  # the job state will set back to "compiled" from "evaluating"
  fin_eval.check_gpu()
  with DbCursor() as cur:
    get_num_jobs = "select count(*) from conv_job where state = 'evaluating' and reason = 'tuna_pytest_fin_builder'"
    cur.execute(get_num_jobs)
    res = cur.fetchall()
    assert (res[0][0] == 0)

  # test check gpu with "good" GPU
  # the job state will remain 'evaluated'
  ans = fin_eval.get_job('compiled', 'evaluated', False)
  assert (ans is True)
  fin_eval.machine.set_gpu_state(True)
  fin_eval.check_gpu()
  with DbCursor() as cur:
    get_num_jobs = "select count(*) from conv_job where state = 'evaluated' and reason = 'tuna_pytest_fin_builder'"
    cur.execute(get_num_jobs)
    res = cur.fetchall()
    assert (res[0][0] == 1)

  with DbCursor() as cur:
    del_job = "delete from conv_job where state = 'evaluated' and reason = 'tuna_pytest_fin_builder'"
    cur.execute(del_job)

  #test get_job false branch
  fin_eval = FinEvaluator(**kwargs)
  ans = fin_eval.get_job('new', 'evaluating', False)
  assert (ans is False)
