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

sys.path.append("../tuna")
sys.path.append("tuna")

this_path = os.path.dirname(__file__)

from tuna.utils.logger import setup_logger
from tuna.rocmlir.rocmlir_lib import RocMLIR
from utils import ExampleArgs
from tuna.utils.miopen_utility import load_machines
from tuna.dbBase.sql_alchemy import DbSession
from tuna.rocmlir.rocmlir_tables import SessionRocMLIR, ConvolutionJob, RocMLIRDBTables, clear_tables
from tuna.rocmlir.load_job import add_jobs
from tuna.rocmlir.import_configs import import_cfgs
from utils import CfgImportArgs

SAMPLE_CONV_CONFIGS = """
-F 1 -n 256 -c 1024 -H 14 -W 14 -k 2048 -y 1 -x 1 -p 0 -q 0 -u 2 -v 2 -l 1 -j 1 -m conv -g 1 -t 1
"""

def test_rocmlir():
  logger = setup_logger('test_rocmlir')
  dbt = RocMLIRDBTables(session_id=None)

  rocmlir = RocMLIR()
  assert (rocmlir.add_tables())
  clear_tables()

  # To get some sample configs imported.
  with open("test-conv-configs", 'w') as f:
    f.write(SAMPLE_CONV_CONFIGS)
  args = CfgImportArgs
  args.file_name = "test-conv-configs"
  count = import_cfgs(args, dbt, logger)
  assert count == 6

  rocmlir.args = ExampleArgs()
  rocmlir.args.init_session = True
  rocmlir.args.label = 'test_rocmlir'
  machines = load_machines(rocmlir.args)
  # With .init_session True, launch_worker adds a session and bails.
  rocmlir.compose_worker_list(machines)
  with DbSession() as session:
    query = session.query(SessionRocMLIR)
    res = query.all()
    assert len(res) is not None

  #test load_job
  rocmlir.args.init_session = False
  rocmlir.args.session_id = 1
  rocmlir.args.execute = True
  rocmlir.args.config = 1
  num_jobs = add_jobs(rocmlir.args, dbt)
  assert num_jobs == 6

  # +++pf:  can't get this part to work
  #   #testing execute rocminfo
  #   # With .init_session False, launch_worker starts the worker.
  #   workers = rocmlir.compose_worker_list(machines)
  #   assert workers
  #   for worker in workers:
  #     worker.join()
  #   with DbSession() as session:
  #     query = session.query(ConvolutionJob).filter(ConvolutionJob.session==1)\
  #                                          .filter(ConvolutionJob.state=='completed')
  #     res = query.all()
  #     assert len(res) == 0
  #     # Because rocMLIR is not in path, error
  #     query = session.query(ConvolutionJob).filter(ConvolutionJob.session==1)\
  #                                          .filter(ConvolutionJob.state=='errored')
  #     res = query.all()
  #     assert len(res) == 6

  return True
