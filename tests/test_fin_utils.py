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
import tuna.miopen.fin_utils as fu
from tuna.miopen.miopen_tables import ConvolutionConfig, ConvolutionJob, TensorTable
from multiprocessing import Value, Lock, Queue
from tuna.metadata import LOG_TIMEOUT
from tuna.tables import DBTables, ConfigType
from tuna.session import Session


def test_fin_utils():

  my_job = ConvolutionJob()
  my_job.id = 1
  my_job.valid = 1
  my_job.config = 1
  dbt = DBTables(session=1, config_type=ConfigType.convolution)
  dbt.session = Session()
  dbt.session.id = 1
  dbt.session.arch = 'gfx908'
  dbt.session.num_cu = 120

  # Test config with layout NCHW
  conv_config = ConvolutionConfig()
  conv_config.id = 65637
  conv_config.batchsize = 128
  conv_config.spatial_dim = 2
  conv_config.pad_h = 0
  conv_config.pad_w = 3
  conv_config.pad_d = 0
  conv_config.conv_stride_h = 1
  conv_config.conv_stride_w = 1
  conv_config.conv_stride_d = 1
  conv_config.dilation_h = 1
  conv_config.dilation_w = 1
  conv_config.dilation_d = 1
  conv_config.group_count = 1
  conv_config.mode = 'conv'
  conv_config.pad_mode = 'default'
  conv_config.trans_output_pad_h = 0
  conv_config.trans_output_pad_w = 0
  conv_config.trans_output_pad_d = 0
  conv_config.input_tensor = 6888
  conv_config.weight_tensor = 4716
  conv_config.out_layout = 'NCHW'
  conv_config.valid = 1
  conv_config.input_t = TensorTable()
  conv_config.input_t.id = 6888
  conv_config.input_t.dim0 = 1
  conv_config.input_t.dim1 = 128
  conv_config.input_t.dim2 = 1
  conv_config.input_t.dim3 = 17
  conv_config.input_t.dim4 = 17
  conv_config.input_t.layout = 'NCHW'
  conv_config.input_t.num_dims = 2
  conv_config.input_t.data_type = 'FP32'
  conv_config.input_t.valid = 1
  conv_config.weight_t = TensorTable()
  conv_config.weight_t.id = 4716
  conv_config.weight_t.dim0 = 128
  conv_config.weight_t.dim1 = 128
  conv_config.weight_t.dim2 = 1
  conv_config.weight_t.dim3 = 1
  conv_config.weight_t.dim4 = 7
  conv_config.weight_t.layout = 'NCHW'
  conv_config.weight_t.num_dims = 2
  conv_config.weight_t.data_type = 'FP32'
  conv_config.weight_t.valid = 1
  conv_config.direction = 'F'

  in_dict = fu.get_tensor('in_layout', conv_config.input_t.to_dict())
  assert (in_dict == {
      'in_layout': 'NCHW',
      'in_channels': 128,
      'in_d': 1,
      'in_h': 17,
      'in_w': 17
  })

  wei_dict = fu.get_tensor('wei_layout', conv_config.weight_t.to_dict())
  assert (wei_dict == {
      'wei_layout': 'NCHW',
      'out_channels': 128,
      'in_channels': 128,
      'fil_d': 1,
      'fil_h': 1,
      'fil_w': 7
  })

  return_config = fu.compose_config_obj(conv_config)
  assert (return_config == {
      'id': 65637,
      'batchsize': 128,
      'spatial_dim': 2,
      'pad_h': 0,
      'pad_w': 3,
      'pad_d': 0,
      'conv_stride_h': 1,
      'conv_stride_w': 1,
      'conv_stride_d': 1,
      'dilation_h': 1,
      'dilation_w': 1,
      'dilation_d': 1,
      'group_count': 1,
      'mode': 'conv',
      'pad_mode': 'default',
      'trans_output_pad_h': 0,
      'trans_output_pad_w': 0,
      'trans_output_pad_d': 0,
      'out_layout': 'NCHW',
      'in_layout': 'NCHW',
      'in_channels': 128,
      'in_d': 1,
      'in_h': 17,
      'in_w': 17,
      'wei_layout': 'NCHW',
      'out_channels': 128,
      'fil_d': 1,
      'fil_h': 1,
      'fil_w': 7,
      'cmd': 'conv',
      'direction': 'F',
      'valid': 1
  })

  dict = fu.fin_job("fin_find_compile", True, my_job, conv_config, dbt)
  assert (dict['steps'] == 'fin_find_compile')
  assert (dict['arch'] == 'gfx908:sram-ecc+:xnack-')
  assert (dict['num_cu'] == 120)
  assert (dict['config_tuna_id'] == 65637)
  assert (dict['direction'] == 1)
  assert (dict['dynamic_only'] == True)
  assert (dict['config'] == {
      'id': 65637,
      'batchsize': 128,
      'spatial_dim': 2,
      'pad_h': 0,
      'pad_w': 3,
      'pad_d': 0,
      'conv_stride_h': 1,
      'conv_stride_w': 1,
      'conv_stride_d': 1,
      'dilation_h': 1,
      'dilation_w': 1,
      'dilation_d': 1,
      'group_count': 1,
      'mode': 'conv',
      'pad_mode': 'default',
      'trans_output_pad_h': 0,
      'trans_output_pad_w': 0,
      'trans_output_pad_d': 0,
      'out_layout': 'NCHW',
      'in_layout': 'NCHW',
      'in_channels': 128,
      'in_d': 1,
      'in_h': 17,
      'in_w': 17,
      'wei_layout': 'NCHW',
      'out_channels': 128,
      'fil_d': 1,
      'fil_h': 1,
      'fil_w': 7,
      'cmd': 'conv',
      'direction': 'F',
      'valid': 1
  })

  #Test config with layout NHWC
  conv_config = ConvolutionConfig()
  conv_config.id = 65
  conv_config.batchsize = 64
  conv_config.spatial_dim = 2
  conv_config.pad_h = 0
  conv_config.pad_w = 3
  conv_config.pad_d = 0
  conv_config.conv_stride_h = 1
  conv_config.conv_stride_w = 1
  conv_config.conv_stride_d = 1
  conv_config.dilation_h = 1
  conv_config.dilation_w = 1
  conv_config.dilation_d = 1
  conv_config.group_count = 1
  conv_config.mode = 'conv'
  conv_config.pad_mode = 'default'
  conv_config.trans_output_pad_h = 0
  conv_config.trans_output_pad_w = 0
  conv_config.trans_output_pad_d = 0
  conv_config.input_tensor = 68
  conv_config.weight_tensor = 47
  conv_config.out_layout = 'NHWC'
  conv_config.valid = 1
  conv_config.input_t = TensorTable()
  conv_config.input_t.id = 68
  conv_config.input_t.dim0 = 1
  conv_config.input_t.dim1 = 64
  conv_config.input_t.dim2 = 1
  conv_config.input_t.dim3 = 9
  conv_config.input_t.dim4 = 21
  conv_config.input_t.layout = 'NHWC'
  conv_config.input_t.num_dims = 2
  conv_config.input_t.data_type = 'FP32'
  conv_config.input_t.valid = 1
  conv_config.weight_t = TensorTable()
  conv_config.weight_t.id = 47
  conv_config.weight_t.dim0 = 64
  conv_config.weight_t.dim1 = 64
  conv_config.weight_t.dim2 = 1
  conv_config.weight_t.dim3 = 13
  conv_config.weight_t.dim4 = 9
  conv_config.weight_t.layout = 'NHWC'
  conv_config.weight_t.num_dims = 2
  conv_config.weight_t.data_type = 'FP32'
  conv_config.weight_t.valid = 1
  conv_config.direction = 'F'

  in_dict = fu.get_tensor('in_layout', conv_config.input_t.to_dict())
  assert (in_dict == {
      'in_layout': 'NHWC',
      'in_d': 64,
      'in_h': 1,
      'in_w': 9,
      'in_channels': 21
  })

  wei_dict = fu.get_tensor('wei_layout', conv_config.weight_t.to_dict())
  assert (wei_dict == {
      'wei_layout': 'NHWC',
      'out_channels': 64,
      'in_channels': 64,
      'fil_d': 1,
      'fil_h': 13,
      'fil_w': 9
  })

  return_config = fu.compose_config_obj(conv_config)
  assert (return_config == {
      'id': 65,
      'batchsize': 64,
      'spatial_dim': 2,
      'pad_h': 0,
      'pad_w': 3,
      'pad_d': 0,
      'conv_stride_h': 1,
      'conv_stride_w': 1,
      'conv_stride_d': 1,
      'dilation_h': 1,
      'dilation_w': 1,
      'dilation_d': 1,
      'group_count': 1,
      'mode': 'conv',
      'pad_mode': 'default',
      'trans_output_pad_h': 0,
      'trans_output_pad_w': 0,
      'trans_output_pad_d': 0,
      'out_layout': 'NHWC',
      'in_layout': 'NHWC',
      'in_d': 64,
      'in_h': 1,
      'in_w': 9,
      'in_channels': 64,
      'wei_layout': 'NHWC',
      'out_channels': 64,
      'fil_d': 1,
      'fil_h': 13,
      'fil_w': 9,
      'cmd': 'conv',
      'direction': 'F',
      'valid': 1
  })

  dict = fu.fin_job("fin_find_compile", True, my_job, conv_config, dbt)
  assert (dict['steps'] == 'fin_find_compile')
  assert (dict['arch'] == 'gfx908:sram-ecc+:xnack-')
  assert (dict['num_cu'] == 120)
  assert (dict['config_tuna_id'] == 65)
  assert (dict['direction'] == 1)
  assert (dict['dynamic_only'] == True)
  assert (dict['config'] == {
      'id': 65,
      'batchsize': 64,
      'spatial_dim': 2,
      'pad_h': 0,
      'pad_w': 3,
      'pad_d': 0,
      'conv_stride_h': 1,
      'conv_stride_w': 1,
      'conv_stride_d': 1,
      'dilation_h': 1,
      'dilation_w': 1,
      'dilation_d': 1,
      'group_count': 1,
      'mode': 'conv',
      'pad_mode': 'default',
      'trans_output_pad_h': 0,
      'trans_output_pad_w': 0,
      'trans_output_pad_d': 0,
      'out_layout': 'NHWC',
      'in_layout': 'NHWC',
      'in_d': 64,
      'in_h': 1,
      'in_w': 9,
      'in_channels': 64,
      'wei_layout': 'NHWC',
      'out_channels': 64,
      'fil_d': 1,
      'fil_h': 13,
      'fil_w': 9,
      'cmd': 'conv',
      'direction': 'F',
      'valid': 1
  })
