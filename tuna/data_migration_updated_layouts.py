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
""" Module for moving data out of config table to new tensor tables"""
import argparse
from sqlalchemy.exc import OperationalError
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError  #pylint: disable=wrong-import-order

from tuna.utils.logger import setup_logger
from tuna.db_tables import create_tables
from tuna.miopen_tables import get_miopen_tables
from tuna.utils.utility import get_env_vars

LOGGER = setup_logger('nonstandard_layouts')
ENV_VARS = get_env_vars()
ENGINE = create_engine("mysql+pymysql://{}:{}@{}:3306/{}".format(
    ENV_VARS['user_name'], ENV_VARS['user_password'], ENV_VARS['db_hostname'],
    ENV_VARS['db_name']))


def parse_args():
  """Parsing arguments"""
  parser = argparse.ArgumentParser(description='Optional args')
  parser.add_argument('--recreate_tables',
                      dest='recreate_tables',
                      action="store_true",
                      help='Indicate whether you want to drop and add tables')

  args = parser.parse_args()
  return args


def drop_tables():
  """Drop table to recreate later"""

  tables = [
      'conv_solver_applicability', 'solver_fusion_applicability',
      'solver_bn_applicability', 'conv_config_tags', 'fusion_config_tags',
      'bn_config_tags', 'conv_job', 'fusion_job', 'bn_job', 'conv_config',
      'fusion_config', 'bn_config', 'tensor'
  ]
  with ENGINE.connect() as conn:
    for table in tables:
      try:
        conn.execute("drop table {}".format(table))
      except OperationalError as oerr:
        LOGGER.info('%s \n', oerr)
        continue


def insert_weight_tensor():
  """Copying data out of config into tensor as weight tensor"""

  LOGGER.info('Inserting weight_tensor...')

  query_1 = """insert ignore into tensor(dim0, dim1, dim2, dim3, dim4, data_type)
      select out_channels, in_channels, fil_d, fil_h, fil_w, "FP32"
      from config where cmd="conv";"""
  query_2 = """insert ignore into tensor(dim0, dim1, dim2, dim3, dim4, data_type)
      select out_channels, in_channels, fil_d, fil_h, fil_w, "FP16" from config
      where cmd="convfp16";"""
  query_3 = """insert ignore into tensor(dim0, dim1, dim2, dim3, dim4, data_type)
      select out_channels, in_channels, fil_d, fil_h, fil_w, "BFP16" from config
      where cmd="convbfp16";"""
  query_4 = """insert ignore into tensor(dim0, dim1, dim2, dim3, dim4, data_type)
      select out_channels, in_channels, fil_d, fil_h, fil_w, "FP16" from config
      where cmd="CBAInferfp16";"""

  queries = []
  queries.append(query_1)
  queries.append(query_2)
  queries.append(query_3)
  queries.append(query_4)

  with ENGINE.connect() as conn:
    for elem in queries:
      try:
        conn.execute(elem)
      except OperationalError as oerr:
        LOGGER.info('%s \n', oerr)
        return False
      except IntegrityError as err:
        LOGGER.info('%s', err)
        continue

  return True


def insert_input_tensor():
  """Copying data out of config into tensor as input tensor"""

  LOGGER.info('Inserting input_tensor...')

  query_1 = """insert ignore into tensor(dim0, dim1, dim2, dim3, dim4, data_type)
       select 1, in_channels, in_d, in_h, in_w, "FP32" from config where cmd="conv";"""
  query_2 = """insert ignore into tensor(dim0, dim1, dim2, dim3, dim4, data_type)
       select 1, in_channels, in_d, in_h, in_w, "FP16" from config where cmd="convfp16";"""
  query_3 = """insert ignore into tensor(dim0, dim1, dim2, dim3, dim4, data_type)
       select 1, in_channels, in_d, in_h, in_w, "BFP16" from config where cmd="convbfp16";"""
  query_4 = """insert ignore into tensor(dim0, dim1, dim2, dim3, dim4, data_type)
       select 1, in_channels, in_d, in_h, in_w, "FP16" from config where cmd="CBAInferfp16";"""

  queries = []
  queries.append(query_1)
  queries.append(query_2)
  queries.append(query_3)
  queries.append(query_4)

  with ENGINE.connect() as conn:
    for elem in queries:
      try:
        conn.execute(elem)
      except OperationalError as oerr:
        LOGGER.info('%s \n', oerr)
        return False
      except IntegrityError as err:
        LOGGER.info('%s', err)
        continue

  return True


def create_conv_config_table():
  """Moving data from config to conv_config and relating FKeys to tensor table"""

  query_1 = """insert ignore into conv_config(batchsize, spatial_dim, pad_h, pad_w, pad_d,
  conv_stride_h, conv_stride_w, conv_stride_d,
  dilation_h, dilation_w, dilation_d,
  trans_output_pad_h, trans_output_pad_w, trans_output_pad_d,
  group_count, conv_mode, pad_mode,
  input_tensor, weight_tensor)
  select config.batchsize, config.spatial_dim, config.pad_h, config.pad_w, config.pad_d,
  config.conv_stride_h, config.conv_stride_w, config.conv_stride_d,
  config.dilation_h, config.dilation_w, config.dilation_d,
  0, 0, 0,
  config.group_count, config.conv_mode, config.pad_mode,
  (select tensor.id from tensor where dim0=1 and dim1=config.in_channels and
    dim2=config.in_d and dim3=config.in_h and dim4=config.in_w and data_type="FP32"),
  (select tensor.id from tensor where dim0=config.out_channels and dim1=config.in_channels and
    dim2=config.fil_d and dim3=config.fil_h and dim4=config.fil_w and data_type="FP32")
  from config where cmd="conv";"""

  query_2 = """insert ignore into conv_config(batchsize, spatial_dim, pad_h, pad_w, pad_d,
  conv_stride_h, conv_stride_w, conv_stride_d,
  dilation_h, dilation_w, dilation_d,
  trans_output_pad_h, trans_output_pad_w, trans_output_pad_d,
  group_count, conv_mode, pad_mode,
  input_tensor, weight_tensor)
  select config.batchsize, config.spatial_dim, config.pad_h, config.pad_w, config.pad_d,
  config.conv_stride_h, config.conv_stride_w, config.conv_stride_d,
  config.dilation_h, config.dilation_w, config.dilation_d,
  0, 0, 0,
  config.group_count, config.conv_mode, config.pad_mode,
  (select tensor.id from tensor where dim0=1 and dim1=config.in_channels and
    dim2=config.in_d and dim3=config.in_h and dim4=config.in_w and data_type="FP16"),
  (select tensor.id from tensor where dim0=config.out_channels and dim1=config.in_channels and
    dim2=config.fil_d and dim3=config.fil_h and dim4=config.fil_w and data_type="FP16")
  from config where cmd="convfp16";"""

  query_3 = """insert into conv_config(batchsize, spatial_dim, pad_h, pad_w, pad_d,
  conv_stride_h, conv_stride_w, conv_stride_d,
  dilation_h, dilation_w, dilation_d,
  trans_output_pad_h, trans_output_pad_w, trans_output_pad_d,
  group_count, conv_mode, pad_mode,
  input_tensor, weight_tensor)
  select config.batchsize, config.spatial_dim, config.pad_h, config.pad_w, config.pad_d,
  config.conv_stride_h, config.conv_stride_w, config.conv_stride_d,
  config.dilation_h, config.dilation_w, config.dilation_d,
  0, 0, 0,
  config.group_count, config.conv_mode, config.pad_mode,
  (select tensor.id from tensor where dim0=1 and dim1=config.in_channels and
    dim2=config.in_d and dim3=config.in_h and dim4=config.in_w and data_type="BFP16"),
  (select tensor.id from tensor where dim0=config.out_channels and dim1=config.in_channels and
    dim2=config.fil_d and dim3=config.fil_h and dim4=config.fil_w and data_type="BFP16")
  from config where cmd="convbfp16";"""

  queries = []
  queries.append(query_1)
  queries.append(query_2)
  queries.append(query_3)

  with ENGINE.connect() as conn:
    for elem in queries:
      try:
        conn.execute(elem)
      except OperationalError as oerr:
        LOGGER.info('%s \n', oerr)
        return False
      except IntegrityError:
        continue

  return True


def main():
  """Main script function"""
  args = parse_args()
  if args.recreate_tables:
    LOGGER.info('Recreating DB tables')
    drop_tables()
    create_tables(get_miopen_tables())

  insert_weight_tensor()
  LOGGER.info('Done inserting weight_tensor')

  insert_input_tensor()
  LOGGER.info('Done inserting input_tensor')

  create_conv_config_table()


if __name__ == '__main__':
  main()
