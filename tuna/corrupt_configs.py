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
"""Corrupt config module"""
import sys
import logging

from tuna.sql import DbCursor
from tuna.metadata import TABLE_COLS_FUSION_MAP
from tuna.metadata import TABLE_COLS_CONV_MAP

LOGGER = get_logger()


def get_logger():
  """Setting up logger"""
  logger = logging.getLogger('CorruptConfigs')
  hdlr = logging.FileHandler('corrupt_configs.log')
  formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
  hdlr.setFormatter(formatter)
  logger.addHandler(hdlr)
  logger.setLevel(logging.INFO)

  return logger


def main():
  """Main module function"""
  if len(sys.argv) == 3:
    file_name = sys.argv[1]
    arch = sys.argv[2]
  else:
    sys.exit("Usage: " + sys.argv[0] + " <output_file> <arch>")

  table_cols_conv_invmap = {v: k for k, v in TABLE_COLS_CONV_MAP.items()}
  table_cols_fusion_invmap = {v: k for k, v in TABLE_COLS_FUSION_MAP.items()}

  outfile = open(file_name, "w")
  sub_cmd_idx = None
  with DbCursor() as cur:
    cur.execute(
        "select config.* from job inner join config on config.id = job.config where \
            job.arch = %s and reason = 'corrupt';", (arch,))
    sub_cmd_idx = cur.column_names.index('cmd')
    count = 0

    for row in cur:
      sub_cmd = row[sub_cmd_idx]
      bash_cmd = 'echo {}; ./bin/MIOpenDriver {} -V 0 '.format(row[0], sub_cmd)
      for idx, fds in enumerate(row):
        if cur.column_names[idx] in ['id', 'cmd']:
          continue
        if fds is not None:
          if sub_cmd in ['conv', 'convfp16']:
            arg_name = table_cols_conv_invmap[cur.column_names[idx]]
            bash_cmd += ' -' + arg_name + ' ' + fds
          elif sub_cmd in ['CBAInfer', 'CBAInferfp16']:
            arg_name = table_cols_fusion_invmap[cur.column_names[idx]]
            bash_cmd += ' -' + arg_name + ' ' + fds
      outfile.write(bash_cmd + '\n')
      count += 1

  outfile.close()
  LOGGER.warning("Added {} entries".format(count))


if __name__ == '__main__':
  main()
