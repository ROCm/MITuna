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
import os
import sys
import copy

sys.path.append("../tuna")
sys.path.append("tuna")

this_path = os.path.dirname(__file__)

from sqlalchemy.inspection import inspect

from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.machine_utility import load_machines
from tuna.miopen.db.tables import MIOpenDBTables
from utils import CfgImportArgs, LdJobArgs, GoFishArgs
from tuna.miopen.miopen_lib import MIOpen
from tuna.utils.logger import setup_logger
from tuna.miopen.utils.config_type import ConfigType
from tuna.utils.utility import serialize_job_config_row
from tuna.miopen.celery_tuning.celery_tasks import prep_kwargs
from tuna.machine import Machine
from tuna.libraries import Operation
from tuna.celery_app.celery_workers import launch_celery_worker
from tuna.celery_app.utility import get_q_name


def test_celery_workers():
  miopen = MIOpen()
  miopen.args = GoFishArgs()
  machine_lst = load_machines(miopen.args)
  machine = machine_lst[0]
  miopen.operation = Operation.COMPILE
  miopen.args.session_id = 1
  miopen.dbt = MIOpenDBTables(session_id=miopen.args.session_id,
                              config_type=ConfigType.convolution)
  miopen.args.enqueue_only = False
  db_name = os.environ['TUNA_DB_NAME']

  q_name = get_q_name(miopen, op_compile=True)
  assert q_name == f"compile_q_{db_name}_sess_1"
  q_name = get_q_name(miopen, op_eval=True)
  assert q_name == f"eval_q_{db_name}_sess_1"
  _, subp_list = miopen.prep_tuning()
  assert subp_list
  for subp in subp_list:
    print(subp.pid)
    subp.kill()

  miopen.args.enqueue_only = True
  _, subp_list = miopen.prep_tuning()
  assert subp_list == []
