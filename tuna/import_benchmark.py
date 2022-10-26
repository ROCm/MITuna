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
from sqlalchemy.exc import IntegrityError

from tuna.dbBase.sql_alchemy import DbSession
from tuna.parse_args import TunaArgs, setup_arg_parser
from tuna.utils.logger import setup_logger
from tuna.db_tables import connect_db, ENGINE
from tuna.tables import ConfigType
from tuna.driver_conv import DriverConvolution
from tuna.driver_bn import DriverBatchNorm
from tuna.tables import DBTables
from tuna.miopen.benchmark import Framework, Model


LOGGER = setup_logger('import_configs')


def parse_args():
  """Parsing arguments"""
  parser = setup_arg_parser(
      'Import MIOpenDriver commands and MIOpen performance DB entries.',
      [])
  parser.add_argument(
      '--framework',
      type=str,
      dest='framework',
      default=None,
      choices=Framework,
      type=Framework
      help='Specify framework')
  parser.add_argument(
      '--update_framework',
      action="store_true",
      dest='update_framework',
      help='Populate framework table with all framework enums')
  parser.add_argument(
      '--model',
      type=str,
      dest='model',
      default=None,
      choices=Model,
      type=Model
      help='Specify model')
  parser.add_argument(
      '--update_model',
      action="store_true",
      dest='update_model',
      help='Populate model table with all model enums')
  parser.add_argument('--version',
                      dest='version',
                      type=str,
                      default=None,
                      required=False,
                      help='Specify model version')
  parser.add_argument('-f',
                      '--file_name',
                      type=str,
                      dest='file_name',
                      help='File to import')

  args = parser.parse_args()
  if args.model and not args.version:
    parser.error('Version needs to be specified with model')
  return args

def import_benchmark(args):
  if args.framework:
  if args.model:
  

def main():
  """Main function"""
  args = parse_args()

  LOGGER.info('New configs added: %u', counts['cnt_configs'])
  if args.tag or args.tag_only:
    LOGGER.info('Tagged configs: %u', len(counts['cnt_tagged_configs']))


if __name__ == '__main__':
  main()

