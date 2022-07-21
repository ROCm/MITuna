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
#import pytest
from multiprocessing import Value, Lock, Queue

sys.path.append("../tuna")
sys.path.append("tuna")

this_path = os.path.dirname(__file__)

from tuna.builder import Builder
from tuna.machine import Machine
from tuna.sql import DbCursor
from tuna.tables import ConfigType


def add_job():
  find_configs = "SELECT count(*), tag FROM conv_config_tags WHERE tag='test_builder' GROUP BY tag"

  del_q = "DELETE FROM conv_job WHERE reason = 'tuna_pytest'"
  ins_q = "INSERT INTO conv_job(config, state, solver, valid, reason, session) \
        SELECT conv_config_tags.config, 'new', NULL, 1, 'tuna_pytest', 1 \
        FROM conv_config_tags WHERE conv_config_tags.tag LIKE 'test_builder'"

  print(ins_q)
  with DbCursor() as cur:
    cur.execute(find_configs)
    res = cur.fetchall()
    if len(res) == 0:
      add_cfg = "{0}/../tuna/import_configs.py -f {0}/../utils/recurrent_cfgs/alexnet_4jobs.txt -t test_builder -C convolution".format(
          this_path)
      os.system(add_cfg)

    cur.execute(del_q)
    cur.execute(ins_q)


def test_builder():
  res = None
  with DbCursor() as cur:
    select_text = "SELECT id, hostname, avail_gpus, user, password, port, arch, num_cu, sclk, mclk FROM machine WHERE available = TRUE LIMIT 1"
    cur.execute(select_text)
    res = cur.fetchall()
  assert (len(res) > 0)

  keys = {}
  for machine_id, hostname, avail_gpus, user, password, port, arch, num_cu, sclk, mclk in res:
    num_gpus = Value('i', len(avail_gpus.split(',')))
    v = Value('i', 0)
    e = Value('i', 0)

    keys = {
        'id': machine_id,
        'hostname': hostname,
        'user': user,
        'password': password,
        'port': port,
        'sclk': sclk,
        'mclk': mclk,
        'arch': arch,
        'num_cu': num_cu,
        'avail_gpus': avail_gpus
    }

    m = Machine(**keys)
    for gpu_idx in m.avail_gpus:
      w = None

      kwargs = {
          'machine': m,
          'gpu_id': gpu_idx,
          'num_procs': num_gpus,
          'barred': v,
          'bar_lock': Lock(),
          'envmt': ["MIOPEN_LOG_LEVEL=7"],
          'reset_interval': False,
          'app_test': False,
          'label': 'tuna_pytest',
          'use_tuner': False,
          'job_queue': Queue(),
          'queue_lock': Lock(),
          'end_jobs': e,
          'config_type': ConfigType.convolution,
          'session_id': 1
      }

    w = Builder(**kwargs)
    add_job()

    num_jobs = 0
    with DbCursor() as cur:
      get_jobs = "SELECT count(*) from conv_job where reason='tuna_pytest' and state='new';"
      cur.execute(get_jobs)
      res = cur.fetchall()
      print(res)
      assert (res[0][0] > 0)
      num_jobs = res[0][0]

    #creating abort file just before we execute
    arch_abort = '/tmp/miopen_abort_{}'.format(arch)
    if not os.path.exists(arch_abort):
      os.mknod(arch_abort)

    w.run()

    #checking that no job where actually run due to abort_file_arch being present
    with DbCursor() as cur:
      get_jobs = "SELECT count(*) from conv_job where reason='tuna_pytest' and state='new';"
      cur.execute(get_jobs)
      res = cur.fetchall()
      print(res)
      assert (res[0][0] == num_jobs)
    os.remove(arch_abort)

    #creating file for abort by mid
    if not os.path.exists('/tmp/miopen_abort_mid_{}'.format(m.id)):
      os.mknod('/tmp/miopen_abort_mid_{}'.format(m.id))
    w.run()

    #checking that no job where actually run due to abort_file_mid being present
    with DbCursor() as cur:
      get_jobs = "SELECT count(*) from conv_job where reason='tuna_pytest' and state='new';"
      cur.execute(get_jobs)
      res = cur.fetchall()
      print(res)
      assert (res[0][0] == num_jobs)
    os.remove('/tmp/miopen_abort_mid_{}'.format(m.id))
