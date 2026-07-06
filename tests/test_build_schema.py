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
Tests for MIOpen database schema building module.

This module tests schema creation functions in tuna/miopen/db/build_schema.py.
"""

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import OperationalError

from tuna.miopen.db.build_schema import recreate_triggers


@pytest.mark.unit
@pytest.mark.db
@pytest.mark.miopen
class TestRecreateTriggers:
  """Tests for recreate_triggers function."""

  def test_recreate_triggers_returns_true(self, mock_subprocess):
    """Test that recreate_triggers returns True on success."""
    with patch('tuna.miopen.db.build_schema.ENGINE') as mock_engine:
      mock_conn = MagicMock()
      mock_engine.connect.return_value.__enter__.return_value = mock_conn

      drop_triggers = ['trigger1;', 'trigger2;']
      create_triggers = ['CREATE trigger1', 'CREATE trigger2']

      result = recreate_triggers(drop_triggers, create_triggers)
      assert result is True

  def test_recreate_triggers_drops_all_triggers(self):
    """Test that all drop trigger commands are executed."""
    with patch('tuna.miopen.db.build_schema.ENGINE') as mock_engine:
      mock_conn = MagicMock()
      mock_engine.connect.return_value.__enter__.return_value = mock_conn

      drop_triggers = ['drop1;', 'drop2;', 'drop3;']
      create_triggers = []

      recreate_triggers(drop_triggers, create_triggers)

      # Should execute drop for each trigger
      assert mock_conn.execute.call_count == len(drop_triggers)

  def test_recreate_triggers_creates_all_triggers(self):
    """Test that all create trigger commands are executed."""
    with patch('tuna.miopen.db.build_schema.ENGINE') as mock_engine:
      mock_conn = MagicMock()
      mock_engine.connect.return_value.__enter__.return_value = mock_conn

      drop_triggers = []
      create_triggers = ['CREATE t1', 'CREATE t2']

      recreate_triggers(drop_triggers, create_triggers)

      # Should execute create for each trigger
      assert mock_conn.execute.call_count == len(create_triggers)

  def test_recreate_triggers_drops_before_creates(self):
    """Test that drop commands are executed before create commands."""
    with patch('tuna.miopen.db.build_schema.ENGINE') as mock_engine:
      mock_conn = MagicMock()
      mock_engine.connect.return_value.__enter__.return_value = mock_conn

      drop_triggers = ['drop1;']
      create_triggers = ['CREATE t1']

      recreate_triggers(drop_triggers, create_triggers)

      # Verify execution order
      calls = mock_conn.execute.call_args_list
      assert len(calls) == 2
      # First call should be drop
      assert 'drop' in str(calls[0])
      # Second call should be create
      assert 'CREATE' in str(calls[1])

  def test_recreate_triggers_handles_operational_error(self):
    """Test that OperationalError during create is handled gracefully."""
    with patch('tuna.miopen.db.build_schema.ENGINE') as mock_engine:
      mock_conn = MagicMock()
      mock_engine.connect.return_value.__enter__.return_value = mock_conn

      # Make execute raise OperationalError on create
      def side_effect(sql):
        if 'CREATE' in sql:
          raise OperationalError("test error", None, None)
        return None

      mock_conn.execute.side_effect = side_effect

      drop_triggers = []
      create_triggers = ['CREATE t1', 'CREATE t2']

      # Should not raise exception, should continue and return True
      result = recreate_triggers(drop_triggers, create_triggers)
      assert result is True

  def test_recreate_triggers_continues_after_error(self):
    """Test that trigger creation continues after an error."""
    with patch('tuna.miopen.db.build_schema.ENGINE') as mock_engine:
      mock_conn = MagicMock()
      mock_engine.connect.return_value.__enter__.return_value = mock_conn

      # Make first create fail, second succeed
      call_count = [0]

      def side_effect(sql):
        if 'CREATE' in sql:
          call_count[0] += 1
          if call_count[0] == 1:
            raise OperationalError("test error", None, None)
        return None

      mock_conn.execute.side_effect = side_effect

      create_triggers = ['CREATE t1', 'CREATE t2']
      result = recreate_triggers([], create_triggers)

      # Should have tried both creates
      assert mock_conn.execute.call_count == 2
      assert result is True

  def test_recreate_triggers_with_empty_lists(self):
    """Test recreate_triggers with empty trigger lists."""
    with patch('tuna.miopen.db.build_schema.ENGINE') as mock_engine:
      mock_conn = MagicMock()
      mock_engine.connect.return_value.__enter__.return_value = mock_conn

      result = recreate_triggers([], [])

      assert result is True
      # No execute calls should be made
      assert mock_conn.execute.call_count == 0

  def test_recreate_triggers_uses_drop_trigger_if_exists(self):
    """Test that drop trigger commands use 'if exists' pattern."""
    with patch('tuna.miopen.db.build_schema.ENGINE') as mock_engine:
      mock_conn = MagicMock()
      mock_engine.connect.return_value.__enter__.return_value = mock_conn

      drop_triggers = ['my_trigger;']

      recreate_triggers(drop_triggers, [])

      # Check that the drop command includes 'if exists'
      call_args = mock_conn.execute.call_args_list[0][0][0]
      assert 'drop trigger if exists' in call_args


@pytest.mark.integration
@pytest.mark.db
@pytest.mark.miopen
@pytest.mark.slow
class TestBuildSchemaIntegration:
  """Integration tests for build_schema functionality."""

  def test_recreate_triggers_with_real_triggers(self):
    """Test recreate_triggers with actual trigger definitions."""
    from tuna.miopen.db.triggers import get_miopen_triggers, drop_miopen_triggers

    with patch('tuna.miopen.db.build_schema.ENGINE') as mock_engine:
      mock_conn = MagicMock()
      mock_engine.connect.return_value.__enter__.return_value = mock_conn

      drop_triggers = drop_miopen_triggers()
      create_triggers = get_miopen_triggers()

      result = recreate_triggers(drop_triggers, create_triggers)

      assert result is True
      # Should execute all drops and creates
      expected_calls = len(drop_triggers) + len(create_triggers)
      assert mock_conn.execute.call_count == expected_calls

  def test_recreate_triggers_idempotent(self):
    """Test that recreate_triggers can be called multiple times."""
    with patch('tuna.miopen.db.build_schema.ENGINE') as mock_engine:
      mock_conn = MagicMock()
      mock_engine.connect.return_value.__enter__.return_value = mock_conn

      drop_triggers = ['t1;']
      create_triggers = ['CREATE t1']

      # Call twice
      result1 = recreate_triggers(drop_triggers, create_triggers)
      result2 = recreate_triggers(drop_triggers, create_triggers)

      assert result1 is True
      assert result2 is True


@pytest.mark.unit
@pytest.mark.db
@pytest.mark.miopen
class TestBuildSchemaModule:
  """Tests for build_schema module structure."""

  def test_module_imports(self):
    """Test that build_schema module can be imported."""
    import tuna.miopen.db.build_schema as build_schema
    assert build_schema is not None

  def test_module_has_recreate_triggers(self):
    """Test that module exports recreate_triggers function."""
    from tuna.miopen.db import build_schema
    assert hasattr(build_schema, 'recreate_triggers')
    assert callable(build_schema.recreate_triggers)

  def test_module_has_main(self):
    """Test that module has main function."""
    from tuna.miopen.db import build_schema
    assert hasattr(build_schema, 'main')
    assert callable(build_schema.main)

  def test_module_has_logger(self):
    """Test that module has LOGGER configured."""
    from tuna.miopen.db import build_schema
    assert hasattr(build_schema, 'LOGGER')

  def test_recreate_triggers_signature(self):
    """Test that recreate_triggers has correct signature."""
    import inspect
    from tuna.miopen.db.build_schema import recreate_triggers

    sig = inspect.signature(recreate_triggers)
    params = list(sig.parameters.keys())

    assert len(params) == 2
    assert 'drop_triggers' in params
    assert 'create_triggers' in params
