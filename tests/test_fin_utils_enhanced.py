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
"""Enhanced comprehensive tests for fin_utils module"""

import pytest
from unittest.mock import Mock, MagicMock
import tuna.miopen.worker.fin_utils as fu
from tuna.miopen.db.convolutionjob_tables import ConvolutionConfig, ConvolutionJob
from tuna.miopen.db.tensortable import TensorTable
from tuna.miopen.db.tables import MIOpenDBTables
from tuna.miopen.db.session import Session
from tuna.miopen.utils.config_type import ConfigType


@pytest.fixture
def mock_dbt():
  """Create mock database tables"""
  dbt = Mock(spec=MIOpenDBTables)
  session = Mock(spec=Session)
  session.id = 1
  session.arch = 'gfx908'
  session.num_cu = 120
  dbt.session = session
  return dbt


@pytest.fixture
def mock_conv_job():
  """Create mock convolution job"""
  job = Mock(spec=ConvolutionJob)
  job.id = 1
  job.valid = 1
  job.config = 1
  job.solver = None
  return job


@pytest.fixture
def nchw_config():
  """Create NCHW convolution config"""
  config = Mock(spec=ConvolutionConfig)
  config.id = 1
  config.batchsize = 128
  config.spatial_dim = 2
  config.pad_h = 0
  config.pad_w = 3
  config.pad_d = 0
  config.conv_stride_h = 1
  config.conv_stride_w = 1
  config.conv_stride_d = 1
  config.dilation_h = 1
  config.dilation_w = 1
  config.dilation_d = 1
  config.group_count = 1
  config.mode = 'conv'
  config.pad_mode = 'default'
  config.trans_output_pad_h = 0
  config.trans_output_pad_w = 0
  config.trans_output_pad_d = 0
  config.out_layout = 'NCHW'
  config.direction = 'F'
  config.valid = 1

  # Mock input tensor
  input_t = Mock(spec=TensorTable)
  input_t.id = 1
  input_t.dim0 = 1
  input_t.dim1 = 128
  input_t.dim2 = 1
  input_t.dim3 = 17
  input_t.dim4 = 17
  input_t.layout = 'NCHW'
  input_t.num_dims = 2
  input_t.data_type = 'FP32'
  input_t.valid = 1
  input_t.to_dict = lambda: {
      'id': 1,
      'dim0': 1,
      'dim1': 128,
      'dim2': 1,
      'dim3': 17,
      'dim4': 17,
      'layout': 'NCHW',
      'num_dims': 2,
      'data_type': 'FP32',
      'valid': 1
  }

  # Mock weight tensor
  weight_t = Mock(spec=TensorTable)
  weight_t.id = 2
  weight_t.dim0 = 128
  weight_t.dim1 = 128
  weight_t.dim2 = 1
  weight_t.dim3 = 1
  weight_t.dim4 = 7
  weight_t.layout = 'NCHW'
  weight_t.num_dims = 2
  weight_t.data_type = 'FP32'
  weight_t.valid = 1
  weight_t.to_dict = lambda: {
      'id': 2,
      'dim0': 128,
      'dim1': 128,
      'dim2': 1,
      'dim3': 1,
      'dim4': 7,
      'layout': 'NCHW',
      'num_dims': 2,
      'data_type': 'FP32',
      'valid': 1
  }

  config.input_t = input_t
  config.weight_t = weight_t
  config.__dict__ = {
      'id': config.id,
      'batchsize': config.batchsize,
      'spatial_dim': config.spatial_dim,
      'pad_h': config.pad_h,
      'pad_w': config.pad_w,
      'pad_d': config.pad_d,
      'conv_stride_h': config.conv_stride_h,
      'conv_stride_w': config.conv_stride_w,
      'conv_stride_d': config.conv_stride_d,
      'dilation_h': config.dilation_h,
      'dilation_w': config.dilation_w,
      'dilation_d': config.dilation_d,
      'group_count': config.group_count,
      'mode': config.mode,
      'pad_mode': config.pad_mode,
      'trans_output_pad_h': config.trans_output_pad_h,
      'trans_output_pad_w': config.trans_output_pad_w,
      'trans_output_pad_d': config.trans_output_pad_d,
      'out_layout': config.out_layout,
      'direction': config.direction,
      'valid': config.valid,
      'input_t': input_t,
      'weight_t': weight_t
  }
  config.to_dict = lambda: {
      k: v for k, v in config.__dict__.items() if not k.startswith('_')
  }

  return config


@pytest.fixture
def nhwc_config():
  """Create NHWC convolution config"""
  config = Mock(spec=ConvolutionConfig)
  config.id = 2
  config.batchsize = 64
  config.spatial_dim = 2
  config.pad_h = 0
  config.pad_w = 3
  config.pad_d = 0
  config.conv_stride_h = 1
  config.conv_stride_w = 1
  config.conv_stride_d = 1
  config.dilation_h = 1
  config.dilation_w = 1
  config.dilation_d = 1
  config.group_count = 1
  config.mode = 'conv'
  config.pad_mode = 'default'
  config.trans_output_pad_h = 0
  config.trans_output_pad_w = 0
  config.trans_output_pad_d = 0
  config.out_layout = 'NHWC'
  config.direction = 'F'
  config.valid = 1

  # Mock input tensor (NHWC layout)
  input_t = Mock(spec=TensorTable)
  input_t.id = 3
  input_t.dim0 = 1
  input_t.dim1 = 64  # D
  input_t.dim2 = 1  # H
  input_t.dim3 = 9  # W
  input_t.dim4 = 21  # C
  input_t.layout = 'NHWC'
  input_t.num_dims = 2
  input_t.data_type = 'FP32'
  input_t.valid = 1
  input_t.to_dict = lambda: {
      'id': 3,
      'dim0': 1,
      'dim1': 64,
      'dim2': 1,
      'dim3': 9,
      'dim4': 21,
      'layout': 'NHWC',
      'num_dims': 2,
      'data_type': 'FP32',
      'valid': 1
  }

  # Mock weight tensor (NHWC layout)
  weight_t = Mock(spec=TensorTable)
  weight_t.id = 4
  weight_t.dim0 = 64
  weight_t.dim1 = 64
  weight_t.dim2 = 1
  weight_t.dim3 = 13
  weight_t.dim4 = 9
  weight_t.layout = 'NHWC'
  weight_t.num_dims = 2
  weight_t.data_type = 'FP32'
  weight_t.valid = 1
  weight_t.to_dict = lambda: {
      'id': 4,
      'dim0': 64,
      'dim1': 64,
      'dim2': 1,
      'dim3': 13,
      'dim4': 9,
      'layout': 'NHWC',
      'num_dims': 2,
      'data_type': 'FP32',
      'valid': 1
  }

  config.input_t = input_t
  config.weight_t = weight_t
  config.__dict__ = {
      'id': config.id,
      'batchsize': config.batchsize,
      'spatial_dim': config.spatial_dim,
      'pad_h': config.pad_h,
      'pad_w': config.pad_w,
      'pad_d': config.pad_d,
      'conv_stride_h': config.conv_stride_h,
      'conv_stride_w': config.conv_stride_w,
      'conv_stride_d': config.conv_stride_d,
      'dilation_h': config.dilation_h,
      'dilation_w': config.dilation_w,
      'dilation_d': config.dilation_d,
      'group_count': config.group_count,
      'mode': config.mode,
      'pad_mode': config.pad_mode,
      'trans_output_pad_h': config.trans_output_pad_h,
      'trans_output_pad_w': config.trans_output_pad_w,
      'trans_output_pad_d': config.trans_output_pad_d,
      'out_layout': config.out_layout,
      'direction': config.direction,
      'valid': config.valid,
      'input_t': input_t,
      'weight_t': weight_t
  }
  config.to_dict = lambda: {
      k: v for k, v in config.__dict__.items() if not k.startswith('_')
  }

  return config


@pytest.mark.unit
@pytest.mark.utils
class TestGetTensor:
  """Test get_tensor function"""

  def test_get_input_tensor_nchw(self, nchw_config):
    """Test getting input tensor for NCHW layout"""
    tensor_dict = nchw_config.input_t.to_dict()
    result = fu.get_tensor('in_layout', tensor_dict)

    assert result['in_layout'] == 'NCHW'
    assert result['in_channels'] == 128
    assert result['in_d'] == 1
    assert result['in_h'] == 17
    assert result['in_w'] == 17

  def test_get_input_tensor_nhwc(self, nhwc_config):
    """Test getting input tensor for NHWC layout"""
    tensor_dict = nhwc_config.input_t.to_dict()
    result = fu.get_tensor('in_layout', tensor_dict)

    assert result['in_layout'] == 'NHWC'
    assert result['in_d'] == 64
    assert result['in_h'] == 1
    assert result['in_w'] == 9
    assert result['in_channels'] == 21

  def test_get_weight_tensor_nchw(self, nchw_config):
    """Test getting weight tensor for NCHW layout"""
    tensor_dict = nchw_config.weight_t.to_dict()
    result = fu.get_tensor('wei_layout', tensor_dict)

    assert result['wei_layout'] == 'NCHW'
    assert result['out_channels'] == 128
    assert result['in_channels'] == 128
    assert result['fil_d'] == 1
    assert result['fil_h'] == 1
    assert result['fil_w'] == 7

  def test_get_weight_tensor_nhwc(self, nhwc_config):
    """Test getting weight tensor for NHWC layout"""
    tensor_dict = nhwc_config.weight_t.to_dict()
    result = fu.get_tensor('wei_layout', tensor_dict)

    assert result['wei_layout'] == 'NHWC'
    assert result['out_channels'] == 64
    assert result['in_channels'] == 64
    assert result['fil_d'] == 1
    assert result['fil_h'] == 13
    assert result['fil_w'] == 9

  @pytest.mark.parametrize("layout", ["NCHW", "NHWC", "NCDHW", "NDHWC"])
  def test_get_tensor_supported_layouts(self, layout):
    """Test all supported layouts"""
    tensor_dict = {
        'layout': layout,
        'dim0': 1,
        'dim1': 64,
        'dim2': 32,
        'dim3': 32,
        'dim4': 3
    }
    result = fu.get_tensor('in_layout', tensor_dict)
    assert result['in_layout'] == layout


@pytest.mark.unit
@pytest.mark.utils
class TestComposeConfigObj:
  """Test compose_config_obj function"""

  def test_compose_config_nchw(self, nchw_config):
    """Test composing config object for NCHW layout"""
    result = fu.compose_config_obj(nchw_config)

    assert result['id'] == 1
    assert result['batchsize'] == 128
    assert result['spatial_dim'] == 2
    assert result['in_layout'] == 'NCHW'
    assert result['in_channels'] == 128
    assert result['in_h'] == 17
    assert result['in_w'] == 17
    assert result['wei_layout'] == 'NCHW'
    assert result['out_channels'] == 128
    assert result['fil_h'] == 1
    assert result['fil_w'] == 7
    assert result['cmd'] == 'conv'
    assert result['direction'] == 'F'
    assert result['valid'] == 1

  def test_compose_config_nhwc(self, nhwc_config):
    """Test composing config object for NHWC layout"""
    result = fu.compose_config_obj(nhwc_config)

    assert result['id'] == 2
    assert result['batchsize'] == 64
    assert result['spatial_dim'] == 2
    assert result['in_layout'] == 'NHWC'
    assert result['in_d'] == 64
    assert result['in_h'] == 1
    assert result['in_w'] == 9
    assert result['in_channels'] == 64
    assert result['wei_layout'] == 'NHWC'
    assert result['out_channels'] == 64
    assert result['fil_d'] == 1
    assert result['fil_h'] == 13
    assert result['fil_w'] == 9
    assert result['cmd'] == 'conv'
    assert result['direction'] == 'F'

  def test_compose_config_removes_tensor_objects(self, nchw_config):
    """Test that tensor objects are removed from composed config"""
    result = fu.compose_config_obj(nchw_config)

    assert 'input_t' not in result
    assert 'weight_t' not in result

  def test_compose_config_with_batch_norm(self, mock_dbt):
    """Test composing config for batch normalization"""
    # Create a simple batch norm config
    bn_config = Mock()
    bn_config.id = 1
    bn_config.mode = 1
    bn_config.to_dict = lambda: {'id': 1, 'mode': 1}
    bn_config.__dict__ = {'keys': lambda: []}

    result = fu.compose_config_obj(bn_config, ConfigType.batch_norm)
    assert result is not None


@pytest.mark.unit
@pytest.mark.utils
class TestFinJob:
  """Test fin_job function"""

  def test_fin_job_basic(self, mock_dbt, mock_conv_job, nchw_config):
    """Test basic fin_job creation"""
    result = fu.fin_job("fin_find_compile", True, mock_conv_job, nchw_config,
                        mock_dbt)

    assert result['steps'] == 'fin_find_compile'
    assert result['arch'] == 'gfx908:sram-ecc+:xnack-'
    assert result['num_cu'] == 120
    assert result['config_tuna_id'] == 1
    assert result['direction'] == 1  # F = 1
    assert result['dynamic_only'] is True
    assert 'config' in result
    assert result['config']['id'] == 1

  def test_fin_job_with_solver(self, mock_dbt, mock_conv_job, nchw_config):
    """Test fin_job with solver specified"""
    mock_conv_job.solver = 5
    result = fu.fin_job("fin_find_compile", False, mock_conv_job, nchw_config,
                        mock_dbt)

    assert 'solvers' in result
    assert result['solvers'] == [5]
    assert result['dynamic_only'] is False

  def test_fin_job_without_solver(self, mock_dbt, mock_conv_job, nchw_config):
    """Test fin_job without solver"""
    mock_conv_job.solver = None
    result = fu.fin_job("applicability", True, mock_conv_job, nchw_config,
                        mock_dbt)

    assert 'solvers' not in result
    assert result['steps'] == 'applicability'

  @pytest.mark.parametrize(
      "step",
      ["fin_find_compile", "applicability", "get_solvers", "perf_compile"])
  def test_fin_job_different_steps(self, mock_dbt, mock_conv_job, nchw_config,
                                   step):
    """Test fin_job with different step types"""
    result = fu.fin_job(step, True, mock_conv_job, nchw_config, mock_dbt)
    assert result['steps'] == step

  @pytest.mark.parametrize("direction,expected", [("F", 1), ("B", 2), ("W", 4)])
  def test_fin_job_directions(self, mock_dbt, mock_conv_job, nchw_config,
                              direction, expected):
    """Test fin_job with different directions"""
    nchw_config.direction = direction
    result = fu.fin_job("fin_find_compile", True, mock_conv_job, nchw_config,
                        mock_dbt)
    assert result['direction'] == expected


@pytest.mark.unit
@pytest.mark.utils
class TestGetFinSlvStatus:
  """Test get_fin_slv_status function"""

  def test_get_fin_slv_status_success(self):
    """Test getting solver status with success"""
    json_obj = {
        'solver_name': 'ConvAsm1x1U',
        'compiled': True,
        'reason': 'Success'
    }
    result = fu.get_fin_slv_status(json_obj, 'compiled')

    assert result['solver'] == 'ConvAsm1x1U'
    assert result['success'] is True
    assert result['result'] == 'Success'

  def test_get_fin_slv_status_failure(self):
    """Test getting solver status with failure"""
    json_obj = {
        'solver_name': 'ConvOclDirectFwd',
        'compiled': False,
        'reason': 'Not applicable'
    }
    result = fu.get_fin_slv_status(json_obj, 'compiled')

    assert result['solver'] == 'ConvOclDirectFwd'
    assert result['success'] is False
    assert result['result'] == 'Not applicable'


@pytest.mark.unit
@pytest.mark.utils
class TestGetFinResult:
  """Test get_fin_result function"""

  def test_get_fin_result_all_success(self):
    """Test get_fin_result with all successful solvers"""
    status = [{
        'success': True,
        'solver': 'Solver1',
        'result': 'Success'
    }, {
        'success': True,
        'solver': 'Solver2',
        'result': 'Success'
    }]
    success, result_str = fu.get_fin_result(status)

    assert success is True
    assert result_str == 'Success'

  def test_get_fin_result_all_failure(self):
    """Test get_fin_result with all failed solvers"""
    status = [{
        'success': False,
        'solver': 'Solver1',
        'result': 'Not applicable'
    }, {
        'success': False,
        'solver': 'Solver2',
        'result': 'Not applicable'
    }]
    success, result_str = fu.get_fin_result(status)

    assert success is False
    assert result_str == 'Not applicable'

  def test_get_fin_result_mixed(self):
    """Test get_fin_result with mixed results"""
    status = [{
        'success': True,
        'solver': 'Solver1',
        'result': 'Success'
    }, {
        'success': False,
        'solver': 'Solver2',
        'result': 'Not applicable'
    }]
    success, result_str = fu.get_fin_result(status)

    assert success is True
    assert 'Solver1' in result_str or 'Solver2' in result_str

  def test_get_fin_result_legacy_solver(self):
    """Test get_fin_result with legacy solver"""
    status = [{
        'success': False,
        'solver': 'ConvAsmBwdWrW1x1',
        'result': 'Legacy Solver'
    }]
    success, result_str = fu.get_fin_result(status)

    # Legacy solvers are treated as success
    assert success is True
    assert 'Legacy' in result_str

  def test_get_fin_result_different_reasons(self):
    """Test get_fin_result with different failure reasons"""
    status = [{
        'success': False,
        'solver': 'Solver1',
        'result': 'Not applicable'
    }, {
        'success': False,
        'solver': 'Solver2',
        'result': 'Compilation failed'
    }]
    success, result_str = fu.get_fin_result(status)

    assert success is False
    # Should contain individual solver results
    assert 'Solver1' in result_str or 'Solver2' in result_str

  def test_get_fin_result_empty_status(self):
    """Test get_fin_result with empty status list"""
    status = []
    success, result_str = fu.get_fin_result(status)

    assert success is False
    assert result_str == ''


@pytest.mark.unit
@pytest.mark.utils
class TestGetTensorEdgeCases:
  """Test edge cases for get_tensor function"""

  def test_get_tensor_ncdhw_3d(self):
    """Test 3D tensor with NCDHW layout"""
    tensor_dict = {
        'layout': 'NCDHW',
        'dim0': 1,
        'dim1': 64,  # channels
        'dim2': 8,  # depth
        'dim3': 16,  # height
        'dim4': 16,  # width
    }
    result = fu.get_tensor('in_layout', tensor_dict)

    assert result['in_layout'] == 'NCDHW'
    assert result['in_channels'] == 64
    assert result['in_d'] == 8
    assert result['in_h'] == 16
    assert result['in_w'] == 16

  def test_get_tensor_ndhwc_3d(self):
    """Test 3D tensor with NDHWC layout"""
    tensor_dict = {
        'layout': 'NDHWC',
        'dim0': 1,
        'dim1': 8,  # depth
        'dim2': 16,  # height
        'dim3': 16,  # width
        'dim4': 64,  # channels
    }
    result = fu.get_tensor('in_layout', tensor_dict)

    assert result['in_layout'] == 'NDHWC'
    assert result['in_d'] == 8
    assert result['in_h'] == 16
    assert result['in_w'] == 16
    assert result['in_channels'] == 64
