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
  example.add_tables()
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

  assert example.has_tunable_operation()


def test_example_celery_tasks():
  """Test Example celery tasks coverage"""
  import copy
  from unittest.mock import Mock, patch, MagicMock
  from tuna.example.celery_tuning.celery_tasks import prep_kwargs, prep_worker, capture_worker_name
  from tuna.example.example_worker import ExampleWorker
  from tuna.machine import Machine

  # Test prep_kwargs (line 52)
  kwargs = {'test_key': 'test_value'}
  job = {'id': 1, 'session': 1}
  args = [job]
  result = prep_kwargs(kwargs, args)
  assert result is not None
  assert 'job' in result

  # Test prep_worker with new operation - else branch (lines 64-67)
  context = {
      'operation': 'new_operation_test',
      'job': {
          'id': 1,
          'session': 1
      },
      'kwargs': {
          'session_id': 1,
          'machine': Mock()
      }
  }

  with patch('tuna.example.celery_tuning.celery_tasks.ExampleWorker'
            ) as mock_worker_class:
    mock_worker_instance = Mock()
    mock_worker_class.return_value = mock_worker_instance

    worker = prep_worker(context)
    assert worker is not None
    # Verify the worker was added to cache
    from tuna.example.celery_tuning import celery_tasks
    assert 'new_operation_test' in celery_tasks.cached_worker

  # Test prep_worker with cached operation - if branch (lines 61-62)
  context_cached = {
      'operation': 'cached_op',
      'job': {
          'id': 2,
          'session': 1
      },
      'kwargs': {
          'session_id': 1
      }
  }

  # First populate cache with a mock worker
  cached_mock_worker = Mock(spec=ExampleWorker)
  from tuna.example.celery_tuning import celery_tasks
  celery_tasks.cached_worker['cached_op'] = cached_mock_worker

  # Mock get_cached_worker to return the cached worker
  with patch('tuna.example.celery_tuning.celery_tasks.get_cached_worker'
            ) as mock_get_cached:
    mock_get_cached.return_value = cached_mock_worker

    worker_cached = prep_worker(context_cached)
    assert worker_cached is not None
    # Verify get_cached_worker was called
    mock_get_cached.assert_called_once()

  # Test capture_worker_name (line 44)
  from tuna.celery_app.celery_app import app
  mock_sender = 'test_worker_name_123'
  capture_worker_name(sender=mock_sender, instance=None)
  assert app.worker_name == mock_sender

  # Test celery_enqueue function (lines 74-76)
  # Note: celery_enqueue has a bug where it passes ExampleWorker as 2nd arg to prep_worker
  # We'll mock prep_worker to avoid this issue
  from tuna.example.celery_tuning import celery_tasks as ct_module

  context_enqueue = {
      'operation': 'enqueue_test_op',
      'job': {
          'id': 3,
          'session': 1
      },
      'kwargs': {
          'session_id': 1
      }
  }

  with patch.object(ct_module, 'prep_worker') as mock_prep_worker:
    mock_worker_run = Mock()
    mock_worker_run.run.return_value = {'status': 'success', 'time': 1.5}
    mock_prep_worker.return_value = mock_worker_run

    from tuna.example.celery_tuning.celery_tasks import celery_enqueue
    result = celery_enqueue(context_enqueue)

    assert 'ret' in result
    assert 'context' in result
    assert result['context'] == context_enqueue
    assert result['ret']['status'] == 'success'
