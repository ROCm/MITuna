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
from os.path import exists
import sys
import json
import os
import tempfile

from dummy_machine import DummyMachine
from tuna.miopen.utils.config_type import ConfigType
from multiprocessing import Value, Lock, Queue
from tuna.utils.metadata import LOG_TIMEOUT
from tuna.miopen.worker.fin_class import FinClass

sys.path.append("../tuna")
sys.path.append("tuna")
this_path = os.path.dirname(__file__)


def test_set_all_configs():
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
      'fin_steps': ['applicability'],
      'use_tuner': False,
      'job_queue': Queue(),
      'queue_lock': Lock(),
      'fetch_state': {'compiled'},
      'end_jobs': e,
      'config_type': ConfigType.batch_norm,
      'session_id': 1
  }

  fin_worker = FinClass(**kwargs)
  bn_file = "{0}/../utils/test_files/bn_configs_rows.txt".format(this_path)
  db = json.load(open(bn_file))
  #no db connection, set_all_configs returns False
  assert (fin_worker._FinClass__create_dumplist() == False)
  for row in db['bn_configs']:
    fin_worker.all_configs.append(row)
  assert (fin_worker._FinClass__compose_fin_list())
  _, filename = tempfile.mkstemp()
  assert (fin_worker._FinClass__dump_json(filename))
  assert (exists(filename))
  fin_input = json.load(open(filename))
  sample1 = fin_input[0]
  assert (sample1['steps'] == ['applicability'])
  assert (sample1['config_tuna_id'] == 1)
  assert (sample1['config']['forw'] == 1)
  assert (sample1['config']['alpha'] == 1)
  assert (sample1['config']['cmd'] == 'bnorm')
  assert (sample1['config']['out_layout'] == 'NCHW')
  assert (sample1['config']['in_layout'] == 'NHWC')
  assert (sample1['config']['in_channels'] == 32)

  sample2 = fin_input[3]
  assert (sample2['steps'] == ['applicability'])
  assert (sample2['config_tuna_id'] == 4)
  assert (sample2['config']['verify'] == 1)
  assert (sample2['config']['alpha'] == 1)
  assert (sample2['config']['cmd'] == 'bnorm')
  assert (sample2['config']['mode'] == 0)
  assert (sample2['config']['batchsize'] == 128)
  assert (sample2['direction'] == 2)

  sample3 = fin_input[5]
  assert (sample3['steps'] == ['applicability'])
  assert (sample3['config_tuna_id'] == 6)
  assert (sample3['config']['verify'] == 1)
  assert (sample3['config']['alpha'] == 1)
  assert (sample3['config']['cmd'] == 'bnorm')
  assert (sample3['config']['mode'] == 1)
  assert (sample3['config']['batchsize'] == 256)
  assert (sample3['direction'] == 4)
