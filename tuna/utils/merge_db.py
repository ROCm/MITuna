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
import argparse
import sqlite3
from shutil import copyfile

from tuna.parsing import parse_pdb_key, build_driver_cmd
from tuna.utils.logger import setup_logger
from tuna.analyze_parse_db import parse_pdb_filename, insert_solver_sqlite, get_config_sqlite
from tuna.analyze_parse_db import get_sqlite_row, get_sqlite_table, get_sqlite_data
from tuna.helper import prune_cfg_dims
from tuna.metadata import DIR_MAP

LOGGER = setup_logger('merge_pdb')

DB_ALIAS = {'gfx803_36': 'gfx900_64', 'gfx803_64': 'gfx900_64'}


def parse_jobline(line):
  """get entries from a fdb text line """
  # line = line.decode()
  line = line.strip()
  tmp = line.split('=')
  assert len(tmp) == 2
  lhs, rhs = tmp
  vals = rhs.split(';')
  params = {}
  for val in vals:
    solver_id, p_vec = val.split(':')
    params[solver_id] = p_vec
  return lhs, params


def parse_args():
  """command line parsing"""
  parser = argparse.ArgumentParser(
      description='Merge Performance DBs once tunning is finished')
  parser.add_argument(
      '-m',
      '--master_file',
      type=str,
      dest='master_file',
      required=True,
      help=
      'Master perf db from previous runs. May be a specific pdb, fdb, or sqlite db file. \
      If a directory is entered, will gather all pdb / fdb files depending on -f option.'
  )
  parser.add_argument(
      '-t',
      '--target_file',
      type=str,
      default=None,
      dest='target_file',
      required=True,
      help='Supply an absolute path to the file. This file will be merged.')

  op_type = parser.add_mutually_exclusive_group()
  op_type.add_argument('-p',
                       '--perf_db',
                       dest='perf_db',
                       action='store_true',
                       default=False,
                       help='Process perf db')
  op_type.add_argument('-f',
                       '--find_db',
                       dest='find_db',
                       action='store_true',
                       default=False,
                       help='Process find db')
  op_type.add_argument('-b',
                       '--bin_cache',
                       dest='bin_cache',
                       action='store_true',
                       default=False,
                       help='Process binary cache (kernel db)')

  parser.add_argument('-c',
                      '--check_duplicate',
                      dest='check_duplicate',
                      action='store_true',
                      default=False,
                      help='Check for duplicate entries in perf db files')
  parser.add_argument(
      '-o',
      '--copy_only',
      dest='copy_only',
      action='store_true',
      default=False,
      help='Only copy out the remote configs to the master node and dont process'
  )
  parser.add_argument(
      '--keep_keys',
      dest='keep_keys',
      action='store_true',
      default=False,
      help=
      'Keep partial entries from find db. Keeps algorithms that are not explicitly replaced.'
  )

  args = parser.parse_args()

  if not (args.perf_db or args.find_db or args.bin_cache):
    parser.error('Must specify one of perf_db, find_db, or bin_cache')

  return args


def parse_text_fdb_name(master_file):
  """parse out the find db filename, list remote files, create destination file """
  find_db_name = os.path.basename(master_file)
  lst = find_db_name.split('.')
  assert len(lst) == 4
  assert lst[2] == 'fdb'
  assert lst[3] == 'txt'
  backend = lst[1]
  if '_' in lst[0]:
    arch, num_cu = lst[0].split('_')
    final_file = f'{os.getcwd()}/{arch}_{num_cu}.{backend}.fdb.txt'
  elif 'gfx' in lst[0]:
    arch = lst[0][0:6]
    num_cu = int(lst[0][6:], 16)
    final_file = f'{os.getcwd()}/{lst[0]}.{backend}.fdb.txt'

  copy_files = []

  targ = f'{arch}_{num_cu}'
  if targ in DB_ALIAS.values():
    setups = [key for key, val in DB_ALIAS.items() if val == targ]
    for setup in setups:
      file = f'{setup}.{backend}.fdb.txt'
      copy_files.append(file)

  return arch, num_cu, final_file, copy_files


def parse_text_pdb_name(master_file):
  """parse out the perf db filename, list remote files, create destination file """
  (arch, num_cu) = parse_pdb_filename(master_file)
  final_file = f'{os.getcwd()}/{arch}_{num_cu}.cd.pdb.txt'
  copy_files = []

  targ = f'{arch}_{num_cu}'
  if targ in DB_ALIAS.values():
    setups = [key for key, val in DB_ALIAS.items() if val == targ]
    for setup in setups:
      file = f'{setup}.cd.pdb.txt'
      copy_files.append(file)

  return arch, num_cu, final_file, copy_files


def load_master_list(master_file):
  """load db entries from the master file into a dict"""
  master_list = {}
  if master_file is not None:
    LOGGER.info('Loading master file: %s', master_file)
    cnt = 0
    with open(master_file) as master_fp:  # pylint: disable=unspecified-encoding
      for line in master_fp:
        key, vals = parse_jobline(line)
        master_list[key] = vals
        cnt += 1
    LOGGER.info('Master file loading complete with %u lines', cnt)
    LOGGER.info('Master file has %u unique entries', len(master_list))

  return master_list


def best_solver(vals):
  """returns the fastest solver"""
  min_time = float("inf")
  b_solver = None
  for val in vals.values():
    solver, time, _, _, _ = val.split(',')
    if float(time) < min_time:
      min_time = float(time)
      b_solver = solver

  return b_solver, min_time


def target_merge(master_list, key, vals, keep_keys):
  """merge for explicit target file"""
  #Error handling of Ivalid input parameter types
  if not (vals and isinstance(vals, dict)):
    raise ValueError(f'Invalid vals: {vals}')
  if not (key and isinstance(key, str) and key.strip()):
    raise ValueError(f'Invalid key value: {key}')
  if not (master_list and isinstance(master_list, dict)):
    raise ValueError(f'Invalid master_list: {master_list}')

  fds, fds_val, precision, direction = parse_pdb_key(key)
  driver_cmd = build_driver_cmd(fds, fds_val, precision, DIR_MAP[direction])
  if key not in master_list:
    LOGGER.info('%s: Missing Key \n %s', key, driver_cmd)
    master_list[key] = {}
  else:
    old_solver, old_time = best_solver(master_list[key])
    new_solver, new_time = best_solver(vals)

    LOGGER.info(
        '%s: solver_change: %s, speedup: %s, Old Solver: (%s, %s), New Solver: (%s, %s) \n %s',
        key, old_solver != new_solver,
        float(new_time) < float(old_time), old_solver, old_time, new_solver,
        new_time, driver_cmd)

  if keep_keys:
    #keep old key values
    for alg, param in vals.items():
      master_list[key][alg] = param
  else:
    #don't keep old key values
    master_list[key] = vals


def update_master_list(master_list, local_paths, mids, keep_keys):
  """merge data in master_list with values from the file at local_path"""
  for local_path, machine_id in zip(local_paths, mids):
    with open(local_path) as local_file:  # pylint: disable=unspecified-encoding
      LOGGER.info('Processing file: %s', local_path)
      # read the file get rid of the duplicates by keeping the first entry
      for line in local_file:
        key, vals = parse_jobline(line)
        if machine_id < 0:
          #a file was selected explicitly to merge mid = -1
          target_merge(master_list, key, vals, keep_keys)


def write_merge_results(master_list, final_file, copy_files):
  """write merge results to file"""
  # serialize the file out
  LOGGER.info('Begin writing to file: %s', final_file)
  with open(final_file, "w") as out_file:  # pylint: disable=unspecified-encoding
    for perfdb_key, solvers in sorted(master_list.items(),
                                      key=lambda kv: kv[0]):
      params = []
      for solver_id, solver_params in sorted(
          solvers.items(), key=lambda kv: (float(kv[1].split(',')[1]), kv[0])):
        params.append(f'{solver_id}:{solver_params}')
      # pylint: disable-next=consider-using-f-string ; more readble
      perf_line = '{}={}'.format(perfdb_key, ';'.join(params))
      out_file.write(perf_line + '\n')
  LOGGER.info('Finished writing to file: %s', final_file)

  for copy in copy_files:
    copyfile(final_file, copy)
    LOGGER.info('Finished writing to file: %s', copy)


def merge_text_file(master_file, copy_only, keep_keys, target_file=None):
  """merge db text files"""
  if not (target_file and isinstance(target_file, str) and target_file.strip()):
    raise ValueError(f'Invalid target_file: {target_file}')

  if master_file.endswith('.fdb.txt'):
    _, _, final_file, copy_files = parse_text_fdb_name(master_file)
  else:
    _, _, final_file, copy_files = parse_text_pdb_name(master_file)

  master_list = load_master_list(master_file)

  local_paths = [target_file]
  mids = [-1]

  if copy_only:
    LOGGER.warning('Skipping file processing due to copy_only argument')
    return None

  update_master_list(master_list, local_paths, mids, keep_keys)

  write_merge_results(master_list, final_file, copy_files)

  return final_file


def merge_sqlite_pdb(cnx_to, local_paths):  # pylint: disable=too-many-locals
  """sqlite merge for perf db"""
  for local_path in local_paths:
    LOGGER.info('Processing file: %s', local_path)

    cnx_from = sqlite3.connect(local_path)
    perf_rows, perf_cols = get_sqlite_table(cnx_from, 'perf_db')
    for row in perf_rows:
      perf = dict(zip(perf_cols, row))
      cfg_row, cfg_cols = get_sqlite_row(cnx_from, 'config', perf['config'])
      cfg = dict(zip(cfg_cols, cfg_row))
      cfg.pop('id', None)

      res, col = get_sqlite_data(cnx_to, 'config', prune_cfg_dims(cfg))
      if res:
        cfg = dict(zip(col, res[0]))
        if len(res) > 1:
          LOGGER.warning("DUPLICATE CONFIG:%s", res)
          dupe_ids = [dict(zip(col, row))['id'] for row in res]
          dupe_ids.sort()
          list_id = ','.join([str(item) for item in dupe_ids[1:]])
          query = f"delete from perf_db where config in ({list_id});"
          LOGGER.warning("query: %s", query)
          cur = cnx_to.cursor()
          cur.execute(query)
          cnx_to.commit()
          cfg['id'] = dupe_ids[0]

        cfg_id = cfg['id']
      else:
        cfg_id = get_config_sqlite(cnx_to, cfg)

      perf['config'] = cfg_id
      LOGGER.info("insert: %s", perf)
      insert_solver_sqlite(cnx_to, perf)

    cnx_to.commit()
    cnx_from.close()

  cur = cnx_to.cursor()
  query = "delete from config where not id in (select distinct config from perf_db);"
  LOGGER.info("query: %s", query)
  cur.execute(query)
  cnx_to.commit()
  cur.execute("VACUUM;")
  cnx_to.commit()
  cur.close()


def merge_sqlite_bin_cache(cnx_to, local_paths):
  """sqlite merge for binary cache"""
  dup_count = 0
  for local_path in local_paths:
    LOGGER.info('Processing file: %s', local_path)
    cnx_from = sqlite3.connect(local_path)

    db_rows, db_cols = get_sqlite_table(cnx_from, 'kern_db', include_id=False)
    cur_to = cnx_to.cursor()
    # pylint: disable-next=consider-using-f-string ; more readable
    query = "INSERT INTO `kern_db`({}) VALUES({})".format(
        ','.join(db_cols), ','.join(['?'] * len(db_cols)))
    for row in db_rows:
      try:
        cur_to.execute(query, tuple(row))
      except sqlite3.IntegrityError:
        dup_count += 1
        # pylint: disable=consider-using-f-string ; more readable
        cur_to.execute(
            "INSERT OR REPLACE INTO `kern_db`({}) VALUES({})".format(
                ','.join(db_cols), ','.join(['?'] * len(db_cols))), tuple(row))
        # pylint: enable=consider-using-f-string
    cnx_to.commit()
    cur_to.close()
    LOGGER.warning('Duplicate Count: %d', dup_count)


def merge_sqlite(master_file, copy_only, target_file=None):
  """merge db sqlite files"""
  LOGGER.info('SQL db')
  bin_cache = False

  db_name = os.path.basename(master_file)
  arch_cu = db_name.split('.')[0]
  if 'kdb' in master_file:
    final_file = f'{os.getcwd()}/{arch_cu}.kdb'
    bin_cache = True
  else:
    final_file = f'{os.getcwd()}/{arch_cu}.db'

  LOGGER.info('Destination file: %s', final_file)

  local_paths = [os.path.abspath(os.path.expanduser(target_file))]

  if copy_only:
    LOGGER.warning('Skipping file processing due to copy_only argument')
    return None

  if not final_file == master_file:
    copyfile(master_file, final_file)

  cnx_to = sqlite3.connect(final_file)
  if bin_cache:
    merge_sqlite_bin_cache(cnx_to, local_paths)
  else:
    merge_sqlite_pdb(cnx_to, local_paths)

  cnx_to.close()

  return final_file


def merge_files(master_file, copy_only, keep_keys, target_file=None):
  """merge file selector text/sqlite base"""
  basename = os.path.basename(master_file)
  LOGGER.info('basename: %s', basename)

  if basename.endswith('.db') or 'kdb' in basename:
    final_file = merge_sqlite(master_file, copy_only, target_file)
  else:
    final_file = merge_text_file(master_file, copy_only, keep_keys, target_file)

  return final_file


def get_file_list(args):
  """get relevant files in a directory"""
  files = []
  if os.path.isdir(args.master_file):
    all_files = os.listdir(args.master_file)
    for name in all_files:
      if not name.startswith('gfx'):
        continue
      if args.find_db:
        if not name.endswith('.fdb.txt'):
          continue
      elif args.bin_cache:
        if not 'kdb' in name:
          continue
      else:  #perf_db
        if not name.endswith('.db'):
          continue
      lst = name.split('.')
      if lst[0] in DB_ALIAS:
        continue
      name = os.path.join(args.master_file, name)
      files.append(name)
  else:
    files = [args.master_file]

  LOGGER.info('file list: %s', files)
  return files


def main():
  """main"""
  args = parse_args()
  for master_file in get_file_list(args):
    merge_files(master_file, args.copy_only, args.keep_keys, args.target_file)


if __name__ == '__main__':
  main()
