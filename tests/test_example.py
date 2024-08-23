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

from tuna.example.example_lib import Example
from utils import ExampleArgs
from tuna.utils.machine_utility import load_machines
from tuna.dbBase.sql_alchemy import DbSession
from tuna.example.session import SessionExample
from tuna.example.example_tables import Job
from tuna.example.load_job import add_jobs
from tuna.example.tables import ExampleDBTables


def test_example():
  example = Example()
  example.args = ExampleArgs()
  assert (example.add_tables())

  res = load_machines(example.args)
  res = example.compose_worker_list(res)
  with DbSession() as session:
    query = session.query(SessionExample)
    res = query.all()
    assert len(res) is not None

  #test load_job
  dbt = ExampleDBTables(session_id=None)
  example.args.init_session = False
  example.args.session_id = 1
  example.args.execute = True
  example.args.label = 'test_example'
  #assert num_jobs

  #testing execute rocminfo
  res = load_machines(example.args)
  res = example.compose_worker_list(res)


  example.
  num_jobs = add_jobs(example.args, dbt)
  
  #assert num_jobs
  with DbSession() as session:
    query = session.query(Job).filter(Job.session==1)\
                              .filter(Job.state=='completed')
    res = query.all()
    assert res

  return True
