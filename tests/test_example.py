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
from time import sleep

sys.path.append("../tuna")
sys.path.append("tuna")

this_path = os.path.dirname(__file__)

from tuna.example.example_lib import Example
from utils import GoFishArgs, add_test_session
from utils import ExampleArgs
from tuna.utils.machine_utility import load_machines
from tuna.dbBase.sql_alchemy import DbSession
from tuna.example.session import SessionExample
from tuna.example.example_tables import Job
from tuna.example.load_job import add_jobs
from tuna.libraries import Operation
from tuna.example.tables import ExampleDBTables
from tuna.example.session import SessionExample
from tuna.celery_app.celery_workers import launch_worker_per_node
from tuna.celery_app.utility import get_q_name


def test_example():
  example = Example()
  example.args = ExampleArgs()
  example.args = GoFishArgs()
  example.args.label = 'tuna_pytest_example'
  example.args.session_id = add_test_session(label=example.args.label,
                                             session_table=SessionExample)
  example.operation = Operation.COMPILE
  example.args.arch = "gfx90a"
  example.args.num_cu = 104
  example.dbt = ExampleDBTables(session_id=example.args.session_id)

  machines = load_machines(example.args)
  res = example.compose_worker_list(machines)
  with DbSession() as session:
    query = session.query(SessionExample)
    res = query.all()
    assert len(res) is not None

  #test load_job
  example.args.init_session = False
  example.args.session_id = 1
  example.args.execute = True
  example.args.label = 'test_example'
  example.args.execute = True
  #assert num_jobs

  example.args.execute = None
  example.args.enqueue_only = True
  db_name = os.environ['TUNA_DB_NAME']
  _, subp_list = example.prep_tuning()
  assert subp_list == []


  cmd = f"celery -A tuna.celery_app.celery_app worker -l info -E -n tuna_HOSTNAME_sess_{example.args.session_id} -Q test_{db_name}"  #pylint: disable=line-too-long
  #testing launch_worker_per_node
  machine = machines[0]
  subp_list = launch_worker_per_node([machine], cmd, True)
  #wait for workers to finish launch
  sleep(5)
  assert subp_list

  for subp in subp_list:
    print(subp.pid)
    subp.kill()
