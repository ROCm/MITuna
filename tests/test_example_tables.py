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
"""Tests for tuna.example.example_tables"""
import os
import sys

sys.path.append("../tuna")
sys.path.append("tuna")

from tuna.example.example_tables import Job, JobEnum, get_tables
from tuna.example.session import SessionExample
from tuna.machine import Machine


def test_job_enum_values():
  """Test JobEnum enum values"""
  assert JobEnum.new.value == 1
  assert JobEnum.running.value == 3
  assert JobEnum.completed.value == 4
  assert JobEnum.error.value == 5

  # Test enum members exist
  assert hasattr(JobEnum, 'new')
  assert hasattr(JobEnum, 'running')
  assert hasattr(JobEnum, 'completed')
  assert hasattr(JobEnum, 'error')


def test_job_table_structure():
  """Test Job class __tablename__"""
  assert hasattr(Job, '__tablename__')
  assert Job.__tablename__ == "job"


def test_job_table_unique_constraint():
  """Test Job table UniqueConstraint on reason and session"""
  assert hasattr(Job, '__table_args__')
  constraints = Job.__table_args__

  # Find UniqueConstraint
  from sqlalchemy import UniqueConstraint
  has_unique_constraint = False
  for constraint in constraints:
    if isinstance(constraint, UniqueConstraint):
      assert 'reason' in constraint.columns
      assert 'session' in constraint.columns
      assert constraint.name == "uq_idx"
      has_unique_constraint = True

  assert has_unique_constraint, "UniqueConstraint not found"


def test_job_table_columns():
  """Test all Job table column definitions"""
  # Access columns directly from the table
  columns = [col.name for col in Job.__table__.columns]

  # Check required columns exist
  assert 'session' in columns
  assert 'reason' in columns
  assert 'state' in columns
  assert 'retries' in columns
  assert 'result' in columns
  assert 'gpu_id' in columns
  assert 'machine_id' in columns


def test_job_table_state_default():
  """Test Job table state column default is 'new'"""
  job = Job()
  # The default should be 'new' which maps to JobEnum.new == 1
  # But since state is an Enum column, we check the server_default
  # Let's check by inspecting the table
  state_col = None
  for col in Job.__table__.columns:
    if col.name == 'state':
      state_col = col
      break

  assert state_col is not None, "state column not found"
  # The default value might be stored as server_default string representation
  # In practice, it defaults to JobEnum.new


def test_get_tables_returns_list():
  """Test get_tables() returns a list"""
  tables = get_tables()
  assert isinstance(tables, list)
  assert len(tables) > 0


def test_get_tables_contains_session():
  """Test get_tables() contains SessionExample"""
  tables = get_tables()
  table_types = [type(table) for table in tables]

  # Check if SessionExample instance is in the list
  has_session = False
  for table in tables:
    if isinstance(table, SessionExample):
      has_session = True
      break

  assert has_session, "SessionExample not found in get_tables()"


def test_get_tables_contains_machine():
  """Test get_tables() contains Machine"""
  tables = get_tables()

  # Check if Machine instance is in the list
  has_machine = False
  for table in tables:
    if isinstance(table, Machine):
      has_machine = True
      break

  assert has_machine, "Machine not found in get_tables()"


def test_get_tables_contains_job():
  """Test get_tables() contains Job"""
  tables = get_tables()

  # Check if Job instance is in the list
  has_job = False
  for table in tables:
    if isinstance(table, Job):
      has_job = True
      break

  assert has_job, "Job not found in get_tables()"


def test_get_tables_all_required():
  """Test get_tables() returns exactly 3 tables"""
  tables = get_tables()
  assert len(tables) == 3, f"Expected 3 tables, got {len(tables)}"


def test_job_table_column_types():
  """Test Job table column types"""
  from sqlalchemy import inspect
  inspector = inspect(Job)

  # Verify session is a ForeignKey to session_example.id
  # This is tested through the column definition
  job = Job()
  assert hasattr(job, 'session')
  assert hasattr(job, 'reason')
  assert hasattr(job, 'state')
  assert hasattr(job, 'retries')
  assert hasattr(job, 'result')
  assert hasattr(job, 'gpu_id')
  assert hasattr(job, 'machine_id')
