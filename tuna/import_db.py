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
"""script for merging find db or perf db files, across machines or locally"""
import sqlite3

from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.logger import setup_logger
from tuna.analyze_parse_db import get_sqlite_data, sqlite_to_mysql_cfg, parse_pdb_filename
from tuna.metadata import MYSQL_PERF_CONFIG
from tuna.metadata import CONV_CONFIG_COLS
from tuna.miopen_tables import Solver
from tuna.tables import DBTables
from tuna.helper import compose_tensors, valid_cfg_dims
from tuna.helper import mysqldb_insert_dict, mysqldb_overwrite_table
from tuna.parse_args import TunaArgs, setup_arg_parser
from tuna.session import Session

LOGGER = setup_logger('import_db')


def parse_args():
  """command line parsing"""
  parser = setup_arg_parser('Import Performance DBs once tunning is finished',
                            [TunaArgs.VERSION])
  parser.add_argument(
      '-t',
      '--target_file',
      type=str,
      default=None,
      dest='target_file',
      required=True,
      help=
      'Supply an absolute path to the performance database file. This file will be imported.'
  )
  parser.add_argument('--rocm_v',
                      dest='rocm_v',
                      type=str,
                      default=None,
                      required=True,
                      help='Specify rocm version for perf db')
  parser.add_argument('--miopen_v',
                      dest='miopen_v',
                      type=str,
                      default=None,
                      required=True,
                      help='Specify MIOpen version for perf db')

  args = parser.parse_args()

  return args


def insert_configs(context, configs):
  """Read in perf_config sqlite table from configs arg and insert into mysql tables.
  This function constructs a temporary perf_cfg dict that translates a sqlite perf_config entry
  into mysql conv_config and perf_config entry"""
  #fields from perf_config table sans conv_config FKEY and timestamps
  insert_ids = []
  ret = False

  for i, config in enumerate(configs):
    perf_cfg = {
        key: val for key, val in config.items() if key in MYSQL_PERF_CONFIG
    }

    #mysql_cfg represents a conv_config entry
    mysql_cfg = {
        key: val for key, val in config.items() if key in CONV_CONFIG_COLS
    }
    mysql_cfg['input_tensor'] = config['input_tensor']
    mysql_cfg['weight_tensor'] = config['weight_tensor']
    #only use valid mysql configs
    mysql_cfg['valid'] = '1'
    cfg_filter = mysql_cfg.copy()
    ret, cfg_idx = mysqldb_insert_dict(context.table_cfg, mysql_cfg, cfg_filter)
    if not ret:
      LOGGER.error('Could not update config: %s', mysql_cfg)
      break

    if ret:
      insert_ids.append(cfg_idx)
    else:
      LOGGER.error('Could not update perf_config: %s', perf_cfg)
      break

    if i % 100 == 0:
      LOGGER.info('Loading configs... %s', i)

  return ret, insert_ids


def insert_perf_db(context, perf_rows, perf_cols, cvrt):
  """insert sqlite perf_db table into mysql perf_db"""

  perf_db = []
  for row in perf_rows:
    entry = dict(zip(perf_cols, row))
    entry['config'] = cvrt[entry['config']]
    entry.pop('id', None)
    entry['session'] = context.session_id
    entry['valid'] = 1

    with DbSession() as session:
      query = session.query(Solver).filter(Solver.solver == entry['solver'])
      entry['solver'] = query.one().id

    perf_db.append(entry)

  ret, insert_ids = mysqldb_overwrite_table(context.table_perf_db, perf_db,
                                            ['solver', 'config', 'session'])
  if not ret:
    LOGGER.error('Could not update perf_db: %s', perf_db)

  return ret, insert_ids


def record_perfdb(args, cfg_filter=None):
  """insert perf_db entry from sqlite file to mysql"""
  cnx = sqlite3.connect(args.target_file)

  config_rows, config_cols = get_sqlite_data(cnx, 'config', cfg_filter)
  ret = record_perfdb_v2(args, cnx, config_rows, config_cols, cfg_filter)

  return ret


def record_perfdb_v2(args, cnx, config_rows, config_cols, cfg_filter):  #pylint: disable=too-many-locals
  """Get sqlite db rows and insert into msyql for Tuna version 1.0.0"""
  #configs will contain a mysql perf_config entry + its associated
  #conv_config(with tensors) entry in the same dict
  configs = []
  for cfg_row in config_rows:
    perf_cfg = dict(zip(config_cols, cfg_row))
    perf_cfg = valid_cfg_dims(perf_cfg)
    configs.append(get_perf_cfg(perf_cfg, args))

  if not configs:
    print_sqlite_rows(cnx, cfg_filter)
    return False

  perf_rows, perf_cols = get_sqlite_data(
      cnx, 'perf_db', {'config': [perf_cfg['id'] for perf_cfg in configs]})

  #inserting perf_config from sqlite configs
  ret, insert_ids = insert_configs(args, configs)
  if not ret:
    return False

  cvrt = {}  #update config id to inserted location
  for i, _ in enumerate(insert_ids):
    cvrt[configs[i]['id']] = insert_ids[i]

  #inserting perf_fb entry
  ret, _ = insert_perf_db(args, perf_rows, perf_cols, cvrt)

  return ret


def get_perf_cfg(perf_cfg, args):
  """Takes in a dict containing a sqlite perf_config row
  and returns a dict that will contain all cols needed for a
  mysql perf_config and its associated (conv) config row/FKey"""
  perf_cfg = sqlite_to_mysql_cfg(perf_cfg)
  #setting aside perf_config cols that are hidden in tensor/not in conv_config
  p_dict = {}
  p_dict['data_type'] = perf_cfg['data_type']
  p_dict['bias'] = perf_cfg['bias']
  p_dict['layout'] = perf_cfg['layout']

  #constructing a conv_config entry (dict)
  perf_cfg = compose_tensors(perf_cfg, args, True)
  #appending perf_config cols from tensors/not in conv_config
  for key, value in p_dict.items():
    perf_cfg[key] = value
  #TODOS: do we need to remove these? they are used in composing a tensor row
  #perf_cfg = valid_cfg_dims(perf_cfg)
  #LOGGER.info('post prune: %s', perf_cfg)
  return perf_cfg


def print_sqlite_rows(cnx, cfg_filter):
  """Read all sqlite rows from config table and print for debugging"""
  configs = []
  LOGGER.error('No configs found: %s', cfg_filter)
  config_rows, config_cols = get_sqlite_data(cnx, 'config', None)
  for cfg_row in config_rows:
    perf_cfg = dict(zip(config_cols, cfg_row))
    configs.append(perf_cfg)
  LOGGER.error('All configs: %s', configs)


def main():
  """main"""
  args = parse_args()

  args.label = "imported perf db"
  args.arch, args.num_cu = parse_pdb_filename(args.target_file)
  args.session_id = Session().add_new_session(args, None)

  dbt = DBTables(session_id=args.session_id)
  args.table_cfg = dbt.config_table
  args.table_perf_db = dbt.find_db_table
  record_perfdb(args)


if __name__ == '__main__':
  main()
