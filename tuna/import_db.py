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
import os
import sqlite3

from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.logger import setup_logger
from tuna.analyze_parse_db import get_sqlite_data, sqlite_to_mysql_cfg, parse_pdb_filename
from tuna.tables import DBTables
from tuna.helper import valid_cfg_dims
from tuna.parse_args import TunaArgs, setup_arg_parser
from tuna.session import Session
from tuna.config_type import ConfigType
from tuna.driver_conv import DriverConvolution
from tuna.import_configs import insert_config
from tuna.metadata import PREC_TO_CMD
from tuna.metadata import get_solver_ids
from tuna.parsing import parse_fdb_line

LOGGER = setup_logger('import_db')

COMMIT_FREQ = 1000


def parse_args():
  """command line parsing"""
  parser = setup_arg_parser('Import Performance DBs once tunning is finished',
                            [TunaArgs.VERSION, TunaArgs.SESSION_ID])
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


def get_cfg_driver(sqlite_cfg):
  """Takes in a dict containing a sqlite config row
  and returns convolution driver object"""
  mysql_cfg = sqlite_to_mysql_cfg(sqlite_cfg)

  #constructing a conv_config entry (dict)
  mysql_cfg['in_layout'] = mysql_cfg['layout']
  mysql_cfg['out_layout'] = mysql_cfg['layout']
  mysql_cfg['fil_layout'] = mysql_cfg['layout']
  cnv_cmd = PREC_TO_CMD.get(ConfigType.convolution).get(mysql_cfg['data_type'])

  driver = DriverConvolution('', cmd=cnv_cmd, kwargs=mysql_cfg)

  return driver


def get_sql_cfg_id_map(dbt, cnx, args):
  """ load configs into db from sqlite, create mapping to mysql configs """
  counts = {}
  counts['cnt_configs'] = 0
  counts['cnt_tagged_configs'] = set()

  cfg_filter = None
  config_rows, config_cols = get_sqlite_data(cnx, 'config', cfg_filter)

  total = len(config_rows)
  cvrt = {}  #update config id to inserted location
  LOGGER.info("Insert Configurations")
  for i, cfg_row in enumerate(config_rows):
    sqlite_cfg = dict(zip(config_cols, cfg_row))
    sqlite_id = sqlite_cfg['id']
    sqlite_cfg = valid_cfg_dims(sqlite_cfg)

    driver = get_cfg_driver(sqlite_cfg)
    ins_id = insert_config(driver, counts, dbt, args)
    cvrt[sqlite_id] = ins_id

    if (total / 10) % (i + 1) == 0:
      LOGGER.info("Config Insert %s: %s", i, cfg_row)

  return cvrt


def set_fdb_data(fdb_entry, fdb_key, alg_lib, workspace, kernel_time):
  """ set fdb specific data, default for pdb if missing """
  fdb_entry.fdb_key = fdb_key
  fdb_entry.alg_lib = alg_lib
  fdb_entry.workspace_sz = workspace
  fdb_entry.kernel_time = kernel_time
  fdb_entry.kernel_group = fdb_entry.id

  if fdb_entry.params is None:
    fdb_entry.params = ''


def set_pdb_data(fdb_entry, params):
  """ set pdb specific data, fill defaults for fdb if missing """
  fdb_entry.params = params
  if fdb_entry.kernel_time is None:
    fdb_entry.kernel_time = -1
  if fdb_entry.workspace_sz is None:
    fdb_entry.workspace_sz = -1


def get_fdb_entry(session, dbt, config, solver, ocl):
  """ return referenc to fdb entry in mysql, existing one if present"""
  fdb_entry = dbt.find_db_table()
  fdb_entry.config = config
  fdb_entry.solver = solver
  fdb_entry.session = dbt.session_id
  fdb_entry.opencl = ocl
  fdb_entry.logger = LOGGER
  fdb_query = fdb_entry.get_query(session, dbt.find_db_table, dbt.session_id)
  obj = fdb_query.first()
  if obj:  # existing entry in db
    fdb_entry = obj
  else:
    # Insert the above entry
    session.add(fdb_entry)

  return fdb_entry


def insert_perf_db(dbt, perf_rows, perf_cols, cvrt):
  """insert sqlite perf_db table into mysql perf_db"""
  insert_ids = []
  solver_id_map, _ = get_solver_ids()
  with DbSession() as session:
    for row in perf_rows:
      entry = dict(zip(perf_cols, row))
      cfg_id = cvrt[entry['config']]
      slv_id = solver_id_map[entry['solver']]

      fdb_entry = get_fdb_entry(session, dbt, cfg_id, slv_id, False)
      set_pdb_data(fdb_entry, entry['params'])

      fdb_entry.valid = True
      insert_ids.append(fdb_entry.id)

      if len(insert_ids) % COMMIT_FREQ == 0:
        session.commit()
        session.refresh(fdb_entry)
        LOGGER.info("Ins pdb count %s, fdb_id: %s, fdb_key: %s",
                    len(insert_ids), fdb_entry.id, fdb_entry.fdb_key)

    session.commit()

  return insert_ids


def record_perfdb(dbt, args):  #pylint: disable=too-many-locals
  """insert perf_db entry from sqlite file to mysql"""
  cnx = sqlite3.connect(args.target_file)
  cvrt = get_sql_cfg_id_map(dbt, cnx, args)

  perf_rows, perf_cols = get_sqlite_data(cnx, 'perf_db',
                                         {'config': list(cvrt.keys())})

  #inserting perf_fb entry
  LOGGER.info("Insert Performance db")
  insert_perf_db(dbt, perf_rows, perf_cols, cvrt)


def record_fdb(dbt, args):
  """insert find_db entries from fdb text file """
  counts = {}
  counts['cnt_configs'] = 0
  counts['cnt_tagged_configs'] = set()
  solver_id_map, _ = get_solver_ids()
  with open(os.path.expanduser(args.target_file), "r") as infile:  # pylint: disable=unspecified-encoding
    with DbSession() as session:
      num_line = 0
      for line in infile:
        ins_id = insert_config(DriverConvolution(line), counts, dbt, args)

        fdb_data = parse_fdb_line(line)
        for fdb_key, algs in fdb_data.items():
          for alg in algs:
            slv_id = solver_id_map[alg['solver']]
            fdb_entry = get_fdb_entry(session, dbt, ins_id, slv_id, False)
            set_fdb_data(fdb_entry, fdb_key, alg['alg_lib'],
                         alg['workspace_sz'], alg['kernel_time'])

        num_line += 1
        if num_line % COMMIT_FREQ == 0:
          session.commit()
          session.refresh(fdb_entry)
          LOGGER.info("Ins fdb count %s, fdb_id: %s, fdb_key: %s", num_line,
                      fdb_entry.id, fdb_entry.fdb_key)

      session.commit()


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

  args.label = "imported_perf_db"
  args.docker_name = "n_a"
  args.solver_id = None
  args.mark_recurrent = False
  args.tag = None
  args.config_type = ConfigType.convolution
  args.arch, args.num_cu = parse_pdb_filename(args.target_file)
  if not args.session_id:
    args.session_id = Session().add_new_session(args, None)
  dbt = DBTables(session_id=args.session_id)
  if args.target_file.endswith(".db"):
    record_perfdb(dbt, args)
  elif args.target_file.endswith(".fdb.txt"):
    record_fdb(dbt, args)


if __name__ == '__main__':
  main()
