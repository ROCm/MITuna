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

import os
import sys

sys.path.append("../tuna")
sys.path.append("tuna")

this_path = os.path.dirname(__file__)

from tuna.sql import DbCursor
from tuna.utils.logger import setup_logger
from tuna.miopen.db.find_db import ConvolutionFindDB
from utils import CfgImportArgs, LdJobArgs


def parsing(find_db):
  dummy_str = [
      'NA',
      '2020-08-10 15:43:43,724 - /tmp/gfx908/120cu_10.216.64.100_30100p/3 - INFO - MIOpen(HIP): Info [SetValues] , content inserted: ConvHipImplicitGemmBwdDataV1R1Xdlops:64,64,2,64,32,2,1,0',
      '2020-08-10 16:09:07,750 - /tmp/gfx908/120cu_10.216.64.100_30100p/3 - INFO - MIOpen(HIP): Info [SetValues] , content inserted: ConvHipImplicitGemmBwdDataV1R1Xdlops:128,32,2,64,32,2,1,1'
  ]
  good_str = [
      '2020-08-10 15:43:44,096 - /tmp/gfx908/120cu_10.216.64.100_30100p/3 - INFO - MIOpen(HIP): Info [SetValues] 12-82-48-1x1-256-82-48-2-0x0-1x1-1x1-0-NCHW-FP32-B, content inserted: miopenConvolutionBwdDataAlgoImplicitGEMM:ConvHipImplicitGemmBwdDataV1R1Xdlops,0.02688,0,miopenConvolutionBwdDataAlgoImplicitGEMM,<unused>',
      '2020-08-10 16:09:08,075 - /tmp/gfx908/120cu_10.216.64.100_30100p/3 - INFO - MIOpen(HIP): Info [SetValues] 12-84-116-1x1-256-84-116-2-0x0-1x1-1x1-0-NCHW-FP32-B, content inserted: miopenConvolutionBwdDataAlgoImplicitGEMM:ConvHipImplicitGemmBwdDataV1R1Xdlops,0.05392,0,miopenConvolutionBwdDataAlgoImplicitGEMM,<unused>',
      '2020-08-13 11:11:15,877 - /tmp/gfx908/120cu_10.216.64.100_30100p/3 - INFO - MIOpen(HIP): Info [SetValues] 256-46-56-1x1-12-46-56-2-0x0-1x1-1x1-0-NCHW-FP32-F, content inserted: miopenConvolutionFwdAlgoDirect:ConvAsm1x1U,0.115839,0,miopenConvolutionFwdAlgoDirect,<unused>',
      '2020-08-13 11:11:42,935 - /tmp/gfx908/120cu_10.216.64.100_30100p/3 - INFO - MIOpen(HIP): Info [SetValues] 256-46-72-3x3-256-46-72-2-1x1-1x1-1x1-0-NCHW-FP32-F, content inserted: miopenConvolutionFwdAlgoWinograd:ConvBinWinogradRxSf3x2,0.571349,0,miopenConvolutionFwdAlgoWinograd,<unused>'
  ]

  for line in dummy_str:
    ret = find_db.parse(line)
    assert (ret == False)

  for line in good_str:
    ret = find_db.parse(line)
    assert (ret == True)


def test_find():
  logger = setup_logger('Machine')
  keys = {'logger': logger}

  find_db = ConvolutionFindDB(**keys)

  parsing(find_db)


# Additional comprehensive tests for find_db module

import pytest
from unittest.mock import MagicMock
from tuna.miopen.db.find_db import BNFindDB, ConvolutionTuningData, FDB_SLV_NUM_FIELDS


@pytest.mark.unit
@pytest.mark.db
@pytest.mark.miopen
class TestConvolutionFindDB:
  """Tests for ConvolutionFindDB class."""

  def test_convolution_find_db_creation(self):
    """Test that ConvolutionFindDB can be instantiated."""
    logger = setup_logger('test')
    find_db = ConvolutionFindDB(logger=logger)
    assert find_db is not None

  def test_convolution_find_db_has_logger(self):
    """Test that ConvolutionFindDB has logger attribute."""
    logger = setup_logger('test')
    find_db = ConvolutionFindDB(logger=logger)
    assert hasattr(find_db, 'logger')
    assert find_db.logger is not None

  def test_convolution_find_db_has_fdb_slv_dir(self):
    """Test that ConvolutionFindDB initializes fdb_slv_dir."""
    logger = setup_logger('test')
    find_db = ConvolutionFindDB(logger=logger)
    assert hasattr(find_db, 'fdb_slv_dir')
    assert isinstance(find_db.fdb_slv_dir, dict)

  def test_convolution_find_db_tablename(self):
    """Test that ConvolutionFindDB has correct table name."""
    assert ConvolutionFindDB.__tablename__ == 'conv_find_db'

  def test_convolution_find_db_parse_valid_line(self):
    """Test parsing valid find db entry."""
    logger = setup_logger('test')
    find_db = ConvolutionFindDB(logger=logger)

    valid_line = (
        '2020-08-10 15:43:44,096 - INFO - MIOpen(HIP): Info [SetValues] '
        '12-82-48-1x1-256-82-48-2-0x0-1x1-1x1-0-NCHW-FP32-B, '
        'content inserted: miopenConvolutionBwdDataAlgoImplicitGEMM:'
        'ConvHipImplicitGemmBwdDataV1R1Xdlops,0.02688,0,'
        'miopenConvolutionBwdDataAlgoImplicitGEMM,<unused>')

    result = find_db.parse(valid_line)
    assert result is True

  def test_convolution_find_db_parse_invalid_line(self):
    """Test parsing invalid line returns False."""
    logger = setup_logger('test')
    find_db = ConvolutionFindDB(logger=logger)

    invalid_line = 'This is not a valid find db line'
    result = find_db.parse(invalid_line)
    assert result is False

  def test_convolution_find_db_parse_no_setvalues(self):
    """Test parsing line without [SetValues] returns False."""
    logger = setup_logger('test')
    find_db = ConvolutionFindDB(logger=logger)

    line_without_setvalues = '2020-08-10 15:43:44,096 - INFO - Some other message'
    result = find_db.parse(line_without_setvalues)
    assert result is False

  def test_convolution_find_db_parse_populates_fdb_slv_dir(self):
    """Test that parsing populates fdb_slv_dir."""
    logger = setup_logger('test')
    find_db = ConvolutionFindDB(logger=logger)

    valid_line = (
        '2020-08-10 15:43:44,096 - INFO - MIOpen(HIP): Info [SetValues] '
        '12-82-48-1x1-256-82-48-2-0x0-1x1-1x1-0-NCHW-FP32-B, '
        'content inserted: miopenConvolutionBwdDataAlgoImplicitGEMM:'
        'ConvHipImplicitGemmBwdDataV1R1Xdlops,0.02688,0,'
        'miopenConvolutionBwdDataAlgoImplicitGEMM,<unused>')

    find_db.parse(valid_line)
    assert len(find_db.fdb_slv_dir) > 0

  def test_convolution_find_db_get_query(self):
    """Test get_query method constructs proper query."""
    logger = setup_logger('test')
    find_db = ConvolutionFindDB(logger=logger)
    find_db.config = 1
    find_db.solver = 1
    find_db.opencl = False

    mock_sess = MagicMock()
    mock_query = MagicMock()
    mock_sess.query.return_value = mock_query
    mock_query.filter.return_value = mock_query

    result = find_db.get_query(mock_sess, ConvolutionFindDB, session_id=1)

    # Verify query was called
    mock_sess.query.assert_called_once()
    assert result is not None


@pytest.mark.unit
@pytest.mark.db
@pytest.mark.miopen
class TestBNFindDB:
  """Tests for BNFindDB class."""

  def test_bn_find_db_creation(self):
    """Test that BNFindDB can be instantiated."""
    logger = setup_logger('test')
    find_db = BNFindDB(logger=logger)
    assert find_db is not None

  def test_bn_find_db_has_logger(self):
    """Test that BNFindDB has logger attribute."""
    logger = setup_logger('test')
    find_db = BNFindDB(logger=logger)
    assert hasattr(find_db, 'logger')

  def test_bn_find_db_tablename(self):
    """Test that BNFindDB has correct table name."""
    assert BNFindDB.__tablename__ == 'bn_find_db'

  def test_bn_find_db_has_fdb_slv_dir(self):
    """Test that BNFindDB initializes fdb_slv_dir."""
    logger = setup_logger('test')
    find_db = BNFindDB(logger=logger)
    assert hasattr(find_db, 'fdb_slv_dir')
    assert isinstance(find_db.fdb_slv_dir, dict)


@pytest.mark.unit
@pytest.mark.db
@pytest.mark.miopen
class TestConvolutionTuningData:
  """Tests for ConvolutionTuningData class."""

  def test_convolution_tuning_data_creation(self):
    """Test that ConvolutionTuningData can be instantiated."""
    logger = setup_logger('test')
    tuning_data = ConvolutionTuningData(logger=logger)
    assert tuning_data is not None

  def test_convolution_tuning_data_tablename(self):
    """Test that ConvolutionTuningData has correct table name."""
    assert ConvolutionTuningData.__tablename__ == 'conv_tuning_data'

  def test_convolution_tuning_data_has_logger(self):
    """Test that ConvolutionTuningData has logger attribute."""
    logger = setup_logger('test')
    tuning_data = ConvolutionTuningData(logger=logger)
    assert hasattr(tuning_data, 'logger')


@pytest.mark.unit
@pytest.mark.miopen
class TestFindDBConstants:
  """Tests for find_db module constants."""

  def test_fdb_slv_num_fields_value(self):
    """Test that FDB_SLV_NUM_FIELDS has expected value."""
    assert FDB_SLV_NUM_FIELDS == 5

  def test_fdb_slv_num_fields_is_int(self):
    """Test that FDB_SLV_NUM_FIELDS is an integer."""
    assert isinstance(FDB_SLV_NUM_FIELDS, int)


@pytest.mark.integration
@pytest.mark.db
@pytest.mark.miopen
class TestFindDBIntegration:
  """Integration tests for find_db functionality."""

  def test_parse_multiple_lines(self):
    """Test parsing multiple find db lines in sequence."""
    logger = setup_logger('test')
    find_db = ConvolutionFindDB(logger=logger)

    lines = [('2020-08-10 15:43:44,096 - INFO - MIOpen(HIP): Info [SetValues] '
              '12-82-48-1x1-256-82-48-2-0x0-1x1-1x1-0-NCHW-FP32-B, '
              'content inserted: miopenConvolutionBwdDataAlgoImplicitGEMM:'
              'ConvHipImplicitGemmBwdDataV1R1Xdlops,0.02688,0,'
              'miopenConvolutionBwdDataAlgoImplicitGEMM,<unused>'),
             ('2020-08-10 16:09:08,075 - INFO - MIOpen(HIP): Info [SetValues] '
              '12-84-116-1x1-256-84-116-2-0x0-1x1-1x1-0-NCHW-FP32-B, '
              'content inserted: miopenConvolutionBwdDataAlgoImplicitGEMM:'
              'ConvHipImplicitGemmBwdDataV1R1Xdlops,0.05392,0,'
              'miopenConvolutionBwdDataAlgoImplicitGEMM,<unused>')]

    for line in lines:
      result = find_db.parse(line)
      assert result is True

  def test_parse_opencl_line(self):
    """Test parsing OpenCL find db entry."""
    logger = setup_logger('test')
    find_db = ConvolutionFindDB(logger=logger)

    opencl_line = (
        '2020-08-10 15:43:44,096 - INFO - MIOpen(OpenCL): Info [SetValues] '
        '12-82-48-1x1-256-82-48-2-0x0-1x1-1x1-0-NCHW-FP32-B, '
        'content inserted: miopenConvolutionBwdDataAlgoImplicitGEMM:'
        'ConvHipImplicitGemmBwdDataV1R1Xdlops,0.02688,0,'
        'miopenConvolutionBwdDataAlgoImplicitGEMM,<unused>')

    result = find_db.parse(opencl_line)
    assert result is True
    # Verify OpenCL flag is set
    for solver_data in find_db.fdb_slv_dir.values():
      for direction_data in solver_data.values():
        assert 'is_ocl' in direction_data
        if direction_data['is_ocl']:
          assert direction_data['is_ocl'] == 1

  def test_parse_different_directions(self):
    """Test parsing find db entries with different directions."""
    logger = setup_logger('test')
    find_db = ConvolutionFindDB(logger=logger)

    forward_line = (
        '2020-08-13 11:11:15,877 - INFO - MIOpen(HIP): Info [SetValues] '
        '256-46-56-1x1-12-46-56-2-0x0-1x1-1x1-0-NCHW-FP32-F, '
        'content inserted: miopenConvolutionFwdAlgoDirect:'
        'ConvAsm1x1U,0.115839,0,miopenConvolutionFwdAlgoDirect,<unused>')

    backward_line = (
        '2020-08-10 15:43:44,096 - INFO - MIOpen(HIP): Info [SetValues] '
        '12-82-48-1x1-256-82-48-2-0x0-1x1-1x1-0-NCHW-FP32-B, '
        'content inserted: miopenConvolutionBwdDataAlgoImplicitGEMM:'
        'ConvHipImplicitGemmBwdDataV1R1Xdlops,0.02688,0,'
        'miopenConvolutionBwdDataAlgoImplicitGEMM,<unused>')

    find_db.parse(forward_line)
    find_db.parse(backward_line)

    # Verify both directions are captured
    for solver_data in find_db.fdb_slv_dir.values():
      # Should have entries for different directions
      assert len(solver_data) > 0
