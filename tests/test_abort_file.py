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

from tuna.miopen.fin_builder import FinBuilder
from tuna.machine import Machine
from tuna.sql import DbCursor
from tuna.config_type import ConfigType
from utils import CfgImportArgs, LdJobArgs
from tuna.miopen.tables import MIOpenDBTables
from tuna.import_configs import import_cfgs
from tuna.db_tables import connect_db
from tuna.miopen.miopen_tables import ConvolutionJob
from load_job import test_tag_name as tag_name_test, add_jobs
from utils import add_test_session
from tuna.dbBase.sql_alchemy import DbSession


def test_abort():
  #import configs
  session_id = add_test_session()
  args = CfgImportArgs()
  args.tag = 'test_builder'
  args.mark_recurrent = True
  args.file_name = f"{this_path}/../utils/recurrent_cfgs/alexnet_4jobs.txt"

  dbt = MIOpenDBTables(session_id=session_id, config_type=args.config_type)
  counts = import_cfgs(args, dbt)

  #load jobs
  job_list = []
  for i in list(range(4)):
    job_list.append(ConvolutionJob())
  for i in range(len(job_list)):
    print(i)
    job_list[i].reason = 'tuna_pytest_abort'
    job_list[i].tag = 'test_abort'
    job_list[i].fin_steps = ['miopen_find_compile', 'miopen_find_eval']
    job_list[i].session = session_id
    job_list[i].solver = i + 1
    job_list[i].config = i + 1
  with DbSession() as session:
    for job in job_list:
      session.add(job)
    session.commit()
  num_jobs = len(job_list)

  connect_db()
  dbt = MIOpenDBTables(session_id=session_id, config_type=args.config_type)
  if args.tag:
    try:
      tag_name_test(args.tag, dbt)
    except ValueError as terr:
      print(terr)

  hostname = socket.gethostname()
  m = Machine(hostname=hostname, local_machine=True)
  arch = m.arch = 'gfx908'
  num_gpus = Value('i', 4)
  v = Value('i', 0)
  e = Value('i', 0)

  for gpu_idx in range(0, 4):
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
        'label': 'tuna_pytest_abort',
        'use_tuner': False,
        'job_queue': Queue(),
        'queue_lock': Lock(),
        'end_jobs': e,
        'config_type': ConfigType.convolution,
        'session_id': session_id
    }

  w = FinBuilder(**kwargs)

  #creating abort file just before we execute
  arch_abort = '/tmp/miopen_abort_{}'.format(arch)
  if not os.path.exists(arch_abort):
    os.mknod(arch_abort)

  w.run()

  #checking that no job where actually run due to abort_file_arch being present
  with DbCursor() as cur:
    get_jobs = f"SELECT count(*) from conv_job where reason='tuna_pytest_abort' and state='new' and session={session_id};"
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
    get_jobs = f"SELECT count(*) from conv_job where reason='tuna_pytest_abort' and state='new' and session={session_id};"
    cur.execute(get_jobs)
    res = cur.fetchall()
    print(res)
    assert (res[0][0] == num_jobs)
  os.remove('/tmp/miopen_abort_mid_{}'.format(m.id))
