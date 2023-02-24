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
"""Module to represent MIOpen subcommands parsers"""
import jsonargparse
from tuna.parse_args import TunaArgs, setup_arg_parser


def get_import_cfg_parser(
    with_yaml: bool = True) -> jsonargparse.ArgumentParser:
  """Return parser for import_configs subcommand"""

  parser = setup_arg_parser(
      'Import MIOpenDriver commands and MIOpen performance DB entries.',
      [TunaArgs.VERSION, TunaArgs.CONFIG_TYPE],
      with_yaml=with_yaml)
  parser.add_argument(
      '-c',
      '--command',
      type=str,
      dest='command',
      default=None,
      help='Command override: run a different command on the imported configs',
      choices=[None, 'conv', 'convfp16', 'convbfp16'])
  parser.add_argument('-b',
                      '--batches',
                      type=str,
                      dest='batches',
                      help='Batch sizes to iterate over in the given configs')
  parser.add_argument('-f',
                      '--file_name',
                      type=str,
                      dest='file_name',
                      help='File to import')
  parser.add_argument(
      '--mark_recurrent',
      dest='mark_recurrent',
      action="store_true",
      help='Indicate whether you want the configs to be marked as recurrent')
  parser.add_argument('-t',
                      '--tag',
                      type=str,
                      required=True,
                      dest='tag',
                      help='Tag to mark the origin of this \
                      config, if config not present it will insert. No wildcard columns for \
                      tagging.')
  parser.add_argument(
      '-T',
      '--tag_only',
      action='store_true',
      dest='tag_only',
      help=
      'Tag to mark the origin of this config but skips the insert new config \
                      step in case the config does not exist in the table. Wildcard columns \
                      allowed for tagging')

  return parser
