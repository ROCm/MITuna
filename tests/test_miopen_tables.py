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
Tests for MIOpen table management module.

This module tests table addition functions in tuna/miopen/db/miopen_tables.py.
"""

import pytest

from tuna.miopen.db.miopen_tables import (add_conv_tables, add_fusion_tables,
                                          add_bn_tables, COMMON_UNIQ_FDS)
from tuna.miopen.db.convolutionjob_tables import (
    ConvolutionConfig, ConvolutionJob, ConvolutionConfigTags,
    ConvSolverApplicability, ConvolutionKernelCache, ConvJobCache,
    ConvFinJobCache, ConvolutionGolden, ConvSolverAnalyticsAggregated,
    ConvSolverAnalyticsDetailed, ConvolutionBenchmark)
from tuna.miopen.db.find_db import ConvolutionFindDB, ConvolutionTuningData, BNFindDB
from tuna.miopen.db.batch_norm_tables import (BNConfig, BNJob, BNConfigTags,
                                              BNSolverApplicability,
                                              BNKernelCache, BNJobCache,
                                              BNFinJobCache, BNBenchmark)
from tuna.miopen.db.bn_golden_tables import BNGolden
from tuna.miopen.db.fusion_config_tables import (FusionConfig,
                                                 SolverFusionApplicability,
                                                 FusionJob, FusionConfigTags)

# ============================================================================
# Tests for add_conv_tables
# ============================================================================


@pytest.mark.unit
@pytest.mark.db
@pytest.mark.miopen
class TestConvolutionTables:
  """Tests for convolution table addition."""

  def test_add_conv_tables_returns_list(self):
    """Test that add_conv_tables returns a list."""
    result = add_conv_tables([])
    assert isinstance(result, list)

  def test_add_conv_tables_adds_all_tables(self):
    """Test that all convolution tables are added."""
    tables = add_conv_tables([])

    # Should add 13 convolution-specific tables
    assert len(tables) == 13

  def test_add_conv_tables_contains_config_table(self):
    """Test that ConvolutionConfig table is added."""
    tables = add_conv_tables([])
    config_tables = [t for t in tables if isinstance(t, ConvolutionConfig)]
    assert len(config_tables) == 1

  def test_add_conv_tables_contains_job_table(self):
    """Test that ConvolutionJob table is added."""
    tables = add_conv_tables([])
    job_tables = [t for t in tables if isinstance(t, ConvolutionJob)]
    assert len(job_tables) == 1

  def test_add_conv_tables_contains_all_required_tables(self):
    """Test that all required convolution tables are included."""
    tables = add_conv_tables([])

    required_types = [
        ConvolutionConfig, ConvolutionJob, ConvolutionConfigTags,
        ConvSolverApplicability, ConvolutionKernelCache, ConvJobCache,
        ConvFinJobCache, ConvolutionFindDB, ConvolutionTuningData,
        ConvolutionGolden, ConvSolverAnalyticsAggregated,
        ConvSolverAnalyticsDetailed, ConvolutionBenchmark
    ]

    for req_type in required_types:
      matching = [t for t in tables if isinstance(t, req_type)]
      assert len(matching) == 1, f"Expected exactly one {req_type.__name__}"

  def test_add_conv_tables_appends_to_existing(self):
    """Test that add_conv_tables appends to existing list."""
    existing = ["dummy_table"]
    tables = add_conv_tables(existing)

    assert len(tables) == 14  # 1 existing + 13 new
    assert tables[0] == "dummy_table"

  def test_add_conv_tables_order(self):
    """Test that tables are added in expected order."""
    tables = add_conv_tables([])

    # First table should be ConvolutionConfig
    assert isinstance(tables[0], ConvolutionConfig)
    # Second table should be ConvolutionJob
    assert isinstance(tables[1], ConvolutionJob)


# ============================================================================
# Tests for add_fusion_tables
# ============================================================================


@pytest.mark.unit
@pytest.mark.db
@pytest.mark.miopen
class TestFusionTables:
  """Tests for fusion table addition."""

  def test_add_fusion_tables_returns_list(self):
    """Test that add_fusion_tables returns a list."""
    result = add_fusion_tables([])
    assert isinstance(result, list)

  def test_add_fusion_tables_adds_all_tables(self):
    """Test that all fusion tables are added."""
    tables = add_fusion_tables([])

    # Should add 4 fusion-specific tables
    assert len(tables) == 4

  def test_add_fusion_tables_contains_all_required_tables(self):
    """Test that all required fusion tables are included."""
    tables = add_fusion_tables([])

    required_types = [
        FusionConfig, SolverFusionApplicability, FusionJob, FusionConfigTags
    ]

    for req_type in required_types:
      matching = [t for t in tables if isinstance(t, req_type)]
      assert len(matching) == 1, f"Expected exactly one {req_type.__name__}"

  def test_add_fusion_tables_appends_to_existing(self):
    """Test that add_fusion_tables appends to existing list."""
    existing = ["dummy_table"]
    tables = add_fusion_tables(existing)

    assert len(tables) == 5  # 1 existing + 4 new
    assert tables[0] == "dummy_table"

  def test_add_fusion_tables_order(self):
    """Test that tables are added in expected order."""
    tables = add_fusion_tables([])

    # First table should be FusionConfig
    assert isinstance(tables[0], FusionConfig)


# ============================================================================
# Tests for add_bn_tables
# ============================================================================


@pytest.mark.unit
@pytest.mark.db
@pytest.mark.miopen
class TestBatchNormTables:
  """Tests for batch norm table addition."""

  def test_add_bn_tables_returns_list(self):
    """Test that add_bn_tables returns a list."""
    result = add_bn_tables([])
    assert isinstance(result, list)

  def test_add_bn_tables_adds_all_tables(self):
    """Test that all batch norm tables are added."""
    tables = add_bn_tables([])

    # Should add 10 batch norm-specific tables
    assert len(tables) == 10

  def test_add_bn_tables_contains_all_required_tables(self):
    """Test that all required batch norm tables are included."""
    tables = add_bn_tables([])

    required_types = [
        BNConfig, BNJob, BNConfigTags, BNSolverApplicability, BNKernelCache,
        BNJobCache, BNFinJobCache, BNFindDB, BNGolden, BNBenchmark
    ]

    for req_type in required_types:
      matching = [t for t in tables if isinstance(t, req_type)]
      assert len(matching) == 1, f"Expected exactly one {req_type.__name__}"

  def test_add_bn_tables_appends_to_existing(self):
    """Test that add_bn_tables appends to existing list."""
    existing = ["dummy_table"]
    tables = add_bn_tables(existing)

    assert len(tables) == 11  # 1 existing + 10 new
    assert tables[0] == "dummy_table"

  def test_add_bn_tables_order(self):
    """Test that tables are added in expected order."""
    tables = add_bn_tables([])

    # First table should be BNConfig
    assert isinstance(tables[0], BNConfig)
    # Second table should be BNJob
    assert isinstance(tables[1], BNJob)


# ============================================================================
# Tests for COMMON_UNIQ_FDS constant
# ============================================================================


@pytest.mark.unit
@pytest.mark.miopen
class TestConstants:
  """Tests for module constants."""

  def test_common_uniq_fds_exists(self):
    """Test that COMMON_UNIQ_FDS constant exists."""
    assert COMMON_UNIQ_FDS is not None

  def test_common_uniq_fds_is_list(self):
    """Test that COMMON_UNIQ_FDS is a list."""
    assert isinstance(COMMON_UNIQ_FDS, list)

  def test_common_uniq_fds_contains_expected_fields(self):
    """Test that COMMON_UNIQ_FDS contains expected fields."""
    expected_fields = ["config", "solver", "session"]
    assert COMMON_UNIQ_FDS == expected_fields


# ============================================================================
# Integration tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.db
@pytest.mark.miopen
class TestTableIntegration:
  """Integration tests for table management."""

  def test_all_table_functions_work_together(self):
    """Test that all table functions can be called in sequence."""
    tables = []
    tables = add_conv_tables(tables)
    tables = add_fusion_tables(tables)
    tables = add_bn_tables(tables)

    # Should have 13 + 4 + 10 = 27 tables
    assert len(tables) == 27

  def test_no_duplicate_tables(self):
    """Test that calling functions multiple times doesn't cause issues."""
    tables1 = []
    tables1 = add_conv_tables(tables1)

    tables2 = []
    tables2 = add_conv_tables(tables2)

    # Both should have same length
    assert len(tables1) == len(tables2)

  def test_tables_have_tablename_attribute(self):
    """Test that all added tables have __tablename__ attribute."""
    tables = []
    tables = add_conv_tables(tables)
    tables = add_fusion_tables(tables)
    tables = add_bn_tables(tables)

    for table in tables:
      assert hasattr(table, '__tablename__') or hasattr(table.__class__,
                                                        '__tablename__')
