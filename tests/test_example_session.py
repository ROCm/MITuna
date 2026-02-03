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
"""Tests for tuna.example.session"""
import os
import sys
import argparse
from unittest.mock import Mock, MagicMock, patch

sys.path.append("../tuna")
sys.path.append("tuna")

from tuna.example.session import SessionExample
from tuna.db.session_mixin import SessionMixin
from sqlalchemy import inspect
from sqlalchemy import UniqueConstraint


def test_session_example_table_name():
  """Test SessionExample __tablename__"""
  session = SessionExample()
  assert hasattr(SessionExample, '__tablename__')
  assert SessionExample.__tablename__ == "session_example"


def test_session_example_unique_constraint():
  """Test SessionExample UniqueConstraint"""
  assert hasattr(SessionExample, '__table_args__')
  constraints = SessionExample.__table_args__

  # Find UniqueConstraint
  has_unique_constraint = False
  for constraint in constraints:
    if isinstance(constraint, UniqueConstraint):
      assert 'arch' in constraint.columns
      assert 'num_cu' in constraint.columns
      assert 'rocm_v' in constraint.columns
      assert 'reason' in constraint.columns
      assert 'docker' in constraint.columns
      assert constraint.name == "uq_idx"
      has_unique_constraint = True

  assert has_unique_constraint, "UniqueConstraint not found"


def test_session_example_inherits_session_mixin():
  """Test SessionExample inherits from SessionMixin"""
  session = SessionExample()
  assert isinstance(session, SessionMixin)


def test_get_query_filters():
  """Test get_query method filters correctly"""
  session_obj = SessionExample()
  mock_session = MagicMock()

  # Create a mock query object
  mock_query = MagicMock()
  mock_session.query.return_value = mock_query
  mock_query.filter.return_value = mock_query

  # Create test entry
  entry = argparse.Namespace()
  entry.arch = 'gfx90a'
  entry.num_cu = 104
  entry.rocm_v = '5.7.1'
  entry.reason = 'test_reason'
  entry.docker = 'miopentuna'

  # Create session object with same values
  sess_obj = SessionExample()
  sess_obj.arch = 'gfx90a'
  sess_obj.num_cu = 104
  sess_obj.rocm_v = '5.7.1'
  sess_obj.reason = 'test_reason'
  sess_obj.docker = 'miopentuna'

  # Call get_query
  query = session_obj.get_query(mock_session, SessionExample, entry)

  # Verify query was created (it returns mock_query in our test)
  assert query is not None


def test_add_new_session():
  """Test add_new_session method"""
  session = SessionExample()

  # Create mock args
  args = argparse.Namespace()
  args.label = 'test_label'
  args.docker_name = 'test_docker'
  args.arch = 'gfx90a'
  args.num_cu = 104
  args.rocm_v = '5.7.1'
  args.ticket = 'TEST-123'

  # Create mock worker
  worker = Mock()
  worker.machine = Mock()
  worker.machine.arch = 'gfx906'
  worker.machine.num_cu = 60
  worker.get_rocm_v = Mock(return_value='5.6.0')

  # Call add_new_session
  session.add_new_session(args, worker)

  # Verify values were set
  assert session.reason == 'test_label'
  assert session.docker == 'test_docker'
  assert session.arch == 'gfx90a'  # From args
  assert session.num_cu == 104  # From args
  assert session.rocm_v == '5.7.1'  # From args
  assert session.ticket == 'TEST-123'


def test_add_new_session_falls_back_to_worker():
  """Test add_new_session falls back to worker values when args missing"""
  session = SessionExample()

  # Create mock args without arch/num_cu/rocm_v
  args = argparse.Namespace()
  args.label = 'test_label'
  args.docker_name = 'test_docker'
  args.arch = None
  args.num_cu = None
  args.rocm_v = None
  args.ticket = None

  # Create mock worker with machine
  worker = Mock()
  worker.machine = Mock()
  worker.machine.arch = 'gfx906'
  worker.machine.num_cu = 60
  worker.get_rocm_v = Mock(return_value='5.6.0')

  # Call add_new_session
  session.add_new_session(args, worker)

  # Verify values fell back to worker
  assert session.reason == 'test_label'
  assert session.docker == 'test_docker'
  assert session.arch == 'gfx906'  # From worker
  assert session.num_cu == 60  # From worker
  assert session.rocm_v == '5.6.0'  # From worker
  assert session.ticket == 'N/A'  # Default


def test_add_new_session_calls_parent_and_insert():
  """Test add_new_session calls parent method and insert_session"""
  session = SessionExample()

  # Create mock args and worker
  args = argparse.Namespace()
  args.label = 'test_label'
  args.docker_name = 'test_docker'
  args.arch = 'gfx90a'
  args.num_cu = 104
  args.rocm_v = '5.7.1'
  args.ticket = 'N/A'

  worker = Mock()
  worker.machine = Mock()
  worker.machine.arch = 'gfx90a'
  worker.machine.num_cu = 104
  worker.get_rocm_v = Mock(return_value='5.7.1')

  # Mock insert_session to return a session ID
  session.insert_session = Mock(return_value=42)

  # Call add_new_session
  result = session.add_new_session(args, worker)

  # Verify insert_session was called and result returned
  assert session.insert_session.called
  assert result == 42


def test_add_new_session_returns_session_id():
  """Test add_new_session returns session ID"""
  session = SessionExample()

  args = argparse.Namespace()
  args.label = 'test_label'
  args.docker_name = 'test_docker'
  args.arch = 'gfx90a'
  args.num_cu = 104
  args.rocm_v = '5.7.1'

  worker = Mock()
  worker.machine = Mock()
  worker.machine.arch = 'gfx90a'
  worker.machine.num_cu = 104
  worker.get_rocm_v = Mock(return_value='5.7.1')

  # Mock insert_session
  with patch.object(session, 'insert_session', return_value=123):
    result = session.add_new_session(args, worker)
    assert result == 123
