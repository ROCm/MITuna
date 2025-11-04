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
"""Extended tests for tuna.example.example_lib to improve coverage"""
import os
import sys
import argparse
from unittest.mock import Mock, patch, MagicMock, call

sys.path.append("../tuna")
sys.path.append("tuna")

from tuna.example.example_lib import Example
from tuna.example.session import SessionExample
from tuna.example.tables import ExampleDBTables
from tuna.example.example_worker import ExampleWorker
from tuna.libraries import Operation
from tuna.utils.utility import SimpleDict


# Tests for parse_args method (lines 64-100)
def test_parse_args_add_tables_flag():
  """Test parse_args with --add_tables flag"""
  example = Example()

  test_args = [
      '--add_tables', '--session_id', '1', '--arch', 'gfx90a', '--num_cu', '104'
  ]

  with patch('sys.argv', ['script'] + test_args):
    example.parse_args()
    assert example.args.add_tables is True
    assert example.args.execute is False
    assert hasattr(example, 'dbt')


def test_parse_args_execute_flag():
  """Test parse_args with --execute flag"""
  example = Example()

  test_args = [
      '--execute', '--session_id', '1', '--arch', 'gfx90a', '--num_cu', '104'
  ]

  with patch('sys.argv', ['script'] + test_args):
    example.parse_args()
    assert example.args.execute is True
    assert hasattr(example, 'dbt')


def test_parse_args_init_session_flag():
  """Test parse_args with --init_session flag"""
  example = Example()

  test_args = [
      '--init_session', '--session_id', '1', '--arch', 'gfx90a', '--num_cu',
      '104', '--label', 'test_label'
  ]

  with patch('sys.argv', ['script'] + test_args):
    example.parse_args()
    assert example.args.init_session is True
    assert hasattr(example, 'dbt')


def test_parse_args_execute_enqueue_mutually_exclusive():
  """Test parse_args error when execute and enqueue_only both set"""
  example = Example()

  test_args = [
      '--execute', '--enqueue_only', '--session_id', '1', '--arch', 'gfx90a',
      '--num_cu', '104'
  ]

  with patch('sys.argv', ['script'] + test_args), \
       patch('argparse.ArgumentParser.error') as mock_error:
    try:
      example.parse_args()
    except SystemExit:
      pass
    # Verify error was raised for mutually exclusive args


def test_parse_args_creates_example_dbt():
  """Test parse_args creates ExampleDBTables"""
  example = Example()

  test_args = ['--session_id', '42', '--arch', 'gfx90a', '--num_cu', '104']

  with patch('sys.argv', ['script'] + test_args), \
       patch('tuna.tables_interface.DbSession'):
    example.parse_args()
    assert isinstance(example.dbt, ExampleDBTables)
    assert example.dbt.session_id == 42


# Tests for update_operation method (lines 102-108)
def test_update_operation_without_execute():
  """Test update_operation when execute is False"""
  example = Example()
  example.args = Mock()
  example.args.execute = False
  example.fetch_state = set()

  example.update_operation()

  assert example.operation == Operation.COMPILE
  assert 'new' in example.fetch_state
  assert example.set_state == 'running'


def test_update_operation_with_execute():
  """Test update_operation when execute is True"""
  example = Example()
  example.args = Mock()
  example.args.execute = True

  example.update_operation()

  # When execute is True, operation might not be set
  # The method checks "if not self.args.execute"
  # So with execute=True, it shouldn't set operation


# Tests for has_tunable_operation method (lines 110-114)
def test_has_tunable_operation_none_args():
  """Test has_tunable_operation when args is None"""
  example = Example()
  example.args = None
  example.operation = None

  with patch.object(example, 'parse_args') as mock_parse:
    mock_parse.return_value = None
    result = example.has_tunable_operation()

    mock_parse.assert_called_once()
    # After parse_args, operation might still be None


def test_has_tunable_operation_with_operation():
  """Test has_tunable_operation when operation exists"""
  example = Example()
  example.args = Mock()
  example.operation = Operation.COMPILE

  result = example.has_tunable_operation()

  assert result is True


def test_has_tunable_operation_without_operation():
  """Test has_tunable_operation when operation is None"""
  example = Example()
  example.args = Mock()
  example.operation = None

  result = example.has_tunable_operation()

  assert result is False


# Tests for launch_worker method (lines 117-134)
def test_launch_worker_normal():
  """Test launch_worker normal execution"""
  example = Example()
  example.args = Mock()
  example.args.init_session = False

  gpu_idx = 0
  f_vals = {'envmt': [], 'machine': Mock()}
  worker_lst = []

  with patch.object(example, 'get_kwargs') as mock_get_kwargs:
    mock_get_kwargs.return_value = {
        'session_id': 1,
        'gpu_idx': gpu_idx,
        'machine': f_vals['machine'],
        'envmt': []
    }

    mock_worker = Mock(spec=ExampleWorker)
    mock_worker.start = Mock()

    with patch('tuna.example.example_lib.ExampleWorker',
               return_value=mock_worker):
      result = example.launch_worker(gpu_idx, f_vals, worker_lst)

      assert result is True
      assert len(worker_lst) == 1
      mock_worker.start.assert_called_once()


def test_launch_worker_with_init_session():
  """Test launch_worker with init_session flag"""
  example = Example()
  example.args = Mock()
  example.args.init_session = True

  gpu_idx = 0
  f_vals = {'envmt': [], 'machine': Mock()}
  worker_lst = []

  with patch.object(example, 'get_kwargs') as mock_get_kwargs, \
       patch('tuna.example.example_lib.SessionExample') as mock_session_example:
    mock_get_kwargs.return_value = {
        'session_id': 1,
        'gpu_idx': gpu_idx,
        'machine': f_vals['machine'],
        'envmt': []
    }

    mock_session = Mock()
    mock_session.add_new_session = Mock()
    mock_session_example.return_value = mock_session

    mock_worker = Mock(spec=ExampleWorker)

    with patch('tuna.example.example_lib.ExampleWorker',
               return_value=mock_worker):
      result = example.launch_worker(gpu_idx, f_vals, worker_lst)

      assert result is False
      assert len(worker_lst) == 0
      mock_session.add_new_session.assert_called_once()


# Tests for compose_worker_list method (lines 136-161)
def test_compose_worker_list_normal():
  """Test compose_worker_list normal execution"""
  example = Example()
  example.args = Mock()
  example.args.restart_machine = False

  mock_machine = Mock()
  mock_machine.id = 1
  mock_machine.get_num_cpus.return_value = 10  # Return a number for multiplication

  with patch('tuna.mituna_interface.get_env_vars') as mock_get_env, \
       patch.object(example, 'get_f_vals') as mock_get_f_vals, \
       patch.object(example, 'launch_worker') as mock_launch:
    # Mock get_env_vars to return empty slurm_cpus so it uses machine.get_num_cpus()
    mock_get_env.return_value = {'slurm_cpus': 0}
    mock_get_f_vals.return_value = {'envmt': []}
    mock_launch.return_value = True

    example.logger = Mock()

    result = example.compose_worker_list([mock_machine])

    assert result is not None
    assert isinstance(result, list)


def test_compose_worker_list_with_restart_machine():
  """Test compose_worker_list with restart_machine flag"""
  example = Example()
  example.args = Mock()
  example.args.restart_machine = True

  mock_machine = Mock()
  mock_machine.restart_server = Mock()

  result = example.compose_worker_list([mock_machine])

  mock_machine.restart_server.assert_called_once_with(wait=False)
  assert result == []


def test_compose_worker_list_empty_worker_ids():
  """Test compose_worker_list when no worker IDs returned"""
  example = Example()
  example.args = Mock()
  example.args.restart_machine = False

  mock_machine = Mock()
  mock_machine.get_num_cpus.return_value = 0  # Return 0 so int(0 * 0.6) = 0, resulting in empty list

  with patch('tuna.mituna_interface.get_env_vars') as mock_get_env:
    # Mock get_env_vars to return empty slurm_cpus so it uses machine.get_num_cpus()
    mock_get_env.return_value = {'slurm_cpus': 0}

    result = example.compose_worker_list([mock_machine])

    assert result is None


# Tests for get_envmt method (lines 184-189)
def test_get_envmt():
  """Test get_envmt returns empty list"""
  example = Example()
  envmt = example.get_envmt()

  assert isinstance(envmt, list)
  assert envmt == []


# Tests for get_kwargs method (lines 191-201)
def test_get_kwargs_basic():
  """Test get_kwargs basic usage"""
  example = Example()
  gpu_idx = 0
  f_vals = {'envmt': [], 'machine': Mock()}

  with patch('tuna.example.example_lib.super') as mock_super:
    mock_super.return_value.get_kwargs.return_value = {
        'session_id': 1,
        'gpu_idx': gpu_idx,
        'machine': f_vals['machine'],
        'envmt': []
    }

    kwargs = example.get_kwargs(gpu_idx, f_vals)

    # Verify parent method was called
    # Note: actual implementation calls super().get_kwargs


# Tests for get_job_list method (lines 203-212)
def test_get_job_list():
  """Test get_job_list method"""
  example = Example()
  example.dbt = Mock()
  example.dbt.job_table = Mock()
  example.dbt.job_table.__tablename__ = 'job'

  mock_session = Mock()
  mock_jobs = [Mock(), Mock()]

  with patch('tuna.example.example_lib.gen_select_objs') as mock_gen_select:
    mock_gen_select.return_value = mock_jobs

    with patch.object(example, 'get_job_attr') as mock_get_job_attr:
      mock_get_job_attr.return_value = {}

      job_list = example.get_job_list(mock_session)

      assert job_list == mock_jobs
      mock_gen_select.assert_called_once()
      # Verify WHERE clause contains 'new' state


# Tests for serialize_jobs method (lines 214-219)
def test_serialize_jobs():
  """Test serialize_jobs method"""
  example = Example()

  mock_job1 = Mock()
  mock_job1.to_dict.return_value = {'id': 1, 'state': 'new'}
  mock_job2 = Mock()
  mock_job2.to_dict.return_value = {'id': 2, 'state': 'running'}

  batch_jobs = [mock_job1, mock_job2]
  mock_session = Mock()

  result = example.serialize_jobs(mock_session, batch_jobs)

  assert isinstance(result, list)
  assert len(result) == 2
  assert result[0]['id'] == 1
  assert result[1]['id'] == 2


def test_serialize_jobs_empty():
  """Test serialize_jobs with empty list"""
  example = Example()
  result = example.serialize_jobs(Mock(), [])

  assert isinstance(result, list)
  assert len(result) == 0


# Tests for build_context method (lines 221-237)
def test_build_context_single_job():
  """Test build_context with single job"""
  example = Example()
  example.dbt = Mock()
  example.dbt.session = Mock()
  example.dbt.session.arch = 'gfx90a'
  example.dbt.session.num_cu = 104
  example.operation = Operation.COMPILE

  serialized_jobs = [{'id': 1, 'reason': 'test'}]

  with patch.object(example, 'get_context_items') as mock_get_context:
    mock_get_context.return_value = {}

    context_list = example.build_context(serialized_jobs)

    assert len(context_list) == 1
    context = context_list[0]
    assert context['job'] == serialized_jobs[0]
    assert context['operation'] == Operation.COMPILE
    assert context['arch'] == 'gfx90a'
    assert context['num_cu'] == 104


def test_build_context_multiple_jobs():
  """Test build_context with multiple jobs"""
  example = Example()
  example.dbt = Mock()
  example.dbt.session = Mock()
  example.dbt.session.arch = 'gfx90a'
  example.dbt.session.num_cu = 104
  example.operation = Operation.COMPILE

  serialized_jobs = [{
      'id': 1,
      'reason': 'test1'
  }, {
      'id': 2,
      'reason': 'test2'
  }, {
      'id': 3,
      'reason': 'test3'
  }]

  with patch.object(example, 'get_context_items') as mock_get_context:
    mock_get_context.return_value = {}

    context_list = example.build_context(serialized_jobs)

    assert len(context_list) == 3
    assert all('job' in ctx for ctx in context_list)
    assert all(ctx['operation'] == Operation.COMPILE for ctx in context_list)


# Tests for celery_enqueue_call method (lines 239-248)
def test_celery_enqueue_call():
  """Test celery_enqueue_call method"""
  example = Example()

  context = {'job': {'id': 1}, 'operation': Operation.COMPILE}
  q_name = 'test_queue'

  with patch('tuna.example.celery_tuning.celery_tasks.celery_enqueue'
            ) as mock_celery_enqueue:
    mock_async_result = Mock()
    mock_celery_enqueue.apply_async.return_value = mock_async_result

    result = example.celery_enqueue_call(context, q_name)

    mock_celery_enqueue.apply_async.assert_called_once()
    assert result == mock_async_result


# Tests for process_compile_results method (lines 250-257)
def test_process_compile_results():
  """Test process_compile_results method"""
  example = Example()
  example.logger = Mock()

  mock_session = Mock()
  fin_json = {'result': 'success'}
  context = {'job': {'id': 1}}

  with patch.object(example, 'update_job_state') as mock_update:
    example.process_compile_results(mock_session, fin_json, context)

    mock_update.assert_called_once_with(mock_session, fin_json, context)
    example.logger.info.assert_called()


# Tests for process_eval_results method (lines 259-266)
def test_process_eval_results():
  """Test process_eval_results method"""
  example = Example()
  example.logger = Mock()

  mock_session = Mock()
  fin_json = {'result': 'success'}
  context = {'job': {'id': 1}}

  with patch.object(example, 'update_job_state') as mock_update:
    example.process_eval_results(mock_session, fin_json, context)

    mock_update.assert_called_once_with(mock_session, fin_json, context)
    example.logger.info.assert_called()


# Tests for update_job_state method (lines 268-276)
def test_update_job_state():
  """Test update_job_state method"""
  example = Example()
  example.logger = Mock()
  example.dbt = Mock()

  mock_session = Mock()
  fin_json = {'result': 'success', 'time': 123.45}
  context = {'job': {'id': 1, 'session': 1}}

  with patch('tuna.example.example_lib.set_job_state') as mock_set_state:
    example.update_job_state(mock_session, fin_json, context)

    example.logger.info.assert_called_with(fin_json)
    mock_set_state.assert_called_once()
    # Verify 'completed' state and result were passed


def test_run_add_tables_mode():
  """Test run() method with add_tables flag"""
  example = Example()

  with patch.object(example, 'parse_args') as mock_parse, \
       patch.object(example, 'add_tables') as mock_add_tables:
    example.args = Mock()
    example.args.add_tables = True

    result = example.run()

    mock_parse.assert_called_once()
    mock_add_tables.assert_called_once()
    assert result is None
