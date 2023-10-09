#!/usr/bin/env python3
###############################################################################
#
# MIT License
#
# Copyright (c) 2023 Advanced Micro Devices, Inc.
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
""" Module for exporting configs for use in performance runs """

from tuna.parse_args import TunaArgs, setup_arg_parser
from tuna.rocmlir.rocmlir_tables import RocMLIRDBTables
from tuna.rocmlir.config_type import ConfigType, CONVOLUTION, GEMM


def main():
  """Import conv-configs file into database rocmlir_conv_config table."""
  # pylint: disable=duplicate-code
  parser = setup_arg_parser('Export perf-configs from MySQL db',
                            [TunaArgs.VERSION, TunaArgs.SESSION_ID])
  parser.add_argument('-f',
                      '--file_name',
                      type=str,
                      dest='file_name',
                      help='File to import')
  parser.add_argument(
      '--config_type',
      dest='config_type',
      help='Specify configuration type',
      default=CONVOLUTION,
      choices=[CONVOLUTION, GEMM],
      type=ConfigType)
  parser.add_argument('--append',
                      dest='append',
                      action='store_true',
                      help='Append to file instead of overwriting')
  args = parser.parse_args()
  dbt = RocMLIRDBTables(session_id=args.session_id, config_type=args.config_type)
  dbt.results().export_as_tsv(args.file_name, dbt, args.append)


if __name__ == '__main__':
  main()
