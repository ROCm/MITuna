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

import sys
import logging
import pytest
from tuna.miopen.subcmd.update_golden import (
    arg_update_golden, get_golden_query, gold_base_update, gold_session_update,
    create_perf_table, verify_no_duplicates, latest_golden_v)
from tuna.miopen.db.tables import MIOpenDBTables
from tuna.dbBase.sql_alchemy import DbSession
from tuna.miopen.utils.config_type import ConfigType
from tuna.miopen.db.convolutionjob_tables import ConvolutionGolden
from tuna.miopen.db.find_db import ConvolutionFindDB
from utils import add_test_session, DummyArgs, build_fdb_entry

sys.path.append("../tuna")
sys.path.append("tuna")

logger = logging.getLogger("update_golden_test_logger")


@pytest.fixture(scope='module')
def test_session_id():
  """Create test session once per module."""
  session_id = add_test_session(arch='gfx908',
                                num_cu=120,
                                label='pytest_update_golden')
  return session_id


@pytest.fixture
def test_args(test_session_id):
  """Create test args with session."""
  args = DummyArgs()
  args.session_id = test_session_id
  args.config_type = ConfigType.convolution
  args.base_golden_v = 1.0
  args.golden_version = 1.1
  return args


@pytest.fixture
def test_dbt(test_session_id):
  """Create MIOpenDBTables for tests."""
  return MIOpenDBTables(session_id=test_session_id,
                        config_type=ConfigType.convolution)


@pytest.mark.db
def test_args_golden(test_args):
  """Test argument validation for update_golden."""
  results = arg_update_golden(test_args, logger)
  assert results is not None
  assert results.base_golden_v == test_args.base_golden_v


@pytest.mark.db
def test_update_golden(test_session_id, test_args, test_dbt):
  """Test update golden with database operations and cleanup."""
  # Clean up any existing test data first
  with DbSession() as session:
    # Delete existing find_db entries for this test
    session.query(ConvolutionFindDB).filter(
        ConvolutionFindDB.session == test_session_id).delete()
    session.commit()

  # Create and insert test entry
  fdb_entry = build_fdb_entry(test_session_id)
  with DbSession() as session:
    session.add(fdb_entry)
    session.commit()

  try:
    gld_v1 = latest_golden_v(test_dbt, logger) + 1
    test_args.golden_v = gld_v1

    with DbSession() as session:
      assert gold_session_update(session, gld_v1, test_session_id, logger, True)
      query = session.query(ConvolutionGolden)\
                      .filter(ConvolutionGolden.golden_miopen_v == gld_v1)\
                      .filter(ConvolutionGolden.session == test_session_id)
      res = query.all()
      assert len(res) == 1
      assert res[0].params == 'param'

      gld_v2 = gld_v1 + 1
      assert gold_base_update(session, gld_v2, gld_v1, logger, True)
      query = session.query(ConvolutionGolden)\
                      .filter(ConvolutionGolden.golden_miopen_v == gld_v2)\
                      .filter(ConvolutionGolden.session == test_session_id)
      res = query.all()
      assert len(res) == 1
      assert res[0].params == 'param'

    # Test verify_no_duplicates
    with DbSession() as session:
      entries = session.query(ConvolutionFindDB)\
                      .filter(ConvolutionFindDB.session == test_session_id).all()
      assert verify_no_duplicates(entries, logger)

      fdb_entry2 = build_fdb_entry(test_session_id)
      fdb_entry2.config = 2
      entries.append(fdb_entry2)
      assert verify_no_duplicates(entries, logger)

      fdb_entry3 = build_fdb_entry(test_session_id)
      fdb_entry3.solver = 2
      entries.append(fdb_entry3)
      assert verify_no_duplicates(entries, logger)

      session_id2 = add_test_session(arch='gfx90a',
                                     num_cu=110,
                                     label='pytest_update_golden2')
      fdb_entry4 = build_fdb_entry(session_id2)
      entries.append(fdb_entry4)
      assert verify_no_duplicates(entries, logger)

      fdb_entry5 = build_fdb_entry(test_session_id)
      fdb_entry5.params = 'something'
      entries.append(fdb_entry5)
      assert verify_no_duplicates(entries, logger) == False

    test_args.create_perf_table = True
    assert create_perf_table(test_args, logger)

  finally:
    # Cleanup: Remove test data
    with DbSession() as session:
      session.query(ConvolutionGolden).filter(
          ConvolutionGolden.session == test_session_id).delete()
      session.query(ConvolutionFindDB).filter(
          ConvolutionFindDB.session == test_session_id).delete()
      session.commit()


def copy(dest, src):
  """Helper function to copy object attributes."""
  dest.__dict__ = src.__dict__.copy()
