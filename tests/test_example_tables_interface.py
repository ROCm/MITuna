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
"""Tests for tuna.example.tables (ExampleDBTables)"""
import os
import sys

sys.path.append("../tuna")
sys.path.append("tuna")

from tuna.example.tables import ExampleDBTables
from tuna.example.example_tables import Job
from tuna.example.session import SessionExample
from tuna.tables_interface import DBTablesInterface


def test_example_dbt_init():
  """Test ExampleDBTables initialization"""
  dbt = ExampleDBTables(session_id=1)
  assert dbt is not None
  assert dbt.session_id == 1


def test_example_dbt_init_no_session():
  """Test ExampleDBTables initialization without session_id"""
  dbt = ExampleDBTables()
  assert dbt is not None
  assert dbt.session_id is None


def test_example_dbt_job_table_attribute():
  """Test ExampleDBTables job_table attribute is set to Job"""
  dbt = ExampleDBTables(session_id=1)
  assert hasattr(dbt, 'job_table')
  assert dbt.job_table == Job


def test_example_dbt_session_table_attribute():
  """Test ExampleDBTables session_table attribute is set to SessionExample"""
  dbt = ExampleDBTables(session_id=1)
  assert hasattr(dbt, 'session_table')
  assert dbt.session_table == SessionExample


def test_example_dbt_set_tables():
  """Test set_tables() method"""
  dbt = ExampleDBTables(session_id=1)
  # Verify tables are set correctly
  assert dbt.job_table == Job
  assert dbt.session_table == SessionExample


def test_example_dbt_set_tables_with_custom_class():
  """Test set_tables() with custom session class"""
  dbt = ExampleDBTables(session_id=1)
  # The set_tables method takes sess_class parameter
  # Default should be SessionExample
  assert dbt.session_table == SessionExample

  # Call set_tables with explicit SessionExample (default behavior)
  dbt.set_tables(SessionExample)
  assert dbt.job_table == Job
  assert dbt.session_table == SessionExample


def test_example_dbt_inheritance():
  """Test ExampleDBTables inherits from DBTablesInterface"""
  dbt = ExampleDBTables(session_id=1)
  assert isinstance(dbt, DBTablesInterface)


def test_example_dbt_has_all_required_methods():
  """Test ExampleDBTables has required methods from parent"""
  dbt = ExampleDBTables(session_id=1)
  # Should have set_tables method
  assert hasattr(dbt, 'set_tables')
  assert callable(dbt.set_tables)


def test_example_dbt_table_instances():
  """Test that table attributes are class types, not instances"""
  dbt = ExampleDBTables(session_id=1)
  # job_table and session_table should be classes, not instances
  assert dbt.job_table == Job  # Class comparison
  assert dbt.session_table == SessionExample  # Class comparison
