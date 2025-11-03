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
"""Fixtures and utilities for example module tests"""
import os
import sys
import argparse
from unittest.mock import Mock, MagicMock, PropertyMock

sys.path.append("../tuna")
sys.path.append("tuna")

from tuna.example.example_tables import Job, JobEnum
from tuna.example.session import SessionExample
from tuna.example.tables import ExampleDBTables
from tuna.example.example_worker import ExampleWorker
from tuna.machine import Machine
from tuna.utils.utility import SimpleDict


def create_mock_args(**kwargs):
  """Create a mock argparse.Namespace with default values for testing"""
  args = argparse.Namespace()

  # Default values
  args.arch = kwargs.get('arch', 'gfx90a')
  args.num_cu = kwargs.get('num_cu', 104)
  args.version = kwargs.get('version', '5.7.1')
  args.session_id = kwargs.get('session_id', 1)
  args.machines = kwargs.get('machines', None)
  args.remote_machine = kwargs.get('remote_machine', False)
  args.label = kwargs.get('label', 'test_label')
  args.restart_machine = kwargs.get('restart_machine', False)
  args.docker_name = kwargs.get('docker_name', 'miopentuna')
  args.enqueue_only = kwargs.get('enqueue_only', False)
  args.shutdown_workers = kwargs.get('shutdown_workers', False)
  args.add_tables = kwargs.get('add_tables', False)
  args.execute = kwargs.get('execute', False)
  args.init_session = kwargs.get('init_session', False)
  args.reason = kwargs.get('reason', 'test_reason')
  args.rocm_v = kwargs.get('rocm_v', '5.7.1')
  args.ticket = kwargs.get('ticket', 'N/A')

  # Update with any provided kwargs
  for key, value in kwargs.items():
    setattr(args, key, value)

  return args


def create_mock_machine(**kwargs):
  """Create a mock Machine object"""
  machine = Mock(spec=Machine)
  machine.id = kwargs.get('id', 1)
  machine.arch = kwargs.get('arch', 'gfx90a')
  machine.num_cu = kwargs.get('num_cu', 104)
  machine.local_machine = kwargs.get('local_machine', True)
  machine.get_num_cpus = Mock(return_value=kwargs.get('num_cpus', 1))
  machine.restart_server = Mock()
  return machine


def create_mock_worker(**kwargs):
  """Create a mock ExampleWorker"""
  worker = Mock(spec=ExampleWorker)
  worker.session_id = kwargs.get('session_id', 1)
  worker.machine = kwargs.get('machine', create_mock_machine())
  worker.envmt = kwargs.get('envmt', [])
  worker.start = Mock()
  worker.join = Mock()
  worker.run = Mock(return_value='test_output')
  worker.get_rocm_v = Mock(return_value='5.7.1')
  return worker


def create_example_job(**kwargs):
  """Create a Job object with default values"""
  job = Job()
  job.session = kwargs.get('session', 1)
  job.reason = kwargs.get('reason', 'test_reason')
  job.state = kwargs.get('state', JobEnum.new)
  job.retries = kwargs.get('retries', 0)
  job.result = kwargs.get('result', None)
  job.gpu_id = kwargs.get('gpu_id', -1)
  job.machine_id = kwargs.get('machine_id', -1)
  return job


def create_example_session(**kwargs):
  """Create a SessionExample object with default values"""
  session = SessionExample()
  session.id = kwargs.get('id', 1)
  session.arch = kwargs.get('arch', 'gfx90a')
  session.num_cu = kwargs.get('num_cu', 104)
  session.rocm_v = kwargs.get('rocm_v', '5.7.1')
  session.reason = kwargs.get('reason', 'test_reason')
  session.docker = kwargs.get('docker', 'miopentuna')
  session.ticket = kwargs.get('ticket', 'N/A')
  return session


def create_mock_db_session():
  """Create a mock database session"""
  session = MagicMock()
  session.add = Mock()
  session.commit = Mock()
  session.rollback = Mock()
  session.query = Mock()
  session.execute = Mock()
  return session


def create_mock_kwargs(**kwargs):
  """Create kwargs dict for worker initialization"""
  return {
      'session_id': kwargs.get('session_id', 1),
      'gpu_idx': kwargs.get('gpu_idx', 0),
      'machine': kwargs.get('machine', create_mock_machine()),
      'envmt': kwargs.get('envmt', []),
      'dbt': kwargs.get('dbt', None),
  }


def create_simple_dict(**kwargs):
  """Create a SimpleDict-like object"""
  return SimpleDict(**kwargs)
