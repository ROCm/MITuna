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
""" Module for tagging and importing configs """
import os
import logging
import argparse
import itertools

from sqlalchemy.exc import IntegrityError
from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.db_utility import connect_db
from tuna.utils.logger import setup_logger
from tuna.rocmlir.rocmlir_tables import RocMLIRDBTables

## Adapted from perfRunner.getConvConfigurations.

#DIRECTIONS = ['-F 1', '-F 2', '-F 4']
# temporarily disable backward-data until rocmlir-tuning-driver can handle multi-kernel code
DIRECTIONS = ['-F 1', '-F 4']
DATA_TYPES = ['-t f32', '-t f16', '-t i8']
LAYOUTS = ['NHWC', 'NCHW']


def get_conv_configurations(filename):
  """Read conv-configs from filename and expand into all combinations of
     direction, type, and layout.
  """
  configs = []
  with open(filename, 'r', encoding='utf8') as config_file:
    lines = config_file.readlines()

    # All combinations of conv direction, type and layouts
    for direction, datatype, layout, line in \
            itertools.product(DIRECTIONS, DATA_TYPES, LAYOUTS, lines):
      line = line.strip()

      # Skip empty lines
      if len(line) == 0 or line[0] == '#':
        continue
      # Skip int8 non-fwd convolutions
      if datatype == '-t i8' and direction != '-F 1':
        continue

      # Skip datatype if already in
      datatype = f"{datatype} "
      # check for the presense of a positional arg
      if line[0][0] != "-":
        datatype = ""

      # Skip direction if already in
      direction = f"{direction} "
      if "-F" in line:
        direction = ""

      # Skip filter layout if already in
      filter_layout = f"-f {layout} "
      if "-f" in line:
        filter_layout = ""

      # Skip input layout if already in
      input_layout = f"-I {layout} "
      if "-I" in line:
        input_layout = ""

      # Skip output layout if already in
      output_layout = f"-O {layout} "
      if "-O" in line:
        output_layout = ""

      one_config = f"{datatype}{direction}{filter_layout}{input_layout}{output_layout}{line}"
      if one_config not in configs:
        configs.append(one_config)

  return configs


def parse_line(line, dbt):
  """Parse a command-line-style conv config into a ConvolutionConfig object."""

  print(f"Parsing line {line}")

  # '-t 1' means 'enable timing' which is confused with -t for type.
  line = line.replace("-t 1", "")

  # Convert the line ("-n 256 -c 1024 -H 14 ...") to dict of flag and value.
  i = iter(line.split())
  options = dict(zip(i, i))
  #  print(f"options = {options}")

  # Mapping of flag to field name.
  # -F 1 -n 2 -c 1280 -H 32 -W 32 -k 640 -y 1 -x 1 -p 0 -q 0 -u 1 -v 1 -l 1 -j 1 -m conv -g 1 -t 1
  fields = {
      '-F': 'direction',
      '-f': 'fil_layout',
      '-I': 'in_layout',
      '-O': 'out_layout',
      '-n': 'batchsize',
      '-c': 'in_channels',
      '-H': 'in_h',
      '-W': 'in_w',
      '-k': 'out_channels',
      '-y': 'fil_h',
      '-x': 'fil_w',
      '-p': 'pad_h',
      '-q': 'pad_w',
      '-u': 'conv_stride_h',
      '-v': 'conv_stride_w',
      '-l': 'dilation_h',
      '-j': 'dilation_w',
      '-g': 'group_size',
      '-m': None,
      '-t': 'data_type'
  }
  # kernel-repeats has no flag, but perfRunner.py uses 5.
  # ConvConfiguration.fromCommandLine accepts but skips -m and -t.
  #   -m is operation and -t is (I think) -time from MIOpenDriver.
  # data_type is inferred from operation -- conv is f32, convfp16 is f16,
  #   convbfp16 is bf16, convint8 is i8

  config = dbt.config_table(kernel_repeats=1)
  for flag, value in options.items():
    field = fields[flag]
    if field:
      setattr(config, field, value)

  return config


def import_cfgs(args: argparse.Namespace, dbt: RocMLIRDBTables,
                logger: logging.Logger):
  """import configs to mysql from file with driver invocations"""
  connect_db()

  configs = get_conv_configurations(os.path.expanduser(args.file_name))
  for line in configs:
    try:
      config = parse_line(line, dbt)

      with DbSession() as session:
        try:
          print(f"Adding config {config} to db")
          session.add(config)
          session.commit()
        except IntegrityError as err:
          logger.warning("Error: %s", err)
          session.rollback()

    except ValueError as err:
      logger.warning(err)

  return len(configs)


def main():
  """Import conv-configs file into database rocmlir_conv_config table."""
  # pylint: disable=duplicate-code
  parser = argparse.ArgumentParser()
  parser.add_argument('-f',
                      '--file_name',
                      type=str,
                      dest='file_name',
                      help='File to import')
  args = parser.parse_args()
  dbt = RocMLIRDBTables(session_id=None)
  logger = setup_logger('import_configs')
  counts = import_cfgs(args, dbt, logger)
  logger.info('New configs added: %u', counts)


if __name__ == '__main__':
  main()
