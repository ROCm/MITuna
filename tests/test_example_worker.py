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
from unittest.mock import Mock, patch, MagicMock

sys.path.append("../tuna")
sys.path.append("tuna")

from tuna.example.example_worker import ExampleWorker
from tuna.worker_interface import WorkerInterface


def test_step_calls_run_cmd():
  """Test step() calls run_cmd()"""
  worker = ExampleWorker(session_id=1, gpu_idx=0, machine=Mock(), envmt=[])

  with patch.object(worker, 'run_cmd') as mock_run_cmd:
    mock_run_cmd.return_value = 'test_output'
    result = worker.step()

    mock_run_cmd.assert_called_once()
    assert result == 'test_output'


def test_run_cmd_constructs_command():
  """Test run_cmd() constructs command correctly"""
  worker = ExampleWorker(session_id=1,
                         gpu_idx=0,
                         machine=Mock(),
                         envmt=['VAR1=value1', 'VAR2=value2'])

  with patch.object(worker, 'run_command') as mock_run_command:
    mock_run_command.return_value = (0, 'test_output')

    result = worker.run_cmd()

    # Verify run_command was called
    assert mock_run_command.called

    # Get the command that was passed
    call_args = mock_run_command.call_args[0]
    cmd_list = call_args[0]

    # Command should be a list
    assert isinstance(cmd_list, list)
    # Should contain rocminfo
    cmd_str = ' '.join(cmd_list)
    assert '/opt/rocm/bin/rocminfo' in cmd_str or 'rocminfo' in cmd_str


def test_run_cmd_includes_envmt():
  """Test run_cmd() includes environment variables"""
  worker = ExampleWorker(session_id=1,
                         gpu_idx=0,
                         machine=Mock(),
                         envmt=['VAR1=value1', 'VAR2=value2'])

  with patch.object(worker, 'run_command') as mock_run_command:
    mock_run_command.return_value = (0, 'test_output')

    worker.run_cmd()

    # Verify the command includes environment variables
    call_args = mock_run_command.call_args[0]
    cmd_list = call_args[0]
    cmd_str = ' '.join(cmd_list)

    # Environment should be included at the start
    assert 'VAR1=value1' in cmd_str or 'VAR2=value2' in cmd_str


def test_run_cmd_runs_rocminfo():
  """Test run_cmd() runs rocminfo command"""
  worker = ExampleWorker(session_id=1, gpu_idx=0, machine=Mock(), envmt=[])

  with patch.object(worker, 'run_command') as mock_run_command:
    mock_run_command.return_value = (0, 'rocminfo output')

    result = worker.run_cmd()

    assert mock_run_command.called
    assert result == 'rocminfo output'


def test_run_cmd_returns_output():
  """Test run_cmd() returns output correctly"""
  worker = ExampleWorker(session_id=1, gpu_idx=0, machine=Mock(), envmt=[])

  expected_output = 'GPU Information:\nDevice: gfx90a'

  with patch.object(worker, 'run_command') as mock_run_command:
    mock_run_command.return_value = (0, expected_output)

    result = worker.run_cmd()

    assert result == expected_output


def test_run_cmd_with_empty_envmt():
  """Test run_cmd() with empty envmt"""
  worker = ExampleWorker(session_id=1, gpu_idx=0, machine=Mock(), envmt=[])

  with patch.object(worker, 'run_command') as mock_run_command:
    mock_run_command.return_value = (0, 'output')

    result = worker.run_cmd()

    assert mock_run_command.called
    assert result == 'output'

    # Command should still contain rocminfo even with empty envmt
    call_args = mock_run_command.call_args[0]
    cmd_list = call_args[0]
    cmd_str = ' '.join(str(cmd_list))
    assert 'rocminfo' in cmd_str.lower() or '/opt/rocm/bin/rocminfo' in str(
        cmd_list)


def test_worker_inherits_worker_interface():
  """Test ExampleWorker inherits from WorkerInterface"""
  worker = ExampleWorker(session_id=1, gpu_idx=0, machine=Mock(), envmt=[])
  assert isinstance(worker, WorkerInterface)


def test_set_db_tables():
  """Test set_db_tables() method"""
  worker = ExampleWorker(session_id=42, gpu_idx=0, machine=Mock(), envmt=[])

  assert worker.dbt is not None
  assert worker.dbt.session_id == 42


def test_worker_initialization():
  """Test ExampleWorker initialization"""
  mock_machine = Mock()
  mock_machine.arch = 'gfx90a'
  mock_machine.num_cu = 104

  worker = ExampleWorker(session_id=1,
                         gpu_idx=0,
                         machine=mock_machine,
                         envmt=['TEST=value'])

  assert worker.session_id == 1
  assert worker.gpu_idx == 0
  assert worker.machine == mock_machine
  assert worker.envmt == ['TEST=value']
  assert worker.dbt is not None
