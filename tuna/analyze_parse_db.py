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

from tuna.utils.logger import setup_logger
from tuna.metadata import SQLITE_CONFIG_COLS, ARCH_NUM_CU_LIST

LOGGER = setup_logger('AnalyzeParseDB')


def insert_config_sqlite(cnx, fds):
  """insert a config into the sqlite table """
  vals = [fds[x] for x in SQLITE_CONFIG_COLS]

  cur = cnx.cursor()
  query = "INSERT into config(" + ", ".join(
      SQLITE_CONFIG_COLS) + " ) values ( " + ",".join(
          [" ? "] * len(SQLITE_CONFIG_COLS)) + ");"
  cur.execute(query, tuple(vals))
  cur.execute("select last_insert_rowid() as id;")
  res = cur.fetchall()
  cur.close()
  return res[0][0]


def get_config_sqlite(cnx, fds):
  """get the config id from the sqlite table matching the fds conditions"""
  vals = [fds[x] for x in SQLITE_CONFIG_COLS]
  conditions = ['{} = ?'.format(col) for col in SQLITE_CONFIG_COLS]
  query = 'SELECT id from config where ' + ' AND '.join(conditions) + ';'
  cur = cnx.cursor()
  cur.execute(query, tuple(vals))
  res = cur.fetchall()
  cur.close()
  if len(res) == 1:
    config_id = res[0][0]
  elif not res:
    config_id = insert_config_sqlite(cnx, fds)
  else:
    LOGGER.error('Found #duplicate configs: %u', len(res))
    LOGGER.error('Non unique config found, db corrupt')
    sys.exit(-1)
  return config_id


def get_sqlite_data(cnx, table_name, fds):
  """get the config id from the sqlite table matching the fds conditions"""
  conditions = []
  if fds:
    for key, val in fds.items():
      if isinstance(val, list):
        val = ','.join([str(item) for item in val])
        conditions.append('{} in ({})'.format(key, val))
      elif isinstance(val, int):
        conditions.append('{} = {}'.format(key, val))
      else:
        conditions.append('{} = \'{}\''.format(key, val))
  query = 'SELECT * from {}'.format(table_name)
  if conditions:
    query = query + ' where ' + ' AND '.join(conditions)
  query = query + ';'
  #LOGGER.info(query)
  cur = cnx.cursor()
  cur.execute(query)
  columns = [x[0] for x in cur.description]
  res = cur.fetchall()
  cur.close()

  return res, columns


def get_sqlite_table(cnx, table_name, include_id=False):
  """return the sqlite table """
  query = 'SELECT * from {} LIMIT 1'.format(table_name)
  cur = cnx.cursor()
  cur.execute(query)
  if include_id:
    columns = [x[0] for x in cur.description]
  else:
    columns = [x[0] for x in cur.description if x[0] != 'id']
  query = 'SELECT {} FROM {};'.format(','.join(columns), table_name)
  cur.execute(query)
  res = cur.fetchall()
  cur.close()
  return res, columns


def get_sqlite_row(cnx, table, tid):
  """return the config row for the given id"""
  query = 'SELECT * from {} where id={}'.format(table, tid)
  cur = cnx.cursor()
  cur.execute(query)
  res = cur.fetchall()
  row = res[0]
  columns = [x[0] for x in cur.description]
  return row, columns


def get_config_mysql(fds, cnx):
  """get the config id from the mysql table matching the fds conditions"""
  cols, vals = zip(*fds.items())
  # before inserting check if the entry already exists
  conditions = ['{} = %s'.format(col) for col in cols]
  query = 'SELECT id from config where config.valid = TRUE AND ' + ' AND '.join(
      conditions) + ';'
  cur = cnx.cursor()
  cur.execute(query, tuple(vals))
  res = cur.fetchall()
  cur.close()
  if len(res) > 1:
    config_id = res[0][0]
    fds_str = ', '.join(
        ['{}:{}'.format(key, value) for key, value in fds.items()])
    LOGGER.warning('Duplicate config: %s', fds_str)
    LOGGER.warning('Picking first config id=%u', (config_id))
  elif not res:
    fds_str = ', '.join(
        ['{}:{}'.format(key, value) for key, value in fds.items()])
    LOGGER.warning('Adding new config for: %s', fds_str)
    #NOTE: need to add driver class to analyze_parse_db
    #insert_config_v1(cnx, {}, fds) - needs to be reworked to support driver class
    config_id = get_config_mysql(fds, cnx)
  else:
    config_id = res[0][0]
  return config_id


def get_solver(sol, cnx):
  """get id for the solver name"""
  query = "SELECT id from solver where name = %s"
  cur = cnx.cursor()
  cur.execute(query, (sol,))
  res = cur.fetchall()
  if len(res) > 1:
    LOGGER.error('Duplicate entries in solver table for solver: %s', sol)
    sys.exit(-1)
  elif not res:
    LOGGER.error('Unknown Solver: %s', sol)
    sys.exit(-1)
  cur.close()
  return res[0][0]


def insert_solver_sqlite(cnx, slv):
  """insert solver into sqlite """

  config = slv['config']
  solver_id = slv['solver']
  params = slv['params']
  marker = "?"

  where_clause = " where config = {mk} and solver = {mk}".format(mk=marker)
  query = "select id from perf_db " + where_clause
  cur = cnx.cursor()
  cur.execute(query, (config, solver_id))
  res = cur.fetchall()
  cur.close()
  if not res:
    query = "insert into perf_db(config, solver, params) values \
    ({mk}, {mk}, {mk});".format(mk=marker)
    cur = cnx.cursor()
    cur.execute(query, (config, solver_id, params))
    cur.close()
  else:
    query = "update perf_db set params = {mk} ".format(mk=marker) + where_clause
    cur = cnx.cursor()
    cur.execute(query, (params, config, solver_id))
    cur.close()
  cnx.commit()


def parse_pdb_filename(fname):
  """parse filename of perfdb file"""
  fname = os.path.basename(fname)
  found = False
  for item in ARCH_NUM_CU_LIST:
    arch, num_cu = item.split('-')
    num_cu = int(num_cu)
    db_arch = '{}_{}'.format(arch, num_cu)
    if num_cu > 64:
      db_arch = '{}{:x}'.format(arch, num_cu)
    if db_arch in fname:
      found = True
      break

  if not found:
    LOGGER.error('Invalid perf db filename')
    sys.exit(-1)

  return (arch, num_cu)


def mysql_to_sqlite_cfg(in_perf_cfg):
  """convert values to represent sqlite config table"""
  perf_cfg = in_perf_cfg.copy()

  if perf_cfg['direction'] in ('B', 'W'):
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


def sqlite_to_mysql_cfg(in_perf_cfg):
  """convert values to represent mysql config table"""
  perf_cfg = in_perf_cfg.copy()

  if perf_cfg['direction'] in ('B', 'W'):
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
