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
"""Module to export find_db to txt file"""
import sqlite3
import os
from collections import OrderedDict, namedtuple
import base64
from sqlalchemy import and_

from tuna.dbBase.sql_alchemy import DbSession
from tuna.miopen_tables import Solver  # pylint: disable=unused-import
from tuna.tables import DBTables
from tuna.metadata import SQLITE_PERF_DB_COLS
from tuna.utils.db_utility import get_id_solvers, DB_Type
from tuna.utils.logger import setup_logger
from tuna.parse_args import TunaArgs, setup_arg_parser
from tuna.analyze_parse_db import get_config_sqlite, insert_solver_sqlite, mysql_to_sqlite_cfg
from tuna.fin_utils import compose_config_obj

DIR_NAME = {'F': 'Fwd', 'B': 'BwdData', 'W': 'BwdWeights'}

# Setup logging
LOGGER = setup_logger('export_db')


def parse_args():
  """Function to parse arguments"""
  parser = setup_arg_parser('Convert MYSQL find_db to text find_dbs' \
    'architecture', [TunaArgs.ARCH, TunaArgs.NUM_CU, TunaArgs.VERSION])
  parser.add_argument('-c',
                      '--opencl',
                      dest='opencl',
                      action='store_true',
                      help='Use OpenCL extension',
                      default=False)
  parser.add_argument(
      '--session_id',
      action='store',
      type=int,
      dest='session_id',
      help=
      'Session ID to be used as tuning tracker. Allows to correlate DB results to tuning sessions'
  )
  parser.add_argument('--config_tag',
                      dest='config_tag',
                      type=str,
                      help='import configs based on config tag',
                      default=None)
  parser.add_argument('--filename',
                      dest='filename',
                      help='Custom filename for DB dump',
                      default=None)
  group = parser.add_mutually_exclusive_group(required=True)
  group.add_argument('-k',
                     '--kern_db',
                     dest='kern_db',
                     action='store_true',
                     help='Serialize Kernel Database',
                     default=False)
  group.add_argument('-f',
                     '--find_db',
                     dest='find_db',
                     action='store_true',
                     help='Serialize Find Database',
                     default=False)
  group.add_argument('-p',
                     '--perf_db',
                     dest='perf_db',
                     action='store_true',
                     help='Serialize Perf Database',
                     default=False)
  args = parser.parse_args()

  return args


def fdb_query(dbt, args):
  """ Helper function to create find db query
  """
  find_db_table = dbt.find_db_table
  config_tags_table = dbt.config_tags_table
  solver_app = dbt.solver_app
  with DbSession() as session:
    query = session.query(find_db_table, solver_app).filter(
        and_(find_db_table.session == dbt.session.id,
             solver_app.session == dbt.session.id,
             find_db_table.kernel_time != -1, find_db_table.workspace_sz != -1,
             find_db_table.opencl == args.opencl, find_db_table.valid == 1))\
             .filter(find_db_table.solver == solver_app.solver,
                     find_db_table.config == solver_app.config)\
             .order_by(find_db_table.config, find_db_table.update_ts.desc())

    LOGGER.info("Collecting %s entries.", find_db_table.__tablename__)
    query = query.filter(solver_app.applicable == 1)
    LOGGER.info("rocm_v : %s", dbt.session.rocm_v)
    LOGGER.info("miopen_v : %s", dbt.session.miopen_v)
    if args.config_tag:
      LOGGER.info("config_tag : %s", args.config_tag)
      tag_query = session.query(config_tags_table.config).filter(
          config_tags_table.tag == args.config_tag)
      tag_rows = tag_query.all()
      ids = tuple([str(tag_row.config) for tag_row in tag_rows])
      query = query.filter(find_db_table.config.in_(ids))

  return query


def write_kdb(arch, num_cu, kern_db, filename=None):
  """
  Write blob map to sqlite
  """
  file_name = get_filename(arch, num_cu, filename, None, DB_Type.KERN_DB)
  if os.path.isfile(file_name):
    os.remove(file_name)

  conn = sqlite3.connect(file_name)
  cur = conn.cursor()
  cur.execute(
      "CREATE TABLE `kern_db` (`id` INTEGER PRIMARY KEY ASC,`kernel_name` TEXT NOT NULL,"
      "`kernel_args` TEXT NOT NULL,`kernel_blob` BLOB NOT NULL,`kernel_hash` TEXT NOT NULL,"
      "`uncompressed_size` INT NOT NULL);")
  cur.execute(
      "CREATE UNIQUE INDEX `idx_kern_db` ON kern_db(kernel_name, kernel_args);")
  for (name, args), (blob, kern_hash, kern_size) in kern_db.items():
    cur.execute(
        "INSERT INTO kern_db (kernel_name, kernel_args, kernel_blob, kernel_hash, "
        "uncompressed_size) VALUES(?, ?, ?, ?, ?);",
        (name, args, base64.b64decode(blob), kern_hash, kern_size))
  conn.commit()
  cur.close()
  conn.close()
  return file_name


def build_miopen_kdb(find_db):
  """ create miopen kernel db object for export
  """
  num_fdb_entries = 0
  num_kdb_blobs = 0
  kern_db = OrderedDict()
  for _, fdb_row in find_db.items():
    fastest_time = float("inf")
    fastest_entry = None
    num_fdb_entries += 1
    for kinder in fdb_row:
      if kinder.kernel_time < fastest_time:
        fastest_time = kinder.kernel_time
        fastest_entry = kinder
    for blob in fastest_entry.blobs:
      key = (blob.kernel_name, blob.kernel_args)
      kinder = kern_db.get(key)
      if kinder:
        continue
      num_kdb_blobs += 1
      kern_db[key] = (blob.kernel_blob, blob.kernel_hash,
                      blob.uncompressed_size)

  LOGGER.warning("Total number of FDB entries: %s", num_fdb_entries)
  LOGGER.warning("Total number of blobs: %s", num_kdb_blobs)
  return kern_db


def export_kdb(dbt, args):
  """
  Function to export the kernel cache
  """
  query = fdb_query(dbt, args)

  find_db = OrderedDict()
  solvers = {}
  for fdb_entry, _ in query.all():
    fdb_key = fdb_entry.fdb_key
    if fdb_key not in solvers:
      solvers[fdb_key] = {}
    #skip if there is a solver for this key
    if fdb_entry.solver in solvers[fdb_key].keys():
      #LOGGER.warning("skipped duplicate solver: %s : %s : %s vs stored: %s", fdb_key,
      #               fdb_entry.solver, fdb_entry.update_ts,
      #               solvers[fdb_key][fdb_entry.solver])
      continue
    #record found solver for key
    solvers[fdb_key][fdb_entry.solver] = fdb_entry.update_ts
    lst = find_db.get(fdb_key)
    if not lst:
      find_db[fdb_key] = [fdb_entry]
    else:
      lst.append(fdb_entry)

  LOGGER.info("Building kdb.")
  kern_db = build_miopen_kdb(find_db)

  LOGGER.info("write kdb to file.")
  return write_kdb(args.arch, args.num_cu, kern_db, args.filename)


def get_filename(arch, num_cu, filename, ocl, db_type):
  """Helper function to compose filename"""
  version = "1.0.0"
  tuna_dir = 'tuna_{}'.format(version)
  if not os.path.exists(tuna_dir):
    os.makedirs(tuna_dir)
  final_name = "{}/{}_{}".format(tuna_dir, arch, num_cu)
  if num_cu > 64:
    final_name = '{}/{}{:x}'.format(tuna_dir, arch, num_cu)
  if filename:
    final_name = '{}/{}'.format(tuna_dir, filename)

  if db_type == DB_Type.FIND_DB:
    extension = '.{}.fdb.txt'.format('OpenCL' if ocl else 'HIP')
  elif db_type == DB_Type.KERN_DB:
    extension = '.kdb'
  else:
    extension = ".db"

  final_name = "{}{}".format(final_name, extension)

  return final_name


def write_fdb(arch, num_cu, ocl, find_db, filename=None):
  """
  Serialize find_db map to plain text file in MIOpen format
  """
  _, id_solver_map_h = get_id_solvers()
  file_name = get_filename(arch, num_cu, filename, ocl, DB_Type.FIND_DB)
  FDBRecord = namedtuple('FDBRecord',
                         'alg_lib solver_id kernel_time workspace_sz')

  with open(file_name, 'w') as out:
    for key, solvers in sorted(find_db.items(), key=lambda kv: kv[0]):
      solvers.sort(key=lambda x: float(x[2]))
      lst = []
      # for alg_lib, solver_id, kernel_time, workspace_sz in solvers:
      for rec in solvers:
        rec = FDBRecord(*rec)
        lst.append('{alg}:{},{},{},{alg},{}'.format(
            id_solver_map_h[rec.solver_id],
            rec.kernel_time,
            rec.workspace_sz,
            'not used',
            alg=rec.alg_lib))
      out.write('{}={}\n'.format(key, ';'.join(lst)))
  return file_name


def build_miopen_fdb(find_key_alg_lists):
  """ create miopen find db object for export
  """
  num_fdb_entries = 0
  miopen_fdb = OrderedDict()
  for fdb_key_alg, items in find_key_alg_lists.items():
    fdb_key = fdb_key_alg[0]
    num_fdb_entries += 1
    #pick fastest solver for each algorithm
    items.sort(key=lambda x: float(x[2]))
    fastest_entry = items[0]
    lst = miopen_fdb.get(fdb_key)
    if not lst:
      miopen_fdb[fdb_key] = [fastest_entry]
    else:
      lst.append(fastest_entry)

  LOGGER.warning("Total number of entries in Find DB: %s", num_fdb_entries)

  return miopen_fdb


def get_find_key_alg_lists(query):
  """Function to compose find_db entries"""
  find_db = OrderedDict()
  solvers = {}
  for fdb_entry, _ in query.all():
    fdb_key = fdb_entry.fdb_key
    if fdb_key not in solvers:
      solvers[fdb_key] = {}
    if fdb_entry.solver in solvers[fdb_key].keys():
      #LOGGER.warning("skipped duplicate solver: %s : %s : %s vs stored: %s", fdb_key,
      #               fdb_entry.solver, fdb_entry.update_ts, solvers[fdb_key][fdb_entry.solver])
      continue
    solvers[fdb_key][fdb_entry.solver] = fdb_entry.update_ts

    new_entry = (fdb_entry.alg_lib, fdb_entry.solver, fdb_entry.kernel_time,
                 fdb_entry.workspace_sz)
    fdb_key_alg = (fdb_entry.fdb_key, fdb_entry.alg_lib)
    lst = find_db.get(fdb_key_alg)
    if not lst:
      find_db[fdb_key_alg] = [new_entry]
    else:
      lst.append(new_entry)

  return find_db


def export_fdb(dbt, args):
  """Function to export find_db to txt file
  """
  query = fdb_query(dbt, args)
  find_key_alg_lists = get_find_key_alg_lists(query)
  miopen_fdb = build_miopen_fdb(find_key_alg_lists)

  return write_fdb(args.arch, args.num_cu, args.opencl, miopen_fdb,
                   args.filename)


def create_sqlite_tables(arch, num_cu, filename=None):
  """create sqlite3 tables"""
  local_path = get_filename(arch, num_cu, filename, None, DB_Type.PERF_DB)

  cnx = sqlite3.connect(local_path)

  cur = cnx.cursor()
  cur.execute(
      "CREATE TABLE IF NOT EXISTS `config` (`id` INTEGER PRIMARY KEY ASC,`layout` TEXT NOT NULL,"
      "`data_type` TEXT NOT NULL,`direction` TEXT NOT NULL,`spatial_dim` INT NOT NULL,"
      "`in_channels` INT NOT NULL,`in_h` INT NOT NULL,`in_w` INT NOT NULL,`in_d` INT NOT NULL,"
      "`fil_h` INT NOT NULL,`fil_w` INT NOT NULL,`fil_d` INT NOT NULL,"
      "`out_channels` INT NOT NULL, `batchsize` INT NOT NULL,"
      "`pad_h` INT NOT NULL,`pad_w` INT NOT NULL,`pad_d` INT NOT NULL,"
      "`conv_stride_h` INT NOT NULL,`conv_stride_w` INT NOT NULL,`conv_stride_d` INT NOT NULL,"
      "`dilation_h` INT NOT NULL,`dilation_w` INT NOT NULL,`dilation_d` INT NOT NULL,"
      "`bias` INT NOT NULL,`group_count` INT NOT NULL)")
  cur.execute(
      "CREATE TABLE IF NOT EXISTS `perf_db` (`id` INTEGER PRIMARY KEY ASC,`solver` TEXT NOT NULL,"
      "`config` INTEGER NOT NULL, `params` TEXT NOT NULL)")

  cur.execute(
      "CREATE UNIQUE INDEX IF NOT EXISTS `idx_config` ON config( layout,data_type,direction,"
      "spatial_dim,in_channels,in_h,in_w,in_d,fil_h,fil_w,fil_d,out_channels,"
      "batchsize,pad_h,pad_w,pad_d,conv_stride_h,conv_stride_w,conv_stride_d,"
      "dilation_h,dilation_w,dilation_d,bias,group_count )")
  cur.execute(
      "CREATE UNIQUE INDEX IF NOT EXISTS `idx_perf_db` ON perf_db(solver, config)"
  )

  cur.close()
  cnx.commit()
  return cnx, local_path


def get_cfg_dict(cfg_entry, perf_cfg_entry):
  """compose config_dict"""
  cfg_dict = compose_config_obj(cfg_entry)
  cfg_dict.update(perf_cfg_entry.to_dict())

  if cfg_entry.valid == 1:
    cfg_dict = mysql_to_sqlite_cfg(cfg_dict)

  return dict(cfg_dict)


def insert_perf_db_sqlite(session, cnx, perf_db_entry, ins_cfg_id):
  """insert perf_db entry into sqlite"""
  perf_db_dict = perf_db_entry.to_dict()
  perf_db_dict['config'] = ins_cfg_id
  perf_db_dict = {
      k: v for k, v in perf_db_dict.items() if k in SQLITE_PERF_DB_COLS
  }
  query = session.query(Solver).filter(Solver.id == perf_db_dict['solver'])
  perf_db_dict['solver'] = query.one().solver

  insert_solver_sqlite(cnx, perf_db_dict)
  LOGGER.info("Inserting row in perf_db: %s", perf_db_dict)


def get_query(dbt, args):
  """Compose query to get perf_db rows based on filters from args"""
  with DbSession() as session:
    query = session.query(dbt.perf_db_table, dbt.perf_config_table,
                          dbt.config_table)\
        .filter(dbt.perf_db_table.valid == 1)\
        .filter(dbt.perf_db_table.session == dbt.session.id)\
        .filter(dbt.perf_db_table.miopen_config == dbt.perf_config_table.id)\
        .filter(dbt.perf_config_table.config == dbt.config_table.id)

    LOGGER.info("rocm_v : %s", dbt.session.rocm_v)
    LOGGER.info("miopen_v : %s", dbt.session.miopen_v)
    query = query.filter(dbt.perf_db_table.session == dbt.session.id)
    if args.config_tag:
      LOGGER.info("config_tag : %s", args.config_tag)
      tag_query = session.query(dbt.config_tags_table.config).filter(
          dbt.config_tags_table.tag == args.config_tag)
      ids = tuple([str(tag_row.config) for tag_row in tag_query.all()])
      query = query.filter(dbt.perf_config_table.config.in_(ids))

  return query


def export_pdb(dbt, args):
  """ export perf db from mysql to sqlite """
  cnx, local_path = create_sqlite_tables(args.arch, args.num_cu, args.filename)
  num_perf = 0
  with DbSession() as session:
    query = get_query(dbt, args)
    cfg_map = {}
    for perf_db_entry, perf_cfg_entry, cfg_entry in query.all():
      LOGGER.info("%s, %s, %s", dbt.session.miopen_v, dbt.session.rocm_v,
                  perf_db_entry.miopen_config)

      if perf_cfg_entry.id in cfg_map:
        ins_cfg_id = cfg_map[perf_cfg_entry.id]
      else:
        cfg_dict = get_cfg_dict(cfg_entry, perf_cfg_entry)
        #filters cfg_dict by SQLITE_CONFIG_COLS, inserts cfg if missing
        ins_cfg_id = get_config_sqlite(cnx, cfg_dict)
        cfg_map[perf_cfg_entry.id] = ins_cfg_id

      insert_perf_db_sqlite(session, cnx, perf_db_entry, ins_cfg_id)
      num_perf += 1

  LOGGER.warning("Total number of entries in perf_db: %s", num_perf)

  return local_path


def main():
  """Main module function"""
  args = parse_args()
  result_file = ''
  dbt = DBTables(session_id=args.session_id)

  if args.kern_db:
    result_file = export_kdb(dbt, args)
  elif args.find_db:
    result_file = export_fdb(dbt, args)
  elif args.perf_db:
    result_file = export_pdb(dbt, args)

  print(result_file)


if __name__ == '__main__':
  main()
