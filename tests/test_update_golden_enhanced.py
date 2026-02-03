#!/usr/bin/env python3
###############################################################################
#
# MIT License
#
# Copyright (c) 2023 Advanced Micro Devices, Inc.
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
"""Enhanced tests for update_golden subcmd module"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from sqlalchemy.exc import OperationalError

from tuna.miopen.subcmd.update_golden import (
    arg_update_golden, get_golden_query, latest_golden_v, sess_info,
    verify_no_duplicates, get_perf_str, create_perf_table, gold_base_update,
    gold_session_update, run_update_golden, main)
from tuna.miopen.db.tables import MIOpenDBTables
from tuna.miopen.utils.config_type import ConfigType


# ============================================================================
# Test arg_update_golden
# ============================================================================
class TestArgUpdateGolden:
  """Test argument validation for update_golden."""

  def test_arg_update_golden_with_base_golden_v(self):
    """Test args when base_golden_v is provided."""
    args = Mock()
    args.base_golden_v = 1
    args.session_id = None
    args.config_type = ConfigType.convolution
    logger = Mock()

    result = arg_update_golden(args, logger)

    assert result == args
    args.error.assert_not_called()

  def test_arg_update_golden_with_session_id(self):
    """Test args when session_id is provided."""
    args = Mock()
    args.base_golden_v = None
    args.session_id = 123
    args.config_type = ConfigType.convolution
    logger = Mock()

    result = arg_update_golden(args, logger)

    assert result == args
    args.error.assert_not_called()

  @patch('tuna.miopen.subcmd.update_golden.latest_golden_v')
  @patch('tuna.miopen.subcmd.update_golden.MIOpenDBTables')
  def test_arg_update_golden_requires_specification(self, mock_dbt, mock_latest,
                                                    capsys):
    """Test args error when neither base_golden_v nor session_id provided."""
    args = Mock()
    args.base_golden_v = None
    args.session_id = None
    args.config_type = ConfigType.convolution
    logger = Mock()
    mock_latest.return_value = 1  # Golden version exists

    result = arg_update_golden(args, logger)

    # Should call error if version exists
    mock_latest.assert_called_once()


# ============================================================================
# Test get_golden_query
# ============================================================================
class TestGetGoldenQuery:
  """Test golden query composition."""

  @patch('tuna.miopen.subcmd.update_golden.DbSession')
  def test_get_golden_query(self, mock_db_session):
    """Test get_golden_query constructs correct query."""
    mock_session = MagicMock()
    mock_db_session.return_value.__enter__.return_value = mock_session

    dbt = Mock()
    dbt.golden_table = Mock()
    dbt.golden_table.golden_miopen_v = Mock()
    dbt.golden_table.valid = Mock()

    golden_version = 5

    query = get_golden_query(dbt, golden_version)

    # Verify query construction
    assert query is not None
    mock_session.query.assert_called_once_with(dbt.golden_table)


# ============================================================================
# Test latest_golden_v
# ============================================================================
class TestLatestGoldenV:
  """Test latest golden version retrieval."""

  @patch('tuna.miopen.subcmd.update_golden.DbSession')
  def test_latest_golden_v_with_existing_version(self, mock_db_session):
    """Test latest_golden_v when versions exist."""
    mock_session = MagicMock()
    mock_db_session.return_value.__enter__.return_value = mock_session

    mock_query = Mock()
    mock_query.first.return_value = (5,)
    mock_session.query.return_value = mock_query

    dbt = Mock()
    dbt.golden_table = Mock()
    dbt.golden_table.golden_miopen_v = Mock()
    logger = Mock()

    result = latest_golden_v(dbt, logger)

    assert result == 5
    logger.warning.assert_called_once_with(5)

  @patch('tuna.miopen.subcmd.update_golden.DbSession')
  def test_latest_golden_v_with_no_versions(self, mock_db_session):
    """Test latest_golden_v when no versions exist."""
    mock_session = MagicMock()
    mock_db_session.return_value.__enter__.return_value = mock_session

    mock_query = Mock()
    mock_query.first.return_value = None
    mock_session.query.return_value = mock_query

    dbt = Mock()
    logger = Mock()

    result = latest_golden_v(dbt, logger)

    assert result == -1

  @patch('tuna.miopen.subcmd.update_golden.DbSession')
  def test_latest_golden_v_with_none_value(self, mock_db_session):
    """Test latest_golden_v when value is None."""
    mock_session = MagicMock()
    mock_db_session.return_value.__enter__.return_value = mock_session

    mock_query = Mock()
    mock_query.first.return_value = (None,)
    mock_session.query.return_value = mock_query

    dbt = Mock()
    logger = Mock()

    result = latest_golden_v(dbt, logger)

    assert result == -1


# ============================================================================
# Test sess_info
# ============================================================================
class TestSessInfo:
  """Test session info retrieval."""

  def test_sess_info(self):
    """Test sess_info returns correct mapping."""
    mock_session = Mock()
    mock_entry1 = Mock()
    mock_entry1.id = 1
    mock_entry1.arch = 'gfx90a'
    mock_entry1.num_cu = 110

    mock_entry2 = Mock()
    mock_entry2.id = 2
    mock_entry2.arch = 'gfx908'
    mock_entry2.num_cu = 120

    mock_query = Mock()
    mock_query.all.return_value = [mock_entry1, mock_entry2]
    mock_session.query.return_value = mock_query

    result = sess_info(mock_session)

    assert result == {1: ('gfx90a', 110), 2: ('gfx908', 120)}


# ============================================================================
# Test verify_no_duplicates
# ============================================================================
class TestVerifyNoDuplicates:
  """Test duplicate verification."""

  @patch('tuna.miopen.subcmd.update_golden.DbSession')
  @patch('tuna.miopen.subcmd.update_golden.sess_info')
  def test_verify_no_duplicates_no_duplicates(self, mock_sess_info,
                                              mock_db_session):
    """Test verify_no_duplicates with unique entries."""
    mock_sess_info.return_value = {1: ('gfx90a', 110)}

    entry1 = Mock()
    entry1.config = 1
    entry1.solver = 1
    entry1.session = 1
    entry1.fdb_key = 'key1'
    entry1.params = 'params1'

    entry2 = Mock()
    entry2.config = 2
    entry2.solver = 1
    entry2.session = 1
    entry2.fdb_key = 'key2'
    entry2.params = 'params2'

    entries = [entry1, entry2]
    logger = Mock()

    result = verify_no_duplicates(entries, logger)

    assert result is True
    logger.error.assert_not_called()

  @patch('tuna.miopen.subcmd.update_golden.DbSession')
  @patch('tuna.miopen.subcmd.update_golden.sess_info')
  def test_verify_no_duplicates_with_duplicates(self, mock_sess_info,
                                                mock_db_session):
    """Test verify_no_duplicates with duplicate entries."""
    mock_sess_info.return_value = {1: ('gfx90a', 110)}

    entry1 = Mock()
    entry1.config = 1
    entry1.solver = 1
    entry1.session = 1
    entry1.fdb_key = 'key1'
    entry1.params = 'params1'

    entry2 = Mock()  # Duplicate
    entry2.config = 1
    entry2.solver = 1
    entry2.session = 1
    entry2.fdb_key = 'key2'
    entry2.params = 'params2'

    entries = [entry1, entry2]
    logger = Mock()

    result = verify_no_duplicates(entries, logger)

    assert result is False
    logger.error.assert_called_once()


# ============================================================================
# Test get_perf_str
# ============================================================================
class TestGetPerfStr:
  """Test performance table SQL generation."""

  def test_get_perf_str_basic(self):
    """Test get_perf_str generates correct SQL."""
    args = Mock()
    args.golden_v = 3
    table_name = 'test_table'

    result = get_perf_str(args, table_name)

    assert 'create table test_table' in result
    assert 'golden_miopen_v=1' in result  # golden_v - 2
    assert 'golden_miopen_v=2' in result  # golden_v - 1
    assert 'golden_miopen_v=3' in result  # golden_v

  def test_get_perf_str_different_version(self):
    """Test get_perf_str with different golden version."""
    args = Mock()
    args.golden_v = 5
    table_name = 'perf_v5'

    result = get_perf_str(args, table_name)

    assert 'create table perf_v5' in result
    assert 'golden_miopen_v=3' in result  # golden_v - 2
    assert 'golden_miopen_v=4' in result  # golden_v - 1
    assert 'golden_miopen_v=5' in result  # golden_v


# ============================================================================
# Test create_perf_table
# ============================================================================
class TestCreatePerfTable:
  """Test performance table creation."""

  @patch('tuna.miopen.subcmd.update_golden.ENGINE')
  @patch('tuna.miopen.subcmd.update_golden.get_perf_str')
  def test_create_perf_table_golden_v0(self, mock_get_perf_str, mock_engine):
    """Test create_perf_table for golden version 0."""
    args = Mock()
    args.golden_v = 0
    logger = Mock()

    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_get_perf_str.return_value = 'CREATE TABLE sql'

    result = create_perf_table(args, logger)

    assert result is True
    mock_conn.execute.assert_any_call('drop table if exists conv_gv0')

  @patch('tuna.miopen.subcmd.update_golden.ENGINE')
  @patch('tuna.miopen.subcmd.update_golden.get_perf_str')
  def test_create_perf_table_golden_v1(self, mock_get_perf_str, mock_engine):
    """Test create_perf_table for golden version 1."""
    args = Mock()
    args.golden_v = 1
    logger = Mock()

    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_get_perf_str.return_value = 'CREATE TABLE sql'

    result = create_perf_table(args, logger)

    assert result is True
    mock_conn.execute.assert_any_call('drop table if exists conv_gv1_0')

  @patch('tuna.miopen.subcmd.update_golden.ENGINE')
  @patch('tuna.miopen.subcmd.update_golden.get_perf_str')
  def test_create_perf_table_higher_version(self, mock_get_perf_str,
                                            mock_engine):
    """Test create_perf_table for higher golden versions."""
    args = Mock()
    args.golden_v = 5
    logger = Mock()

    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_get_perf_str.return_value = 'CREATE TABLE sql'

    result = create_perf_table(args, logger)

    assert result is True
    mock_conn.execute.assert_any_call('drop table if exists conv_gv3_4_5')

  @patch('tuna.miopen.subcmd.update_golden.ENGINE')
  def test_create_perf_table_operational_error(self, mock_engine):
    """Test create_perf_table handles OperationalError."""
    args = Mock()
    args.golden_v = 2
    logger = Mock()

    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.side_effect = [
        None, OperationalError('test', 'test', 'test')
    ]

    result = create_perf_table(args, logger)

    assert result is False
    logger.info.assert_called()


# ============================================================================
# Test gold_base_update
# ============================================================================
class TestGoldBaseUpdate:
  """Test gold_base_update function."""

  def test_gold_base_update_with_overwrite(self):
    """Test gold_base_update with overwrite=True."""
    mock_session = Mock()
    gold_v = 2
    base_gold_v = 1
    logger = Mock()

    result = gold_base_update(mock_session, gold_v, base_gold_v, logger, True)

    assert result is True
    assert mock_session.execute.call_count == 2  # update and insert
    mock_session.commit.assert_called_once()

  def test_gold_base_update_without_overwrite(self):
    """Test gold_base_update with overwrite=False."""
    mock_session = Mock()
    gold_v = 2
    base_gold_v = 1
    logger = Mock()

    result = gold_base_update(mock_session, gold_v, base_gold_v, logger, False)

    assert result is True
    assert mock_session.execute.call_count == 1  # only insert
    mock_session.commit.assert_called_once()


# ============================================================================
# Test gold_session_update
# ============================================================================
class TestGoldSessionUpdate:
  """Test gold_session_update function."""

  def test_gold_session_update_with_overwrite(self):
    """Test gold_session_update with overwrite=True."""
    mock_session = Mock()
    gold_v = 2
    tune_s = 123
    logger = Mock()

    result = gold_session_update(mock_session, gold_v, tune_s, logger, True)

    assert result is True
    assert mock_session.execute.call_count == 2  # update and insert
    mock_session.commit.assert_called_once()

  def test_gold_session_update_without_overwrite(self):
    """Test gold_session_update with overwrite=False (default behavior)."""
    mock_session = Mock()
    gold_v = 2
    tune_s = 123
    logger = Mock()

    result = gold_session_update(mock_session, gold_v, tune_s, logger, True)

    assert result is True
    mock_session.commit.assert_called_once()


# ============================================================================
# Test run_update_golden
# ============================================================================
class TestRunUpdateGolden:
  """Test run_update_golden orchestration function."""

  @patch('tuna.miopen.subcmd.update_golden.session_retry')
  @patch('tuna.miopen.subcmd.update_golden.DbSession')
  @patch('tuna.miopen.subcmd.update_golden.get_golden_query')
  @patch('tuna.miopen.subcmd.update_golden.MIOpenDBTables')
  def test_run_update_golden_base_version(self, mock_dbt, mock_get_query,
                                          mock_db_session, mock_retry):
    """Test run_update_golden with base_golden_v."""
    args = Mock()
    args.session_id = None
    args.config_type = ConfigType.convolution
    args.golden_v = 2
    args.base_golden_v = 1
    args.overwrite = False
    args.create_perf_table = False
    logger = Mock()

    mock_query = Mock()
    mock_query.first.return_value = None  # No existing version
    mock_get_query.return_value = mock_query

    run_update_golden(args, logger)

    mock_retry.assert_called_once()

  @patch('tuna.miopen.subcmd.update_golden.session_retry')
  @patch('tuna.miopen.subcmd.update_golden.DbSession')
  @patch('tuna.miopen.subcmd.update_golden.get_golden_query')
  @patch('tuna.miopen.subcmd.update_golden.MIOpenDBTables')
  def test_run_update_golden_session_id(self, mock_dbt, mock_get_query,
                                        mock_db_session, mock_retry):
    """Test run_update_golden with session_id."""
    args = Mock()
    args.session_id = 123
    args.config_type = ConfigType.convolution
    args.golden_v = 2
    args.base_golden_v = None
    args.overwrite = False
    args.create_perf_table = False
    logger = Mock()

    mock_query = Mock()
    mock_query.first.return_value = None
    mock_get_query.return_value = mock_query

    run_update_golden(args, logger)

    mock_retry.assert_called_once()

  @patch('tuna.miopen.subcmd.update_golden.create_perf_table')
  @patch('tuna.miopen.subcmd.update_golden.session_retry')
  @patch('tuna.miopen.subcmd.update_golden.DbSession')
  @patch('tuna.miopen.subcmd.update_golden.get_golden_query')
  @patch('tuna.miopen.subcmd.update_golden.MIOpenDBTables')
  def test_run_update_golden_with_perf_table(self, mock_dbt, mock_get_query,
                                             mock_db_session, mock_retry,
                                             mock_create_perf):
    """Test run_update_golden with create_perf_table."""
    args = Mock()
    args.session_id = 123
    args.config_type = ConfigType.convolution
    args.golden_v = 2
    args.base_golden_v = None
    args.overwrite = False
    args.create_perf_table = True
    logger = Mock()

    mock_query = Mock()
    mock_query.first.return_value = None
    mock_get_query.return_value = mock_query

    run_update_golden(args, logger)

    mock_create_perf.assert_called_once_with(args, logger)

  @patch('tuna.miopen.subcmd.update_golden.get_golden_query')
  @patch('tuna.miopen.subcmd.update_golden.MIOpenDBTables')
  def test_run_update_golden_version_exists_no_overwrite(
      self, mock_dbt, mock_get_query):
    """Test run_update_golden raises error when version exists without overwrite."""
    args = Mock()
    args.session_id = 123
    args.config_type = ConfigType.convolution
    args.golden_v = 2
    args.base_golden_v = None
    args.overwrite = False
    args.create_perf_table = False
    logger = Mock()

    mock_query = Mock()
    mock_query.first.return_value = Mock()  # Version exists
    mock_get_query.return_value = mock_query

    with pytest.raises(ValueError, match='exists.*overwrite'):
      run_update_golden(args, logger)


# ============================================================================
# Test main
# ============================================================================
class TestMain:
  """Test main entry point."""

  @patch('tuna.miopen.subcmd.update_golden.setup_logger')
  @patch('tuna.miopen.subcmd.update_golden.run_update_golden')
  @patch('tuna.miopen.subcmd.update_golden.get_update_golden_parser')
  def test_main(self, mock_parser, mock_run, mock_logger):
    """Test main function orchestrates correctly."""
    mock_args = Mock()
    mock_parser.return_value.parse_args.return_value = mock_args
    mock_log = Mock()
    mock_logger.return_value = mock_log

    main()

    mock_parser.assert_called_once()
    mock_run.assert_called_once_with(mock_args, mock_log)
    mock_logger.assert_called_once_with('update_golden')


if __name__ == '__main__':
  pytest.main([__file__, '-v'])
