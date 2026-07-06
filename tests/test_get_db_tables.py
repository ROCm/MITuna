#!/usr/bin/env python3
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
"""
Tests for MIOpen DB table retrieval module.

This module tests the get_miopen_tables function in tuna/miopen/db/get_db_tables.py.
"""

import pytest

from tuna.miopen.db.get_db_tables import get_miopen_tables
from tuna.miopen.db.solver import Solver
from tuna.miopen.db.session import Session
from tuna.miopen.db.benchmark import Framework, Model
from tuna.machine import Machine
from tuna.miopen.db.tensortable import TensorTable


@pytest.mark.unit
@pytest.mark.db
@pytest.mark.miopen
class TestGetMiopenTables:
  """Tests for get_miopen_tables function."""

  def test_get_miopen_tables_returns_list(self):
    """Test that get_miopen_tables returns a list."""
    tables = get_miopen_tables()
    assert isinstance(tables, list)

  def test_get_miopen_tables_not_empty(self):
    """Test that get_miopen_tables returns non-empty list."""
    tables = get_miopen_tables()
    assert len(tables) > 0

  def test_get_miopen_tables_contains_common_tables(self):
    """Test that common MIOpen tables are included."""
    tables = get_miopen_tables()

    # Check for common table types
    has_solver = any(isinstance(t, Solver) for t in tables)
    has_session = any(isinstance(t, Session) for t in tables)
    has_framework = any(isinstance(t, Framework) for t in tables)
    has_model = any(isinstance(t, Model) for t in tables)
    has_machine = any(isinstance(t, Machine) for t in tables)
    has_tensor = any(isinstance(t, TensorTable) for t in tables)

    assert has_solver, "Solver table not found"
    assert has_session, "Session table not found"
    assert has_framework, "Framework table not found"
    assert has_model, "Model table not found"
    assert has_machine, "Machine table not found"
    assert has_tensor, "TensorTable not found"

  def test_get_miopen_tables_expected_count(self):
    """Test that get_miopen_tables returns expected number of tables."""
    tables = get_miopen_tables()

    # 6 common tables + 13 conv + 4 fusion + 10 bn = 33 tables
    assert len(tables) == 33

  def test_get_miopen_tables_includes_convolution_tables(self):
    """Test that convolution tables are included."""
    tables = get_miopen_tables()
    table_names = [
        t.__tablename__
        if hasattr(t, '__tablename__') else t.__class__.__tablename__
        for t in tables
    ]

    # Check for some convolution-specific tables
    assert 'conv_config' in table_names
    assert 'conv_job' in table_names

  def test_get_miopen_tables_includes_fusion_tables(self):
    """Test that fusion tables are included."""
    tables = get_miopen_tables()
    table_names = [
        t.__tablename__
        if hasattr(t, '__tablename__') else t.__class__.__tablename__
        for t in tables
    ]

    # Check for fusion-specific tables
    assert 'fusion_config' in table_names
    assert 'fusion_job' in table_names

  def test_get_miopen_tables_includes_batch_norm_tables(self):
    """Test that batch norm tables are included."""
    tables = get_miopen_tables()
    table_names = [
        t.__tablename__
        if hasattr(t, '__tablename__') else t.__class__.__tablename__
        for t in tables
    ]

    # Check for batch norm-specific tables
    assert 'bn_config' in table_names
    assert 'bn_job' in table_names

  def test_get_miopen_tables_no_duplicates(self):
    """Test that there are no duplicate table names."""
    tables = get_miopen_tables()
    table_names = [
        t.__tablename__
        if hasattr(t, '__tablename__') else t.__class__.__tablename__
        for t in tables
    ]

    # Check for duplicates
    assert len(table_names) == len(set(table_names))

  def test_get_miopen_tables_consistent_calls(self):
    """Test that multiple calls return same table count."""
    tables1 = get_miopen_tables()
    tables2 = get_miopen_tables()

    assert len(tables1) == len(tables2)

  def test_get_miopen_tables_all_have_tablename(self):
    """Test that all tables have __tablename__ attribute."""
    tables = get_miopen_tables()

    for table in tables:
      assert hasattr(table, '__tablename__') or \
             hasattr(table.__class__, '__tablename__'), \
             f"Table {table} missing __tablename__ attribute"

  def test_get_miopen_tables_order(self):
    """Test that common tables come first."""
    tables = get_miopen_tables()

    # First 6 tables should be common tables
    assert isinstance(tables[0], Solver)
    assert isinstance(tables[1], Session)
    assert isinstance(tables[2], Framework)
    assert isinstance(tables[3], Model)
    assert isinstance(tables[4], Machine)
    assert isinstance(tables[5], TensorTable)


@pytest.mark.integration
@pytest.mark.db
@pytest.mark.miopen
class TestGetMiopenTablesIntegration:
  """Integration tests for get_miopen_tables."""

  def test_tables_can_be_used_for_schema_creation(self):
    """Test that returned tables have necessary attributes for schema creation."""
    tables = get_miopen_tables()

    for table in tables:
      # Each table should have metadata or be a valid ORM class
      assert hasattr(table, '__tablename__') or \
             hasattr(table.__class__, '__tablename__')

  def test_get_miopen_tables_performance(self):
    """Test that get_miopen_tables executes quickly."""
    import time

    start = time.time()
    tables = get_miopen_tables()
    elapsed = time.time() - start

    # Should complete in less than 1 second
    assert elapsed < 1.0
    assert len(tables) > 0
