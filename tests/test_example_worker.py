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
"""Tests for tuna.example.example_worker"""
import os
import sys
from io import StringIO
from unittest.mock import Mock, patch, MagicMock

sys.path.append("../tuna")
sys.path.append("tuna")

from tuna.example.example_worker import ExampleWorker
from tuna.worker_interface import WorkerInterface


def test_step_calls_run_cmd():
  """Test step() calls run_cmd()"""
  mock_machine = Mock()
  mock_machine.hostname = 'test_host'
  mock_machine.port = 22

  with patch('tuna.example.tables.DbSession'):
    worker = ExampleWorker(session_id=None,
                           gpu_id=0,
                           machine=mock_machine,
                           envmt=[])

  with patch.object(worker, 'run_cmd') as mock_run_cmd:
    mock_run_cmd.return_value = 'test_output'
    result = worker.step()

    mock_run_cmd.assert_called_once()
    assert result == 'test_output'


def test_run_cmd_constructs_command():
  """Test run_cmd() constructs command correctly"""
  mock_machine = Mock()
  mock_machine.hostname = 'test_host'
  mock_machine.port = 22

  with patch('tuna.example.tables.DbSession'):
    worker = ExampleWorker(session_id=None,
                           gpu_id=0,
                           machine=mock_machine,
                           envmt=['VAR1=value1', 'VAR2=value2'])

  with patch.object(worker, 'exec_docker_cmd') as mock_exec_docker:
    mock_err = StringIO('')
    mock_exec_docker.return_value = (0, 'test_output', mock_err)

    result = worker.run_cmd()

    # Verify exec_docker_cmd was called
    assert mock_exec_docker.called

    # Get the command that was passed (it will be a string joined from the list)
    call_args = mock_exec_docker.call_args[0]
    cmd = call_args[0]

    # Command should be a string containing rocminfo
    assert '/opt/rocm/bin/rocminfo' in cmd or 'rocminfo' in cmd
    assert result == 'test_output'


def test_run_cmd_includes_envmt():
  """Test run_cmd() includes environment variables"""
  mock_machine = Mock()
  mock_machine.hostname = 'test_host'
  mock_machine.port = 22

  with patch('tuna.example.tables.DbSession'):
    worker = ExampleWorker(session_id=None,
                           gpu_id=0,
                           machine=mock_machine,
                           envmt=['VAR1=value1', 'VAR2=value2'])

  with patch.object(worker, 'exec_docker_cmd') as mock_exec_docker:
    mock_err = StringIO('')
    mock_exec_docker.return_value = (0, 'test_output', mock_err)

    worker.run_cmd()

    # Verify the command includes environment variables
    call_args = mock_exec_docker.call_args[0]
    cmd = call_args[0]

    # Environment should be included at the start
    assert 'VAR1=value1' in cmd or 'VAR2=value2' in cmd


def test_run_cmd_runs_rocminfo():
  """Test run_cmd() runs rocminfo command"""
  mock_machine = Mock()
  mock_machine.hostname = 'test_host'
  mock_machine.port = 22

  with patch('tuna.example.tables.DbSession'):
    worker = ExampleWorker(session_id=None,
                           gpu_id=0,
                           machine=mock_machine,
                           envmt=[])

  with patch.object(worker, 'exec_docker_cmd') as mock_exec_docker:
    mock_out = StringIO('rocminfo output')
    mock_err = StringIO('')
    mock_exec_docker.return_value = (0, mock_out, mock_err)

    result = worker.run_cmd()

    assert mock_exec_docker.called
    assert result == 'rocminfo output'


def test_run_cmd_returns_output():
  """Test run_cmd() returns output correctly"""
  mock_machine = Mock()
  mock_machine.hostname = 'test_host'
  mock_machine.port = 22

  with patch('tuna.example.tables.DbSession'):
    worker = ExampleWorker(session_id=None,
                           gpu_id=0,
                           machine=mock_machine,
                           envmt=[])

  expected_output = 'GPU Information:\nDevice: gfx90a'

  with patch.object(worker, 'exec_docker_cmd') as mock_exec_docker:
    mock_err = StringIO('')
    mock_exec_docker.return_value = (0, expected_output, mock_err)

    result = worker.run_cmd()

    assert result == expected_output


def test_run_cmd_with_empty_envmt():
  """Test run_cmd() with empty envmt"""
  mock_machine = Mock()
  mock_machine.hostname = 'test_host'
  mock_machine.port = 22

  with patch('tuna.example.tables.DbSession'):
    worker = ExampleWorker(session_id=None,
                           gpu_id=0,
                           machine=mock_machine,
                           envmt=[])

  with patch.object(worker, 'exec_docker_cmd') as mock_exec_docker:
    mock_err = StringIO('')
    mock_exec_docker.return_value = (0, 'output', mock_err)

    result = worker.run_cmd()

    assert mock_exec_docker.called
    assert result == 'output'

    # Command should still contain rocminfo even with empty envmt
    call_args = mock_exec_docker.call_args[0]
    cmd = call_args[0]
    assert 'rocminfo' in cmd.lower() or '/opt/rocm/bin/rocminfo' in cmd


def test_worker_inherits_worker_interface():
  """Test ExampleWorker inherits from WorkerInterface"""
  mock_machine = Mock()
  mock_machine.hostname = 'test_host'
  mock_machine.port = 22

  with patch('tuna.example.tables.DbSession'):
    worker = ExampleWorker(session_id=None,
                           gpu_id=0,
                           machine=mock_machine,
                           envmt=[])
  assert isinstance(worker, WorkerInterface)


def test_set_db_tables():
  """Test set_db_tables() method"""
  mock_machine = Mock()
  mock_machine.hostname = 'test_host'
  mock_machine.port = 22

  with patch('tuna.example.tables.DbSession'):
    worker = ExampleWorker(session_id=None,
                           gpu_id=0,
                           machine=mock_machine,
                           envmt=[])

  assert worker.dbt is not None
  assert worker.dbt.session_id is None


def test_worker_initialization():
  """Test ExampleWorker initialization"""
  mock_machine = Mock()
  mock_machine.arch = 'gfx90a'
  mock_machine.num_cu = 104
  mock_machine.hostname = 'test_host'
  mock_machine.port = 22

  with patch('tuna.example.tables.DbSession'):
    worker = ExampleWorker(session_id=1,
                           gpu_id=0,
                           machine=mock_machine,
                           envmt=['TEST=value'])

  assert worker.session_id == 1
  assert worker.gpu_id == 0
  assert worker.machine == mock_machine
  assert worker.envmt == ['TEST=value']
  assert worker.dbt is not None
