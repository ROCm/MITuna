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

from utils import ExampleArgs, CfgImportArgs
from multiprocessing import Value

from tuna.utils.logger import setup_logger
from tuna.rocmlir.rocmlir_lib import RocMLIR
from tuna.machine import Machine
from tuna.dbBase.sql_alchemy import DbSession
from tuna.rocmlir.rocmlir_tables import SessionRocMLIR, ConvolutionJob, RocMLIRDBTables, clear_tables
from tuna.rocmlir.load_job import add_jobs
from tuna.rocmlir.import_configs import import_cfgs
from tuna.rocmlir.config_type import ConfigType
from tuna.rocmlir.rocmlir_worker import RocMLIRWorker

SAMPLE_CONV_CONFIGS = """
-F 1 -n 256 -c 1024 -H 14 -W 14 -k 2048 -y 1 -x 1 -p 0 -q 0 -u 2 -v 2 -l 1 -j 1 -m conv -g 1 -t 1
"""


def test_rocmlir():
  logger = setup_logger('test_rocmlir')
  dbt = RocMLIRDBTables(session_id=None, config_type=ConfigType.convolution)

  rocmlir = RocMLIR()
  assert rocmlir.add_tables()
  clear_tables(ConfigType.convolution)

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
  rocmlir.args.load_factor = 1
  rocmlir.args.config_type = ConfigType.convolution
  # Fake up a machine.  CI doesn't give access to GPU, thus no arch info.
  machine = Machine(hostname="test",
                    local_machine=True,
                    arch='gfx908',
                    arch_full='gfx908',
                    num_cu=12,
                    avail_gpus=[0])
  worker = RocMLIRWorker(config_type=rocmlir.args.config_type,
                         session_id=None,
                         machine=machine,
                         num_procs=Value('i', 0))
  session_id = SessionRocMLIR().add_new_session(rocmlir.args, worker)

  with DbSession() as session:
    query = session.query(SessionRocMLIR)
    res = query.all()
    assert len(res) is not None

  #test load_job
  rocmlir.args.init_session = False
  rocmlir.args.session_id = session_id
  rocmlir.args.execute = True
  rocmlir.args.config = 1
  num_jobs = add_jobs(rocmlir.args, dbt)
  assert num_jobs == 6

  workers = rocmlir.compose_worker_list([machine])
  assert workers
  for worker in workers:
    worker.join()

  # Deliberately did not supply ./bin/tuningRunner.py from rocMLIR, so we
  # should see six 'errored' jobs.
  with DbSession() as session:
    query = session.query(ConvolutionJob).filter(ConvolutionJob.session==session_id)\
                                         .filter(ConvolutionJob.state=='completed')
    res = query.all()
    assert len(res) == 0, \
      f"Should be 0 'completed' jobs and there are {len(res)}"
    # Because rocMLIR is not in path, error
    query = session.query(ConvolutionJob).filter(ConvolutionJob.session==session_id)\
                                         .filter(ConvolutionJob.state=='error')
    res = query.all()
    assert len(res) == 6, f"Should be 6 'error' jobs and there are {len(res)}"

  return True
