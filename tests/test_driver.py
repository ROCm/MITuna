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
from tuna.utils.logger import setup_logger
from tuna.miopen.driver.convolution import DriverConvolution
from tuna.miopen.driver.batchnorm import DriverBatchNorm
from tuna.miopen.subcmd.import_configs import insert_config
from tuna.miopen.db.convolutionjob_tables import ConvolutionConfig
from tuna.miopen.db.batch_norm_tables import BNConfig
from tuna.dbBase.sql_alchemy import DbSession
from tuna.miopen.db.tables import MIOpenDBTables
from tuna.miopen.utils.config_type import ConfigType
from utils import CfgImportArgs


def test_driver():
  args = CfgImportArgs()
  logger = setup_logger('test_driver')
  dbt = MIOpenDBTables(session_id=None, config_type=args.config_type)
  counts = {}
  counts['cnt_configs'] = 0
  counts['cnt_tagged_configs'] = set()
  conv_driver(args, logger, dbt, counts)
  bn_driver(args, logger, counts)


def conv_driver(args, logger, dbt, counts):
  cmd0 = "./bin/MIOpenDriver conv --pad_h 1 --pad_w 1 --out_channels 128 --fil_w 3 --fil_h 3 --dilation_w 1 --dilation_h 1 --conv_stride_w 1 --conv_stride_h 1 --in_channels 128 --in_w 28 --in_h 28 --in_h 28 --batchsize 256 --group_count 1 --in_d 1 --fil_d 1 --in_layout NHWC --fil_layout NHWC --out_layout NHWC -V 0"
  try:
    _ = DriverConvolution(cmd0)
    assert False
  except ValueError as err:
    assert "needs direction" in str(err)

  cmd1 = "./bin/MIOpenDriver conv --pad_h 1 --pad_w 1 --out_channels 128 --fil_w 3 --fil_h 3 --dilation_w 1 --dilation_h 1 --conv_stride_w 1 --conv_stride_h 1 --in_channels 128 --in_w 28 --in_h 28 --in_h 28 --batchsize 256 --group_count 1 --in_d 1 --fil_d 1 --forw 1 --out_layout NHWC -V 0"
  driver1 = DriverConvolution(cmd1)
  d1_str = driver1.to_dict()
  assert d1_str["fil_h"] == 3
  assert d1_str["fil_layout"] == 'NHWC'
  assert d1_str["in_layout"] == 'NHWC'
  assert d1_str["out_layout"] == 'NHWC'
  assert d1_str["in_channels"] == 128
  assert d1_str["out_channels"] == 128
  assert d1_str["spatial_dim"] == 2
  assert d1_str["direction"] == 'F'
  assert d1_str["cmd"] == 'conv'
  itensor1 = driver1.get_input_t_id()
  assert itensor1
  wtensor1 = driver1.get_weight_t_id()
  assert wtensor1
  c_dict1 = driver1.compose_tensors(keep_id=True)
  assert c_dict1["input_tensor"]
  assert c_dict1["weight_tensor"]

  cmd1_id = insert_config(driver1, counts, dbt, args, logger)
  with DbSession() as session:
    row1 = session.query(ConvolutionConfig).filter(
        ConvolutionConfig.id == cmd1_id).one()
    driver_1_row = DriverConvolution(db_obj=row1)
    #compare DriverConvolution for same driver cmd built from Driver-line, vs built from that Driver-line's DB row
    assert driver1 == driver_1_row

  c_dict1 = driver1.compose_tensors(keep_id=True)
  assert c_dict1['id'] is not None
  assert c_dict1["input_tensor"]
  assert c_dict1["weight_tensor"]

  cmd2 = "./bin/MIOpenDriver convfp16 -n 128 -c 256 -H 56 -W 56 -k 64 -y 1 -x 1 -p 0 -q 0 -u 1 -v 1 -l 1 -j 1 -m conv -g 1 -F 2 -t 1 --fil_layout NCHW --in_layout NCHW --out_layout NCHW"
  driver2 = DriverConvolution(cmd2)
  d2_str = driver2.to_dict()
  assert d2_str
  assert d2_str["cmd"] == 'convfp16'
  assert d2_str["direction"] == 'B'
  assert d2_str["in_h"] == 56
  assert d2_str["fil_layout"] == 'NCHW'
  assert d2_str["dilation_d"] == 0
  assert d2_str["conv_stride_d"] == 0
  assert d2_str["fil_w"] == 1
  assert d2_str["out_channels"] == 64
  assert driver2.get_input_t_id()
  assert driver2.get_weight_t_id()
  c_dict2 = driver2.compose_tensors(keep_id=True)
  assert c_dict2["input_tensor"]
  assert c_dict2["weight_tensor"]
  assert c_dict2

  cmd2_id = insert_config(driver2, counts, dbt, args, logger)
  with DbSession() as session:
    row2 = session.query(ConvolutionConfig).filter(
        ConvolutionConfig.id == cmd2_id).one()
    driver_2_row = DriverConvolution(db_obj=row2)
    #compare DriverConvolution for same driver cmd built from Driver-line, vs built from that Driver-line's DB row
    assert driver2 == driver_2_row

  fdb1 = "64-75-75-3x3-64-75-75-512-1x1-1x1-1x1-0-NHWC-FP16-W="
  driver4 = DriverConvolution(fdb1)
  d4_str = str(driver4)
  d4_dict = driver4.to_dict()
  assert d4_dict["in_layout"] == "NHWC"
  assert d4_dict["out_layout"] == "NHWC"
  assert d4_dict["fil_layout"] == "NHWC"
  driver5 = DriverConvolution(d4_str)
  assert driver4 == driver5
  d5_dict = driver5.to_dict()
  assert d5_dict["in_layout"] == "NHWC"
  assert d5_dict["out_layout"] == "NHWC"
  assert d5_dict["fil_layout"] == "NHWC"


def bn_driver(args, logger, counts):
  cmd3 = "./bin/MIOpenDriver bnormfp16 -n 256 -c 64 -H 56 -W 56 -m 1 --forw 1 -b 0 -s 1 -r 1"
  args.config_type = ConfigType.batch_norm
  dbt2 = MIOpenDBTables(session_id=None, config_type=args.config_type)
  driver3 = DriverBatchNorm(cmd3)
  d3_str = driver3.to_dict()
  assert d3_str
  assert d3_str["forw"] == 1
  assert d3_str["back"] == 0
  assert d3_str["cmd"] == 'bnormfp16'
  assert d3_str["mode"] == 1
  assert d3_str["run"] == 1
  assert d3_str["in_channels"] == 64
  assert d3_str["alpha"] == 1
  assert d3_str["beta"] == 0
  assert d3_str["direction"] == 'F'
  assert driver3.get_input_t_id()
  c_dict3 = driver3.compose_tensors(keep_id=True)
  assert c_dict3["input_tensor"]
  assert c_dict3

  cmd3_id = insert_config(driver3, counts, dbt2, args, logger)
  with DbSession() as session:
    row3 = session.query(BNConfig).filter(BNConfig.id == cmd3_id).one()
    driver_3_row = DriverBatchNorm(db_obj=row3)
    #compare DriverBN for same driver cmd built from Driver-line, vs built from that Driver-line's DB row
    assert driver3 == driver_3_row
