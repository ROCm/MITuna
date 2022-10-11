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
"""pull finddb down into a pandas dataframe object from the tuna database"""

import os
import argparse
from enum import Enum

import pandas as pd
from sqlalchemy import and_, or_

from tuna.utils import logging
from tuna.tables import DBTables
import tuna.utils.tools.io as io_tools
import tuna.utils.tools.df as df_tools
from tuna.config_type import ConfigType
from tuna.utils.helpers import pretty_list
from tuna.dbBase.sql_alchemy import DbSession

_DEFAULT_OUTPUT_DIR = os.path.join(os.getcwd(), 'finddb_')


def load_finddb(finddb_pickle_filename, tag=''):
  """ loads finddb dataframe from a pickle

  Attributes:
    finddb_pickle_filename: pickle of finddb dataframe
    tag: tag for finddb (just for better logging)
  """
  finddb = io_tools.safe_load(None, finddb_pickle_filename,
                              df_tools.from_pickle)
  describe_finddb(finddb, tag)
  return finddb


def describe_finddb(finddb, tag=''):
  """ logs a description of finddb

  Attributes:
    finddb: finddb dataframe
    tag: tag for finddb (just for better logging)
  """
  if len(finddb) == 0:
    logging.warning('finddb empty!')
  else:
    logging.info(f'{tag}finddb corresponds to session IDs: %s' %
                 pretty_list(finddb['session'].unique()))
    logging.info(f'Total entries in {tag}finddb: %d' % len(finddb))
    logging.info(f'Total unique solvers in {tag}finddb: %d' %
                 len(finddb['solver'].unique()))

    if "arch" in finddb.columns and "num_cu" in finddb.columns:
      gpus_present = df_tools.unique_combinations(finddb, ["arch", "num_cu"])
      gpus_present_lst = [f"{x['arch']}({x['num_cu']})" for x in gpus_present]
      logging.info(f'GPUS in {tag}finddb: %s' % pretty_list(gpus_present_lst))


def gen_finddb(session_ids, invalid_too, opencl_only):
  """pulls down finddb into a pandas dataframe from the mysql database

  Attributes:
    session_ids: finddb dataframe will only contain entries from these session_ids
    invalid_too: finddb dataframe will contain invalid entries too
    opencl_only: finddb dataframe will only contain entries with opencl
  """
  db_tables = DBTables(config_type=ConfigType.convolution)
  finddb = db_tables.golden_table

  logging.info(f'tuna database name: {os.environ["TUNA_DB_NAME"]}')
  logging.info(f'finddb table name: {finddb.__tablename__}')

  with DbSession() as session:
    logging.log(f'quering {finddb.__tablename__}...', end_char='\r')
    query = session.query(finddb)
    query = query.filter(
        and_(finddb.kernel_time != -1, finddb.workspace_sz != -1))
    if session_ids is not None:
      # why is False the first argument in the OR clause below? see:
      # docs.sqlalchemy.org/en/14/core/sqlelement.html#sqlalchemy.sql.expression.or_
      # pylint: disable=comparison-with-callable
      query = query.filter(
          or_(False,
              *(finddb.session == session_id for session_id in session_ids)))
      # pylint: enable=comparison-with-callable
    if invalid_too is False:
      query = query.filter(finddb.valid == True)  # pylint: disable=singleton-comparison
    if opencl_only is True:
      query = query.filter(finddb.opencl == True)  # pylint: disable=singleton-comparison

    query = query.order_by(finddb.update_ts.desc(), finddb.config)

    logging.reset_line()
    logging.success('query processed!')

    logging.log('reading query into a dataframe...', end_char='\r')
    df = pd.read_sql(query.statement, session.bind)  # pylint: disable=invalid-name
    logging.reset_line()

    describe_finddb(df)

    return df


class FinddbParsing:
  """utilities to add and parse finddb-related Arguments"""

  SIGNATURE = '__hasFinddbArgs__'

  class ARGS(Enum):
    """defines finddb-related arguments and their default values"""
    SESSION_IDS = ('session_ids', None)
    INVALID_TOO = ('invalid_too', False)
    OPENCL_ONLY = ('opencl_only', False)

    def __init__(self, arg_name, arg_default):
      self.arg_name = arg_name
      self.arg_default = arg_default

    @property
    def name(self):  # pylint: disable=function-redefined, invalid-overridden-method
      """returns the argument-name"""
      return self.arg_name

    @property
    def default(self):
      """returns the argument's default value"""
      return self.arg_default

  @classmethod
  def set_finddb_args(cls, parser):
    """adds finddb-related Arguments to a parser

    Attributes:
      parser: argparse.ArgumentParser object
    """
    # SESSION_IDS
    parser.add_argument(
        f'--{FinddbParsing.ARGS.SESSION_IDS.name}',
        type=int,
        nargs='*',
        default=FinddbParsing.ARGS.SESSION_IDS.default,
        dest=FinddbParsing.ARGS.SESSION_IDS.name,
        help=
        'IDs of tuning sessions to fetch finddb for (default: all tuning sessions)'
    )
    # INVALID_TOO
    parser.add_argument(
        f'--{FinddbParsing.ARGS.INVALID_TOO.name}',
        action='store_true',
        default=FinddbParsing.ARGS.INVALID_TOO.default,
        dest=FinddbParsing.ARGS.INVALID_TOO.name,
        help='dump both valid and invalid kernels (default: False)')
    # OPENCL_ONLY
    parser.add_argument(
        f'--{FinddbParsing.ARGS.OPENCL_ONLY.name}',
        action='store_true',
        default=FinddbParsing.ARGS.OPENCL_ONLY.default,
        dest=FinddbParsing.ARGS.OPENCL_ONLY.name,
        help='only dump kernels that use opencl extension (default: False)')

    # sign the parser
    setattr(parser, FinddbParsing.SIGNATURE, True)

  @classmethod
  def get_finddb_args(cls, parsed_args):
    """parses finddb-related Arguments from a parser

    Attributes:
      parsed_args: parsed arguments returned by parser.parse_args() call
    """

    return {
        arg.name: getattr(parsed_args, arg.name) for arg in FinddbParsing.ARGS
    }

  @classmethod
  def get_default_finddb_args(cls):
    """returns default values for finddb-related arguments"""
    return {arg.name: arg.default for arg in FinddbParsing.ARGS}


def main():
  """ main """
  default_output_dir = _DEFAULT_OUTPUT_DIR

  parser = argparse.ArgumentParser(
      description='Fetches finddb and exports it as a Pandas DataFrame')
  parser.add_argument(
      '-o',
      '--out',
      type=str,
      default=default_output_dir,
      help=
      f'directory to out pickled finddb pandas-dataframe to (current: {default_output_dir})'
  )
  FinddbParsing.set_finddb_args(parser)

  args = parser.parse_args()

  finddb = gen_finddb(**FinddbParsing.get_finddb_args(args))

  io_tools.safe_save(finddb, os.path.join(args.out, 'finddb.pkl'),
                     df_tools.to_pickle)
  logging.dump_logs(os.path.join(args.out, 'gen_finddb.log'))


if __name__ == '__main__':
  main()
