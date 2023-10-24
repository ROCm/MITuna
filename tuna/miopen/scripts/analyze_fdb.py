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
"""script for detecting find db entries with missing perf db entries"""

import argparse
import sqlite3

from tuna.miopen.utils.parsing import parse_fdb_line
from tuna.miopen.utils.analyze_parse_db import get_sqlite_table
from tuna.miopen.driver.convolution import DriverConvolution
from tuna.miopen.utils.helper import valid_cfg_dims
from tuna.miopen.subcmd.import_db import get_cfg_driver
from tuna.utils.logger import setup_logger
from tuna.miopen.db.tables import MIOpenDBTables
from tuna.dbBase.sql_alchemy import DbSession

LOGGER = setup_logger('analyze_fdb')


def parse_args():
  """command line parsing"""
  parser = argparse.ArgumentParser(
      description='Test Find DB for matching Performance DB entries')
  parser.add_argument('-f',
                      '--fdb_file',
                      type=str,
                      dest='fdb_file',
                      required=True,
                      help='Analyze this find db file.')
  parser.add_argument('-p',
                      '--pdb_file',
                      type=str,
                      dest='pdb_file',
                      required=True,
                      help='Compare with this perf db file.')
  parser.add_argument('-o',
                      '--out_file',
                      type=str,
                      default='scan_results.txt',
                      dest='out_file',
                      help='Compare with this perf db file.')
  parser.add_argument('--only_fastest',
                      action='store_true',
                      dest='only_fastest',
                      help='Return results for only the fastest fdb entry.')

  args = parser.parse_args()

  return args


def driver_key(driver):
  """create a key string using driver dict"""
  out_key = []
  drv_dict = sorted(driver.to_dict().items())
  for _, val in drv_dict:
    out_key.append(str(val))
  out_key = '-'.join(out_key)
  return out_key


def build_cfg_groups(cnx_pdb):
  """organize perf db data into groups by config"""
  perf_rows, perf_cols = get_sqlite_table(cnx_pdb, 'perf_db', include_id=True)
  cfg_rows, cfg_cols = get_sqlite_table(cnx_pdb, 'config', include_id=True)

  perf_db = []
  for row in perf_rows:
    perf_entry = dict(zip(perf_cols, row))
    perf_db.append(perf_entry)

  cfg_db = {}
  for row in cfg_rows:
    cfg_entry = dict(zip(cfg_cols, row))
    cfg_db[cfg_entry['id']] = cfg_entry

  cfg_group = {}
  for item in perf_db:
    cfg_id = item['config']

    sqlite_cfg = valid_cfg_dims(cfg_db[cfg_id])
    cfg_drv = driver_key(get_cfg_driver(sqlite_cfg))
    LOGGER.info("pdb ins key %s", cfg_drv)

    if cfg_drv not in cfg_group:
      cfg_group[cfg_drv] = {}
      cfg_group[cfg_drv]['pdb'] = {}

    cfg_entry = cfg_group[cfg_drv]
    cfg_entry['config'] = cfg_db[cfg_id]
    cfg_entry['pdb'][item['solver']] = item

  return cfg_group


def build_find_groups(fdb_file, only_fastest):
  """organize find db line data"""
  line_count = 0
  find_db = {}
  with open(fdb_file) as fdb_fp:  # pylint: disable=unspecified-encoding
    for line in fdb_fp:
      line_count += 1
      driver = DriverConvolution(line)
      cfg_drv = driver_key(driver)
      LOGGER.info("fdb ins key %s", cfg_drv)

      assert cfg_drv not in find_db
      fdb_dict = parse_fdb_line(line)
      if only_fastest:
        for _, alg_list in fdb_dict.items():
          alg_list.sort(key=lambda x: float(x['kernel_time']))
          i = len(alg_list) - 1
          while i > 0:
            if alg_list[i]['kernel_time'] > alg_list[0]['kernel_time']:
              alg_list.pop(i)
            i -= 1

      find_db[cfg_drv] = {}
      find_db[cfg_drv]['fdb'] = fdb_dict
      find_db[cfg_drv]['line_num'] = line_count

  return find_db


def get_tunable_solvers():
  """get list of tunable solvers"""
  dbt = MIOpenDBTables()
  with DbSession() as session:
    query = session.query(dbt.solver_table.solver)\
                      .filter(dbt.solver_table.tunable == 1)
    solvers = [x[0] for x in query.all()]
  return solvers


def compare(fdb_file, pdb_file, outfile, only_fastest):
  """compare find db entries to perf db entries"""
  tunable_s = get_tunable_solvers()
  cfg_group = build_cfg_groups(sqlite3.connect(pdb_file))

  err_list = []
  for cfg_drv, fdb_obj in build_find_groups(fdb_file, only_fastest).items():
    if cfg_drv not in cfg_group:
      err = {
          'line': fdb_obj['line_num'],
          'msg': f"No pdb entries for key: {list(fdb_obj['fdb'].keys())[0]}"
      }
      err_list.append(err)
      LOGGER.error('%s', err['msg'])
      continue
    for fdb_key, alg_list in fdb_obj['fdb'].items():
      for alg in alg_list:
        solver_nm = alg['solver']
        if solver_nm in tunable_s and solver_nm not in cfg_group[cfg_drv]['pdb']:
          err = {
              'line':
                  fdb_obj['line_num'],
              'msg':
                  f"No pdb entries for key: {fdb_key}, "\
                  f"solver: {alg['alg_lib']}:{solver_nm}, kernel_time: {alg['kernel_time']}"
          }
          err_list.append(err)
          LOGGER.error('%s', err['msg'])

  with open(outfile, 'w') as out_fp:  # pylint: disable=unspecified-encoding
    for err in err_list:
      out_fp.write(f'fdb {err["line"]}: {err["msg"]}\n')


def main():
  """main"""
  args = parse_args()
  compare(args.fdb_file, args.pdb_file, args.out_file, args.only_fastest)


if __name__ == '__main__':
  main()
