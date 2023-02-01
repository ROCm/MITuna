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
"""Functions for interacting with MIOpen perf and find db """
import sys
import os
import sqlite3

from typing import Any, List, Tuple
from tuna.utils.logger import setup_logger
from tuna.metadata import SQLITE_CONFIG_COLS, ARCH_NUM_CU_LIST

LOGGER = setup_logger('AnalyzeParseDB')


def insert_config_sqlite(cnx: sqlite3.Connection, fds: dict) -> int:
  """insert a config into the sqlite table """
  vals: list
  vals = [fds[x] for x in SQLITE_CONFIG_COLS]

  cur: sqlite3.Cursor
  cur = cnx.cursor()
  query: str
  query = "INSERT into config(" + ", ".join(
      SQLITE_CONFIG_COLS) + " ) values ( " + ",".join(
          [" ? "] * len(SQLITE_CONFIG_COLS)) + ");"
  cur.execute(query, tuple(vals))
  cur.execute("select last_insert_rowid() as id;")
  res: list
  res = cur.fetchall()
  cur.close()
  return res[0][0]


def get_config_sqlite(cnx: sqlite3.Connection, fds: dict) -> int:
  """get the config id from the sqlite table matching the fds conditions"""
  vals: List[Any]
  vals = [fds[x] for x in SQLITE_CONFIG_COLS]
  conditions: List
  conditions = [f'{col} = ?' for col in SQLITE_CONFIG_COLS]
  query: str = 'SELECT id from config where ' + ' AND '.join(conditions) + ';'
  cur: sqlite3.Cursor
  cur = cnx.cursor()
  cur.execute(query, tuple(vals))
  res: list = cur.fetchall()
  cur.close()
  config_id: int
  if len(res) == 1:
    config_id = res[0][0]
  elif not res:
    config_id = insert_config_sqlite(cnx, fds)
  else:
    LOGGER.error('Found #duplicate configs: %u', len(res))
    LOGGER.error('Non unique config found, db corrupt')
    sys.exit(-1)
  return config_id


def get_sqlite_data(cnx: sqlite3.Connection, table_name: str,
                    fds: dict) -> Tuple[List, List]:
  """get the config id from the sqlite table matching the fds conditions"""
  conditions: List = []
  if fds:
    key: str
    val: str
    for key, val in fds.items():
      if isinstance(val, list):
        val = ','.join([str(item) for item in val])
        conditions.append(f'{key} in ({val})')
      elif isinstance(val, int):
        conditions.append(f'{key} = {val}')
      else:
        conditions.append(f'{key} = \'{val}\'')
  query: str = f'SELECT * from {table_name}'
  if conditions:
    query = query + ' where ' + ' AND '.join(conditions)
  query = query + ';'
  #LOGGER.info(query)
  cur: sqlite3.Cursor = cnx.cursor()
  cur.execute(query)
  columns: list = [x[0] for x in cur.description]
  res: list = cur.fetchall()
  cur.close()

  return res, columns


def get_sqlite_table(cnx: sqlite3.Connection,
                     table_name: str,
                     include_id: bool = False) -> Tuple[List, List]:
  """return the sqlite table """
  query: str = f'SELECT * from {table_name} LIMIT 1'
  cur: sqlite3.Cursor = cnx.cursor()
  cur.execute(query)
  columns: List
  if include_id:
    columns = [x[0] for x in cur.description]
  else:
    columns = [x[0] for x in cur.description if x[0] != 'id']
  query = f"SELECT {','.join(columns)} FROM {table_name};"
  cur.execute(query)
  res: List = cur.fetchall()
  cur.close()
  return res, columns


def get_sqlite_row(cnx: sqlite3.Connection, table: str,
                   tid: dict) -> Tuple[List, List]:
  """return the config row for the given id"""
  query = f'SELECT * from {table} where id={tid}'
  cur: sqlite3.Cursor = cnx.cursor()
  cur.execute(query)
  res: List = cur.fetchall()
  row: List = res[0]
  columns: List = [x[0] for x in cur.description]
  return row, columns


def insert_solver_sqlite(cnx: sqlite3.Connection, slv: dict) -> None:
  """insert solver into sqlite """

  config: int = slv['config']
  solver_id: str = slv['solver']
  params: str = slv['params']
  mrk: str = "?"

  where_clause = f" where config = {mrk} and solver = {mrk}"
  query: str = "select id from perf_db " + where_clause
  cur: sqlite3.Cursor
  cur = cnx.cursor()
  cur.execute(query, (config, solver_id))
  res: list = cur.fetchall()
  if not res:
    query = f"insert into perf_db(config, solver, params) values \
    ({mrk}, {mrk}, {mrk});"

    cur.execute(query, (config, solver_id, params))
  else:
    perf_id: int = res[0][0]
    query = f"update perf_db set params = {mrk} where id={mrk};"
    cur.execute(query, (params, perf_id))

  cur.close()


def parse_pdb_filename(fname: str) -> Tuple[str, int]:
  """parse filename of perfdb file"""
  fname = os.path.basename(fname)
  found: bool = False
  item: str
  arch: str
  num_cu: int
  num_cu_str: str
  db_arch: str
  for item in ARCH_NUM_CU_LIST:
    arch, num_cu_str = item.split('-')
    num_cu = int(num_cu_str)
    db_arch = f'{arch}_{num_cu}'
    if num_cu > 64:
      db_arch = f'{arch}{num_cu:x}'
    if db_arch in fname:
      found = True
      break

  if not found:
    raise ValueError('Invalid perf db filename')

  return (arch, num_cu)


def mysql_to_sqlite_cfg(in_perf_cfg: dict) -> dict:
  """convert values to represent sqlite config table"""
  perf_cfg: dict = in_perf_cfg.copy()

  if perf_cfg['direction'] in ('B', 'W'):
    tmp: str
    tmp = perf_cfg['out_channels']
    perf_cfg['out_channels'] = perf_cfg['in_channels']
    perf_cfg['in_channels'] = tmp

    perf_cfg['in_w'] = int((perf_cfg['in_w'] - perf_cfg['fil_w'] +
                            2 * perf_cfg['pad_w']) / perf_cfg['conv_stride_w'] +
                           1)
    perf_cfg['in_h'] = int((perf_cfg['in_h'] - perf_cfg['fil_h'] +
                            2 * perf_cfg['pad_h']) / perf_cfg['conv_stride_h'] +
                           1)
    if perf_cfg['spatial_dim'] == 3:
      perf_cfg['in_d'] = int(
          (perf_cfg['in_d'] - perf_cfg['fil_d'] + 2 * perf_cfg['pad_d']) /
          perf_cfg['conv_stride_d'] + 1)

  return perf_cfg


def sqlite_to_mysql_cfg(in_perf_cfg: dict) -> dict:
  """convert values to represent mysql config table"""
  perf_cfg: dict = in_perf_cfg.copy()

  if perf_cfg['direction'] in ('B', 'W'):
    tmp: str
    tmp = perf_cfg['out_channels']
    perf_cfg['out_channels'] = perf_cfg['in_channels']
    perf_cfg['in_channels'] = tmp

    #in_w = (out_w - 1) * stride_w + fil_w - 2pad_w
    perf_cfg['in_w'] = int((perf_cfg['in_w'] - 1) * perf_cfg['conv_stride_w'] +
                           perf_cfg['fil_w'] - 2 * perf_cfg['pad_w'])
    perf_cfg['in_h'] = int((perf_cfg['in_h'] - 1) * perf_cfg['conv_stride_h'] +
                           perf_cfg['fil_h'] - 2 * perf_cfg['pad_h'])
    if perf_cfg['spatial_dim'] == 3:
      perf_cfg['in_d'] = int((perf_cfg['in_d'] - 1) *
                             perf_cfg['conv_stride_d'] + perf_cfg['fil_d'] -
                             2 * perf_cfg['pad_d'])

    return perf_cfg

  return perf_cfg
