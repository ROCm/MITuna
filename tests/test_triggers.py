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
Tests for MIOpen database trigger management module.

This module tests trigger functions in tuna/miopen/db/triggers.py.
"""

import pytest

from tuna.miopen.db.triggers import (get_timestamp_trigger,
                                     get_conv_config_triggers,
                                     get_miopen_triggers, drop_miopen_triggers)


@pytest.mark.unit
@pytest.mark.db
@pytest.mark.miopen
class TestTimestampTrigger:
  """Tests for timestamp trigger generation."""

  def test_get_timestamp_trigger_returns_string(self):
    """Test that get_timestamp_trigger returns a string."""
    trigger = get_timestamp_trigger()
    assert isinstance(trigger, str)

  def test_get_timestamp_trigger_contains_create_trigger(self):
    """Test that trigger SQL contains CREATE trigger statement."""
    trigger = get_timestamp_trigger()
    assert 'CREATE trigger' in trigger

  def test_get_timestamp_trigger_targets_conv_job(self):
    """Test that trigger targets conv_job table."""
    trigger = get_timestamp_trigger()
    assert 'conv_job' in trigger

  def test_get_timestamp_trigger_before_update(self):
    """Test that trigger is set for before UPDATE."""
    trigger = get_timestamp_trigger()
    assert 'before UPDATE' in trigger

  def test_get_timestamp_trigger_handles_states(self):
    """Test that trigger handles different job states."""
    trigger = get_timestamp_trigger()
    assert 'compiled' in trigger
    assert 'compiling' in trigger
    assert 'evaluating' in trigger
    assert 'evaluated' in trigger

  def test_get_timestamp_trigger_sets_timestamps(self):
    """Test that trigger sets appropriate timestamp fields."""
    trigger = get_timestamp_trigger()
    assert 'compile_end' in trigger
    assert 'compile_start' in trigger
    assert 'eval_start' in trigger
    assert 'eval_end' in trigger


@pytest.mark.unit
@pytest.mark.db
@pytest.mark.miopen
class TestConvConfigTriggers:
  """Tests for convolution config trigger generation."""

  def test_get_conv_config_triggers_returns_tuple(self):
    """Test that get_conv_config_triggers returns a tuple."""
    triggers = get_conv_config_triggers()
    assert isinstance(triggers, tuple)
    assert len(triggers) == 2

  def test_conv_config_insert_trigger(self):
    """Test the insert trigger for conv_config."""
    insert_trigger, _ = get_conv_config_triggers()

    assert isinstance(insert_trigger, str)
    assert 'CREATE trigger' in insert_trigger
    assert 'before INSERT' in insert_trigger
    assert 'conv_config' in insert_trigger
    assert 'md5_trigger_conv_config_insert' in insert_trigger

  def test_conv_config_update_trigger(self):
    """Test the update trigger for conv_config."""
    _, update_trigger = get_conv_config_triggers()

    assert isinstance(update_trigger, str)
    assert 'CREATE trigger' in update_trigger
    assert 'before UPDATE' in update_trigger
    assert 'conv_config' in update_trigger
    assert 'md5_trigger_conv_config_update' in update_trigger

  def test_conv_config_triggers_set_md5(self):
    """Test that triggers set MD5 hash."""
    insert_trigger, update_trigger = get_conv_config_triggers()

    assert 'MD5' in insert_trigger
    assert 'MD5' in update_trigger
    assert 'NEW.md5' in insert_trigger
    assert 'NEW.md5' in update_trigger

  def test_conv_config_triggers_include_fields(self):
    """Test that triggers include necessary configuration fields."""
    insert_trigger, update_trigger = get_conv_config_triggers()

    required_fields = [
        'batchsize', 'spatial_dim', 'pad_h', 'pad_w', 'conv_stride_h',
        'conv_stride_w', 'dilation_h', 'dilation_w', 'group_count', 'direction',
        'input_tensor', 'weight_tensor'
    ]

    for field in required_fields:
      assert field in insert_trigger
      assert field in update_trigger


@pytest.mark.unit
@pytest.mark.db
@pytest.mark.miopen
class TestGetMiopenTriggers:
  """Tests for get_miopen_triggers function."""

  def test_get_miopen_triggers_returns_list(self):
    """Test that get_miopen_triggers returns a list."""
    triggers = get_miopen_triggers()
    assert isinstance(triggers, list)

  def test_get_miopen_triggers_not_empty(self):
    """Test that get_miopen_triggers returns non-empty list."""
    triggers = get_miopen_triggers()
    assert len(triggers) > 0

  def test_get_miopen_triggers_contains_conv_triggers(self):
    """Test that list includes convolution config triggers."""
    triggers = get_miopen_triggers()

    # Should have at least 2 triggers (insert and update for conv_config)
    assert len(triggers) >= 2

  def test_get_miopen_triggers_all_are_strings(self):
    """Test that all triggers are SQL strings."""
    triggers = get_miopen_triggers()

    for trigger in triggers:
      assert isinstance(trigger, str)
      assert len(trigger) > 0

  def test_get_miopen_triggers_all_contain_create(self):
    """Test that all triggers contain CREATE statement."""
    triggers = get_miopen_triggers()

    for trigger in triggers:
      assert 'CREATE trigger' in trigger


@pytest.mark.unit
@pytest.mark.db
@pytest.mark.miopen
class TestDropMiopenTriggers:
  """Tests for drop_miopen_triggers function."""

  def test_drop_miopen_triggers_returns_list(self):
    """Test that drop_miopen_triggers returns a list."""
    drop_cmds = drop_miopen_triggers()
    assert isinstance(drop_cmds, list)

  def test_drop_miopen_triggers_not_empty(self):
    """Test that drop_miopen_triggers returns non-empty list."""
    drop_cmds = drop_miopen_triggers()
    assert len(drop_cmds) > 0

  def test_drop_miopen_triggers_all_are_strings(self):
    """Test that all drop commands are strings."""
    drop_cmds = drop_miopen_triggers()

    for cmd in drop_cmds:
      assert isinstance(cmd, str)
      assert len(cmd) > 0

  def test_drop_miopen_triggers_includes_md5_triggers(self):
    """Test that drop commands include MD5 trigger names."""
    drop_cmds = drop_miopen_triggers()

    # Check for expected trigger names
    trigger_names = [
        'md5_trigger', 'md5_trigger_update', 'md5_trigger_conv_config_insert',
        'md5_trigger_conv_config_update'
    ]

    for name in trigger_names:
      assert any(name in cmd for cmd in drop_cmds)

  def test_drop_miopen_triggers_ends_with_semicolon(self):
    """Test that drop commands end with semicolon."""
    drop_cmds = drop_miopen_triggers()

    for cmd in drop_cmds:
      assert cmd.endswith(';')


@pytest.mark.integration
@pytest.mark.db
@pytest.mark.miopen
class TestTriggerIntegration:
  """Integration tests for trigger functionality."""

  def test_create_and_drop_triggers_match(self):
    """Test that number of create and drop commands are reasonable."""
    create_triggers = get_miopen_triggers()
    drop_triggers = drop_miopen_triggers()

    # Drop commands should be at least as many as create commands
    # (may have extras for backwards compatibility)
    assert len(drop_triggers) >= len(create_triggers)

  def test_timestamp_trigger_syntax(self):
    """Test that timestamp trigger has valid SQL syntax structure."""
    trigger = get_timestamp_trigger()

    # Check for SQL structure keywords
    assert 'CREATE trigger' in trigger
    assert 'before UPDATE' in trigger
    assert 'for each row' in trigger
    assert 'begin' in trigger
    assert 'end;' in trigger

  def test_conv_config_triggers_syntax(self):
    """Test that conv config triggers have valid SQL syntax."""
    insert_trigger, update_trigger = get_conv_config_triggers()

    for trigger in [insert_trigger, update_trigger]:
      assert 'CREATE trigger' in trigger
      assert 'for each row' in trigger
      assert 'set' in trigger

  def test_all_triggers_valid_sql_structure(self):
    """Test that all triggers have basic SQL structure."""
    triggers = get_miopen_triggers()

    for trigger in triggers:
      # Each trigger should be a complete SQL statement
      assert 'CREATE trigger' in trigger
      # Should reference a table
      assert 'on' in trigger or 'ON' in trigger

  def test_triggers_use_new_keyword(self):
    """Test that triggers properly use NEW keyword for row references."""
    triggers = get_miopen_triggers()

    for trigger in triggers:
      # Triggers that modify data should use NEW keyword
      if 'set' in trigger.lower():
        assert 'NEW.' in trigger
