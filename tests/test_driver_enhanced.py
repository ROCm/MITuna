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
"""Enhanced comprehensive tests for MIOpen driver modules"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from tuna.miopen.driver.convolution import DriverConvolution
from tuna.miopen.driver.batchnorm import DriverBatchNorm
from tuna.miopen.driver.base import MIOpenDriver
from tuna.miopen.db.convolutionjob_tables import ConvolutionConfig
from tuna.miopen.db.batch_norm_tables import BNConfig
from tuna.miopen.db.tensortable import TensorTable


@pytest.mark.unit
@pytest.mark.driver
class TestDriverConvolutionInit:
  """Test DriverConvolution initialization"""

  def test_default_initialization(self):
    """Test default initialization without arguments"""
    driver = DriverConvolution()
    assert driver.batchsize == 32
    assert driver.spatial_dim == 2
    assert driver.mode == 'conv'
    assert driver.group_count == 1
    assert driver.direction == 'F'

  def test_initialization_with_kwargs(self):
    """Test initialization with keyword arguments"""
    driver = DriverConvolution(kwargs={'batchsize': 64, 'in_h': 224})
    assert driver.batchsize == 64
    assert driver.in_h == 224

  def test_initialization_with_driver_line(self):
    """Test initialization from MIOpenDriver command line"""
    cmd = "./bin/MIOpenDriver conv -n 128 -c 3 -H 224 -W 224 -k 64 -y 7 -x 7 -p 3 -q 3 -u 2 -v 2 -l 1 -j 1 -m conv -g 1 -F 1"
    driver = DriverConvolution(cmd)
    assert driver.batchsize == 128
    assert driver.in_channels == 3
    assert driver.in_h == 224
    assert driver.in_w == 224
    assert driver.out_channels == 64
    assert driver.fil_h == 7
    assert driver.fil_w == 7
    assert driver.direction == 'F'

  def test_initialization_with_fdb_key(self):
    """Test initialization from find database key string"""
    fdb_key = "64-75-75-3x3-64-75-75-512-1x1-1x1-1x1-0-NHWC-FP16-W="
    driver = DriverConvolution(fdb_key)
    assert driver.in_channels == 64
    assert driver.in_h == 75
    assert driver.in_w == 75


@pytest.mark.unit
@pytest.mark.driver
class TestDriverConvolutionLayouts:
  """Test DriverConvolution layout handling"""

  @pytest.mark.parametrize("layout", ["NCHW", "NHWC", "NCDHW", "NDHWC"])
  def test_valid_layouts(self, layout):
    """Test all supported layouts"""
    cmd = f"./bin/MIOpenDriver conv -n 1 -c 64 -H 56 -W 56 -k 64 -y 1 -x 1 -p 0 -q 0 -F 1 --in_layout {layout} --fil_layout {layout} --out_layout {layout}"
    driver = DriverConvolution(cmd)
    assert driver.in_layout == layout
    assert driver.fil_layout == layout
    assert driver.out_layout == layout

  def test_mismatched_layouts_raises_error(self):
    """Test that mismatched layouts raise ValueError"""
    cmd = "./bin/MIOpenDriver conv -n 1 -c 64 -H 56 -W 56 -k 64 -y 1 -x 1 -p 0 -q 0 -F 1 --in_layout NCHW --fil_layout NHWC --out_layout NCHW"
    with pytest.raises(ValueError, match="Layouts do not match"):
      DriverConvolution(cmd)

  def test_default_layout_nchw(self):
    """Test default layout is NCHW for 2D"""
    cmd = "./bin/MIOpenDriver conv -n 1 -c 64 -H 56 -W 56 -k 64 -y 1 -x 1 -p 0 -q 0 -F 1"
    driver = DriverConvolution(cmd)
    driver.config_set_defaults()
    assert driver.in_layout == 'NCHW'
    assert driver.fil_layout == 'NCHW'
    assert driver.out_layout == 'NCHW'


@pytest.mark.unit
@pytest.mark.driver
class TestDriverConvolutionDirection:
  """Test DriverConvolution direction handling"""

  @pytest.mark.parametrize("flag,expected", [
      ("-F 1", "F"),
      ("-F 2", "B"),
      ("-F 4", "W"),
      ("--forw 1", "F"),
      ("--back 1", "B"),
      ("--wrw 1", "W"),
  ])
  def test_direction_flags(self, flag, expected):
    """Test various direction flags"""
    cmd = f"./bin/MIOpenDriver conv -n 1 -c 3 -H 32 -W 32 -k 64 -y 3 -x 3 {flag}"
    driver = DriverConvolution(cmd)
    assert driver.direction == expected

  def test_missing_direction_raises_error(self):
    """Test that missing direction raises ValueError"""
    cmd = "./bin/MIOpenDriver conv -n 1 -c 3 -H 32 -W 32 -k 64 -y 3 -x 3"
    with pytest.raises(ValueError, match="needs direction"):
      DriverConvolution(cmd)


@pytest.mark.unit
@pytest.mark.driver
class TestDriverConvolutionCommands:
  """Test different MIOpenDriver command types"""

  @pytest.mark.parametrize("cmd_type,precision", [
      ("conv", "FP32"),
      ("convfp16", "FP16"),
      ("convint8", "INT8"),
      ("convbfp16", "BF16"),
  ])
  def test_command_types(self, cmd_type, precision):
    """Test different command types and precision"""
    cmd = f"./bin/MIOpenDriver {cmd_type} -n 1 -c 3 -H 32 -W 32 -k 64 -y 3 -x 3 -F 1"
    driver = DriverConvolution(cmd)
    assert driver.cmd == cmd_type


@pytest.mark.unit
@pytest.mark.driver
class TestDriverConvolutionTensors:
  """Test DriverConvolution tensor operations"""

  def test_get_input_tensor_id(self):
    """Test getting input tensor ID"""
    cmd = "./bin/MIOpenDriver conv -n 128 -c 64 -H 56 -W 56 -k 128 -y 3 -x 3 -p 1 -q 1 -F 1"
    driver = DriverConvolution(cmd)
    tensor_id = driver.get_input_t_id()
    assert tensor_id > 0

  def test_get_weight_tensor_id(self):
    """Test getting weight tensor ID"""
    cmd = "./bin/MIOpenDriver conv -n 128 -c 64 -H 56 -W 56 -k 128 -y 3 -x 3 -p 1 -q 1 -F 1"
    driver = DriverConvolution(cmd)
    tensor_id = driver.get_weight_t_id()
    assert tensor_id > 0

  def test_compose_tensors_with_id(self):
    """Test composing tensors with IDs"""
    cmd = "./bin/MIOpenDriver conv -n 1 -c 3 -H 224 -W 224 -k 64 -y 7 -x 7 -F 1"
    driver = DriverConvolution(cmd)
    tensors = driver.compose_tensors(keep_id=True)
    assert 'input_tensor' in tensors
    assert 'weight_tensor' in tensors
    assert tensors['input_tensor'] > 0
    assert tensors['weight_tensor'] > 0

  def test_compose_tensors_without_id(self):
    """Test composing tensors without IDs"""
    cmd = "./bin/MIOpenDriver conv -n 1 -c 3 -H 224 -W 224 -k 64 -y 7 -x 7 -F 1"
    driver = DriverConvolution(cmd)
    tensors = driver.compose_tensors(keep_id=False)
    assert 'input_tensor' not in tensors
    assert 'weight_tensor' not in tensors


@pytest.mark.unit
@pytest.mark.driver
class TestDriverConvolutionSerialization:
  """Test DriverConvolution serialization"""

  def test_to_dict(self):
    """Test conversion to dictionary"""
    cmd = "./bin/MIOpenDriver conv -n 64 -c 3 -H 32 -W 32 -k 64 -y 3 -x 3 -F 1"
    driver = DriverConvolution(cmd)
    d = driver.to_dict()
    assert d['batchsize'] == 64
    assert d['in_channels'] == 3
    assert d['in_h'] == 32
    assert d['out_channels'] == 64
    assert d['direction'] == 'F'
    assert d['cmd'] == 'conv'

  def test_to_string(self):
    """Test string representation"""
    cmd = "./bin/MIOpenDriver conv -n 1 -c 3 -H 32 -W 32 -k 64 -y 3 -x 3 -F 1"
    driver = DriverConvolution(cmd)
    str_repr = str(driver)
    assert 'MIOpenDriver' in str_repr
    assert 'conv' in str_repr

  def test_equality(self):
    """Test driver equality comparison"""
    cmd1 = "./bin/MIOpenDriver conv -n 64 -c 3 -H 32 -W 32 -k 64 -y 3 -x 3 -F 1"
    driver1 = DriverConvolution(cmd1)
    driver2 = DriverConvolution(cmd1)
    assert driver1 == driver2

  def test_inequality(self):
    """Test driver inequality comparison"""
    cmd1 = "./bin/MIOpenDriver conv -n 64 -c 3 -H 32 -W 32 -k 64 -y 3 -x 3 -F 1"
    cmd2 = "./bin/MIOpenDriver conv -n 128 -c 3 -H 32 -W 32 -k 64 -y 3 -x 3 -F 1"
    driver1 = DriverConvolution(cmd1)
    driver2 = DriverConvolution(cmd2)
    assert driver1 != driver2


@pytest.mark.unit
@pytest.mark.driver
class TestDriverConvolutionEdgeCases:
  """Test edge cases and error handling"""

  def test_3d_convolution(self):
    """Test 3D convolution support"""
    cmd = "./bin/MIOpenDriver conv -n 1 -c 3 -D 16 -H 32 -W 32 -k 64 -z 3 -y 3 -x 3 -F 1"
    driver = DriverConvolution(cmd)
    driver.config_set_defaults()
    assert driver.spatial_dim == 3
    assert driver.in_d == 16
    assert driver.fil_d == 3

  def test_grouped_convolution(self):
    """Test grouped convolution"""
    cmd = "./bin/MIOpenDriver conv -n 1 -c 64 -H 56 -W 56 -k 64 -y 3 -x 3 -g 4 -F 1"
    driver = DriverConvolution(cmd)
    assert driver.group_count == 4

  def test_dilated_convolution(self):
    """Test dilated convolution"""
    cmd = "./bin/MIOpenDriver conv -n 1 -c 64 -H 56 -W 56 -k 64 -y 3 -x 3 -l 2 -j 2 -F 1"
    driver = DriverConvolution(cmd)
    assert driver.dilation_h == 2
    assert driver.dilation_w == 2

  def test_strided_convolution(self):
    """Test strided convolution"""
    cmd = "./bin/MIOpenDriver conv -n 1 -c 64 -H 224 -W 224 -k 64 -y 7 -x 7 -u 2 -v 2 -F 1"
    driver = DriverConvolution(cmd)
    assert driver.conv_stride_h == 2
    assert driver.conv_stride_w == 2


@pytest.mark.unit
@pytest.mark.driver
class TestDriverBatchNormInit:
  """Test DriverBatchNorm initialization"""

  def test_default_initialization(self):
    """Test default initialization"""
    driver = DriverBatchNorm()
    assert hasattr(driver, 'batchsize')
    assert hasattr(driver, 'mode')

  def test_initialization_with_driver_line(self):
    """Test initialization from command line"""
    cmd = "./bin/MIOpenDriver bnorm -n 256 -c 64 -H 56 -W 56 -m 1 --forw 1"
    driver = DriverBatchNorm(cmd)
    assert driver.batchsize == 256
    assert driver.in_channels == 64
    assert driver.in_h == 56
    assert driver.in_w == 56
    assert driver.mode == 1
    assert driver.direction == 'F'

  def test_fp16_batch_norm(self):
    """Test FP16 batch normalization"""
    cmd = "./bin/MIOpenDriver bnormfp16 -n 128 -c 64 -H 28 -W 28 -m 1 --forw 1"
    driver = DriverBatchNorm(cmd)
    assert driver.cmd == 'bnormfp16'


@pytest.mark.unit
@pytest.mark.driver
class TestDriverBatchNormDirection:
  """Test DriverBatchNorm direction handling"""

  def test_forward_direction(self):
    """Test forward direction"""
    cmd = "./bin/MIOpenDriver bnorm -n 64 -c 128 -H 28 -W 28 -m 1 --forw 1"
    driver = DriverBatchNorm(cmd)
    assert driver.forw == 1
    assert driver.direction == 'F'

  def test_backward_direction(self):
    """Test backward direction"""
    cmd = "./bin/MIOpenDriver bnorm -n 64 -c 128 -H 28 -W 28 -m 1 --back 1"
    driver = DriverBatchNorm(cmd)
    assert driver.back == 1
    assert driver.direction == 'B'


@pytest.mark.unit
@pytest.mark.driver
class TestDriverBatchNormMode:
  """Test DriverBatchNorm mode handling"""

  @pytest.mark.parametrize("mode", [0, 1, 2, 3, 4])
  def test_valid_modes(self, mode):
    """Test all valid batch norm modes"""
    cmd = f"./bin/MIOpenDriver bnorm -n 64 -c 128 -H 28 -W 28 -m {mode} --forw 1"
    driver = DriverBatchNorm(cmd)
    assert driver.mode == mode


@pytest.mark.unit
@pytest.mark.driver
class TestDriverBatchNormTensors:
  """Test DriverBatchNorm tensor operations"""

  def test_get_input_tensor_id(self):
    """Test getting input tensor ID"""
    cmd = "./bin/MIOpenDriver bnorm -n 256 -c 64 -H 56 -W 56 -m 1 --forw 1"
    driver = DriverBatchNorm(cmd)
    tensor_id = driver.get_input_t_id()
    assert tensor_id > 0

  def test_compose_tensors(self):
    """Test composing tensors"""
    cmd = "./bin/MIOpenDriver bnorm -n 128 -c 64 -H 56 -W 56 -m 1 --forw 1"
    driver = DriverBatchNorm(cmd)
    tensors = driver.compose_tensors(keep_id=True)
    assert 'input_tensor' in tensors
    assert tensors['input_tensor'] > 0


@pytest.mark.unit
@pytest.mark.driver
class TestDriverBatchNormSerialization:
  """Test DriverBatchNorm serialization"""

  def test_to_dict(self):
    """Test conversion to dictionary"""
    cmd = "./bin/MIOpenDriver bnorm -n 64 -c 128 -H 28 -W 28 -m 1 --forw 1 -b 0 -s 1 -r 1"
    driver = DriverBatchNorm(cmd)
    d = driver.to_dict()
    assert d['batchsize'] == 64
    assert d['in_channels'] == 128
    assert d['in_h'] == 28
    assert d['mode'] == 1
    assert d['forw'] == 1
    assert d['back'] == 0
    assert d['save'] == 1
    assert d['run'] == 1

  def test_equality(self):
    """Test driver equality"""
    cmd = "./bin/MIOpenDriver bnorm -n 64 -c 128 -H 28 -W 28 -m 1 --forw 1"
    driver1 = DriverBatchNorm(cmd)
    driver2 = DriverBatchNorm(cmd)
    assert driver1 == driver2


@pytest.mark.unit
@pytest.mark.driver
class TestDriverBatchNormAlphaBeta:
  """Test DriverBatchNorm alpha/beta parameters"""

  def test_alpha_parameter(self):
    """Test alpha parameter"""
    cmd = "./bin/MIOpenDriver bnorm -n 64 -c 128 -H 28 -W 28 -m 1 --forw 1 -a 2.0"
    driver = DriverBatchNorm(cmd)
    assert driver.alpha == 2.0

  def test_beta_parameter(self):
    """Test beta parameter"""
    cmd = "./bin/MIOpenDriver bnorm -n 64 -c 128 -H 28 -W 28 -m 1 --forw 1 -b 1.5"
    driver = DriverBatchNorm(cmd)
    assert driver.beta == 1.5


@pytest.mark.unit
@pytest.mark.driver
@pytest.mark.db
class TestDriverDatabaseRoundTrip:
  """Test driver database round-trip conversion"""

  def test_convolution_driver_from_db_row(self, db_session):
    """Test creating DriverConvolution from database row"""
    # Create a mock ConvolutionConfig row
    config = ConvolutionConfig()
    config.id = 1
    config.batchsize = 128
    config.spatial_dim = 2
    config.pad_h = 1
    config.pad_w = 1
    config.conv_stride_h = 1
    config.conv_stride_w = 1
    config.dilation_h = 1
    config.dilation_w = 1
    config.group_count = 1
    config.mode = 'conv'
    config.pad_mode = 'default'
    config.trans_output_pad_h = 0
    config.trans_output_pad_w = 0
    config.out_layout = 'NCHW'
    config.direction = 'F'
    config.valid = 1

    # Create mock tensor
    input_tensor = TensorTable()
    input_tensor.id = 1
    input_tensor.dim0 = 1
    input_tensor.dim1 = 64
    input_tensor.dim2 = 1
    input_tensor.dim3 = 56
    input_tensor.dim4 = 56
    input_tensor.layout = 'NCHW'
    input_tensor.num_dims = 2
    input_tensor.data_type = 'FP32'
    input_tensor.valid = 1

    weight_tensor = TensorTable()
    weight_tensor.id = 2
    weight_tensor.dim0 = 128
    weight_tensor.dim1 = 64
    weight_tensor.dim2 = 1
    weight_tensor.dim3 = 3
    weight_tensor.dim4 = 3
    weight_tensor.layout = 'NCHW'
    weight_tensor.num_dims = 2
    weight_tensor.data_type = 'FP32'
    weight_tensor.valid = 1

    config.input_t = input_tensor
    config.weight_t = weight_tensor

    # Create driver from db_obj
    driver = DriverConvolution(db_obj=config)
    assert driver.batchsize == 128
    assert driver.direction == 'F'
    assert driver.in_layout == 'NCHW'

  def test_batch_norm_driver_from_db_row(self, db_session):
    """Test creating DriverBatchNorm from database row"""
    # Create a mock BNConfig row
    config = BNConfig()
    config.id = 1
    config.batchsize = 256
    config.mode = 1
    config.forw = 1
    config.back = 0
    config.run = 1
    config.save = 1
    config.alpha = 1
    config.beta = 0
    config.direction = 'F'
    config.valid = 1

    # Create mock tensor
    input_tensor = TensorTable()
    input_tensor.id = 1
    input_tensor.dim0 = 1
    input_tensor.dim1 = 64
    input_tensor.dim2 = 1
    input_tensor.dim3 = 56
    input_tensor.dim4 = 56
    input_tensor.layout = 'NCHW'
    input_tensor.num_dims = 2
    input_tensor.data_type = 'FP32'
    input_tensor.valid = 1

    config.input_t = input_tensor

    # Create driver from db_obj
    driver = DriverBatchNorm(db_obj=config)
    assert driver.batchsize == 256
    assert driver.mode == 1
    assert driver.direction == 'F'
