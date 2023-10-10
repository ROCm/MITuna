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
import jsonargparse
import sys

from sqlalchemy.exc import IntegrityError
from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.db_utility import connect_db
from tuna.utils.logger import setup_logger
from tuna.rocmlir.rocmlir_tables import RocMLIRDBTables
from tuna.rocmlir.config_type import ConfigType


def import_cfgs(args: argparse.Namespace, dbt: RocMLIRDBTables,
                logger: logging.Logger):
  """import configs to mysql from file with driver invocations"""
  connect_db()
  config = dbt.config_table()
  configs = config.get_configurations(os.path.expanduser(args.file_name))
  #print(configs, file=sys.stderr)
  with DbSession() as session:
    for line in configs:
      try:
        config.parse_line(line)
        try:
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
  parser = jsonargparse.ArgumentParser()
  parser.add_argument('-f',
                      '--file_name',
                      type=str,
                      dest='file_name',
                      help='File to import')
  parser.add_argument('--config_type',
                      dest='config_type',
                      help='Specify configuration type',
                      default=ConfigType.convolution,
                      choices=[ct.name for ct in ConfigType],
                      type=ConfigType)
  args = parser.parse_args()
  dbt = RocMLIRDBTables(session_id=None, config_type=args.config_type)
  logger = setup_logger('import_configs')
  counts = import_cfgs(args, dbt, logger)
  logger.info('New configs added: %u', counts)


if __name__ == '__main__':
  main()
