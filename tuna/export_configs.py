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
"""create a file of driver strings from a set of sql jobs """
from tuna.sql import DbCursor
from tuna.metadata import TABLE_COLS_FUSION_MAP
from tuna.metadata import TABLE_COLS_CONV_MAP
from tuna.utils.logger import setup_logger
from tuna.parse_args import TunaArgs, setup_arg_parser


def parse_args():
  """command line parser"""
  parser = setup_arg_parser(
      'Dump out MIOpenDriver commands for selected fields', [TunaArgs.ARCH])
  parser.add_argument(
      '-q',
      '--query',
      type=str,
      dest='query',
      default=None,
      help=
      'Where clause to be appended to the select query on the join of the config and job table'
  )
  parser.add_argument(
      '-f',
      '--full_query',
      type=str,
      dest='full_query',
      default=None,
      help=
      'The complete query to run and instead of the where clause being joined with a join on config'
  )
  parser.add_argument('filename',
                      type=str,
                      help='Filename to write the resulting script to')
  args = parser.parse_args()
  return args


def main():
  """main"""
  args = parse_args()
  # Setup logging
  logger = setup_logger('ExportConfigs')
  table_cols_conv_invmap = {v[0]: k for k, v in TABLE_COLS_CONV_MAP.items()}
  table_cols_fusion_invmap = {v[0]: k for k, v in TABLE_COLS_FUSION_MAP.items()}

  outfile = open(args.filename, "w")

  with DbCursor() as cur:
    count = 0
    if args.full_query is not None:
      query = args.full_query
      cur.execute(query)
    else:
      query = "SELECT config.* FROM job INNER JOIN conv_config as config \
          ON config.id = job.config WHERE config.valid = TRUE AND job.valid = TRUE \
          AND arch = %s AND ({})".format(args.query)
      cur.execute(query, (args.arch,))
    # cur.execute("select * from config where valid = TRUE;")
    sub_cmd_idx = cur.column_names.index('cmd')

    for row in cur:
      sub_cmd = row[sub_cmd_idx]
      bash_cmd = './bin/MIOpenDriver {} -V 0 '.format(sub_cmd)
      for idx, val in enumerate(row):
        if cur.column_names[idx] in ['id', 'cmd', 'valid']:
          continue
        if val is not None:
          if sub_cmd in ['conv', 'convfp16']:
            arg_name = table_cols_conv_invmap[cur.column_names[idx]]
          elif sub_cmd in ['CBAInfer', 'CBAInferfp16']:
            if cur.column_names[idx] == 'direction':
              continue
            arg_name = table_cols_fusion_invmap[cur.column_names[idx]]
          bash_cmd += ' -' + arg_name + ' ' + val
      outfile.write(bash_cmd + '\n')
      count += 1

  outfile.close()
  logger.warning("Added %s entries", count)


if __name__ == '__main__':
  main()
