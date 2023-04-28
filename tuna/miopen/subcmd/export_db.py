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
from collections import OrderedDict
import base64
import argparse
import logging

from tuna.dbBase.sql_alchemy import DbSession
from tuna.miopen.db.tables import MIOpenDBTables
from tuna.miopen.utils.metadata import SQLITE_PERF_DB_COLS
from tuna.utils.db_utility import get_id_solvers, DB_Type
from tuna.utils.utility import arch2targetid
from tuna.utils.logger import setup_logger
from tuna.miopen.utils.analyze_parse_db import get_config_sqlite, insert_solver_sqlite
from tuna.miopen.utils.analyze_parse_db import mysql_to_sqlite_cfg
from tuna.miopen.utils.parsing import parse_pdb_key
from tuna.miopen.worker.fin_utils import compose_config_obj
from tuna.miopen.parse_miopen_args import get_export_db_parser

DIR_NAME = {'F': 'Fwd', 'B': 'BwdData', 'W': 'BwdWeights'}

_, ID_SOLVER_MAP = get_id_solvers()


def arg_export_db(args: argparse.Namespace, logger: logging.Logger):
  """export db args for exportdb"""
  if args.golden_v and not (args.arch and args.num_cu):
    logger.error('arch and num_cu must be set with golden_v')


def get_filename(arch, num_cu, filename, ocl, db_type):
  """Helper function to compose filename"""
  version = "1.0.0"
  tuna_dir = f'tuna_{version}'
  if not os.path.exists(tuna_dir):
    os.makedirs(tuna_dir)
  final_name = f"{tuna_dir}/{arch}_{num_cu}"
  if num_cu > 64:
    final_name = f'{tuna_dir}/{arch}{num_cu:x}'
  if filename:
    final_name = f'{tuna_dir}/{filename}'

  if db_type == DB_Type.FIND_DB:
    # pylint: disable-next=consider-using-f-string ; more readable
    extension = '.{}.fdb.txt'.format('OpenCL' if ocl else 'HIP')
  elif db_type == DB_Type.KERN_DB:
    extension = '.kdb'
  else:
    extension = ".db"

  final_name = f"{final_name}{extension}"

  return final_name


def get_base_query(dbt: MIOpenDBTables, args: argparse.Namespace,
                   logger: logging.Logger):
  """ general query for fdb/pdb results """
  src_table = dbt.find_db_table
  if args.golden_v is not None:
    src_table = dbt.golden_table

  with DbSession() as session:
    query = session.query(src_table, dbt.config_table)
    if args.golden_v is not None:
      query = query.filter(src_table.golden_miopen_v == args.golden_v)\
              .filter(src_table.arch == args.arch)\
              .filter(src_table.num_cu == args.num_cu)
      logger.info("golden_miopen_v: %s, arch: %s, num_cu: %s", args.golden_v,
                  args.arch, args.num_cu)
    else:
      query = query.filter(src_table.session == dbt.session.id)
      logger.info("rocm_v : %s", dbt.session.rocm_v)
      logger.info("miopen_v : %s", dbt.session.miopen_v)

    query = query.filter(src_table.valid == 1)\
        .filter(src_table.opencl == args.opencl)\
        .filter(src_table.config == dbt.config_table.id)

    if args.config_tag:
      logger.info("config_tag : %s", args.config_tag)
      query = query.filter(dbt.config_tags_table.tag == args.config_tag)\
          .filter(dbt.config_table.config == dbt.config_table.id)

  return query


def get_fdb_query(dbt: MIOpenDBTables, args: argparse.Namespace,
                  logger: logging.Logger):
  """ Helper function to create find db query
  """
  src_table = dbt.find_db_table
  if args.golden_v is not None:
    src_table = dbt.golden_table

  query = get_base_query(dbt, args, logger)
  query = query.filter(src_table.kernel_time != -1)\
      .filter(src_table.workspace_sz != -1)

  query = query.order_by(src_table.fdb_key, src_table.update_ts.desc())

  return query


def get_pdb_query(dbt: MIOpenDBTables, args: argparse.Namespace,
                  logger: logging.Logger):
  """Compose query to get perf_db rows based on filters from args"""
  src_table = dbt.find_db_table
  if args.golden_v is not None:
    src_table = dbt.golden_table

  query = get_base_query(dbt, args, logger)
  query = query.filter(src_table.params != '')\
      .filter(src_table.solver == dbt.solver_table.id)\
      .filter(dbt.solver_table.tunable == 1)

  return query


def get_fdb_alg_lists(query, logger: logging.Logger):
  """return dict with key: fdb_key + alg_lib, val: solver list"""
  find_db = OrderedDict()
  solvers = {}
  db_entries = query.all()
  total_entries = len(db_entries)
  logger.info("fdb query returned: %s", total_entries)

  for fdb_entry, _ in db_entries:
    fdb_key = fdb_entry.fdb_key
    if fdb_key not in solvers:
      solvers[fdb_key] = {}
    if fdb_entry.solver in solvers[fdb_key].keys():
      logger.warning("Skipped duplicate solver: %s : %s with ts %s vs prev %s",
                     fdb_key, fdb_entry.solver, fdb_entry.update_ts,
                     solvers[fdb_key][fdb_entry.solver])
      continue
    solvers[fdb_key][fdb_entry.solver] = fdb_entry.update_ts

    fdb_key_alg = (fdb_entry.fdb_key, fdb_entry.alg_lib)
    lst = find_db.get(fdb_key_alg)
    if not lst:
      find_db[fdb_key_alg] = [fdb_entry]
    else:
      lst.append(fdb_entry)

  return find_db


def build_miopen_fdb(fdb_alg_lists, logger: logging.Logger):
  """ create miopen find db object for export
  """
  total_entries = len(fdb_alg_lists)
  num_fdb_entries = 0
  miopen_fdb = OrderedDict()
  for fdbkey_alg, alg_entries in fdb_alg_lists.items():
    fdb_key = fdbkey_alg[0]
    num_fdb_entries += 1
    #pick fastest solver for each algorithm
    alg_entries.sort(key=lambda x: float(x.kernel_time))
    fastest_entry = alg_entries[0]
    lst = miopen_fdb.get(fdb_key)
    if not lst:
      miopen_fdb[fdb_key] = [fastest_entry]
    else:
      lst.append(fastest_entry)

    if num_fdb_entries % (total_entries // 10) == 0:
      logger.info("FDB count: %s, fdb: %s, cfg: %s, slv: %s", num_fdb_entries,
                  fastest_entry.fdb_key, fastest_entry.config,
                  ID_SOLVER_MAP[fastest_entry.solver])

  logger.warning("Total number of entries in Find DB: %s", num_fdb_entries)

  return miopen_fdb


def write_fdb(arch, num_cu, ocl, find_db, filename=None):
  """
  Serialize find_db map to plain text file in MIOpen format
  """
  file_name = get_filename(arch, num_cu, filename, ocl, DB_Type.FIND_DB)

  with open(file_name, 'w') as out:  # pylint: disable=unspecified-encoding
    for key, solvers in sorted(find_db.items(), key=lambda kv: kv[0]):
      solvers.sort(key=lambda x: (float(x.kernel_time), x.alg_lib))
      lst = []
      # for alg_lib, solver_id, kernel_time, workspace_sz in solvers:
      for rec in solvers:
        # pylint: disable-next=consider-using-f-string ; more reable
        lst.append('{alg}:{},{},{},{alg},{}'.format(ID_SOLVER_MAP[rec.solver],
                                                    rec.kernel_time,
                                                    rec.workspace_sz,
                                                    '<unused>',
                                                    alg=rec.alg_lib))
      out.write(f"{key}={';'.join(lst)}\n")
  return file_name


def export_fdb(dbt: MIOpenDBTables, args: argparse.Namespace,
               logger: logging.Logger):
  """Function to export find_db to txt file
  """
  query = get_fdb_query(dbt, args, logger)
  fdb_alg_lists = get_fdb_alg_lists(query, logger)
  miopen_fdb = build_miopen_fdb(fdb_alg_lists, logger)

  return write_fdb(args.arch, args.num_cu, args.opencl, miopen_fdb,
                   args.filename)


def build_miopen_kdb(dbt: MIOpenDBTables, find_db, logger: logging.Logger):
  """ create miopen kernel db object for export
  """
  num_fdb_entries = 0
  num_kdb_blobs = 0
  kern_db = []
  with DbSession() as session:
    total = len(find_db.items())
    last_pcnt = 0
    for _, entries in find_db.items():
      num_fdb_entries += 1
      entries.sort(key=lambda x: float(x.kernel_time))
      fastest_slv = entries[0]
      query = session.query(dbt.kernel_cache)\
          .filter(dbt.kernel_cache.kernel_group == fastest_slv.kernel_group)
      for kinder in query.all():
        num_kdb_blobs += 1
        kern_db.append(kinder)
      pcnt = int(num_fdb_entries * 100 / total)
      if pcnt > last_pcnt:
        logger.warning("Building db: %s%%, blobs: %s", pcnt, num_kdb_blobs)
        last_pcnt = pcnt

  logger.warning("Total FDB entries: %s, Total blobs: %s", num_fdb_entries,
                 num_kdb_blobs)
  return kern_db


def write_kdb(arch, num_cu, kern_db, logger: logging.Logger, filename=None):
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

  ins_list = []
  arch_ext = arch2targetid(arch)
  for kern in kern_db:
    name = kern.kernel_name
    args = kern.kernel_args
    #check if extensions should be added
    if not name.endswith('.o'):
      name += ".o"
    if not "-mcpu=" in args:
      if not name.endswith('.mlir.o'):
        args += f" -mcpu={arch_ext}"

    ins_key = (name, args)
    if ins_key not in ins_list:
      ins_list.append(ins_key)
      cur.execute(
          "INSERT INTO kern_db (kernel_name, kernel_args, kernel_blob, kernel_hash, "
          "uncompressed_size) VALUES(?, ?, ?, ?, ?);",
          (name, args, base64.b64decode(
              kern.kernel_blob), kern.kernel_hash, kern.uncompressed_size))

  conn.commit()
  cur.close()
  conn.close()

  logger.warning("Inserted blobs: %s", len(ins_list))
  return file_name


def export_kdb(dbt: MIOpenDBTables, args: argparse.Namespace,
               logger: logging.Logger):
  """
  Function to export the kernel cache
  """
  query = get_fdb_query(dbt, args, logger)
  fdb_alg_lists = get_fdb_alg_lists(query, logger)
  miopen_fdb = build_miopen_fdb(fdb_alg_lists, logger)

  logger.info("Building kdb.")
  kern_db = build_miopen_kdb(dbt, miopen_fdb, logger)

  logger.info("write kdb to file.")
  return write_kdb(args.arch, args.num_cu, kern_db, logger, args.filename)


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


def get_cfg_dict(cfg_entry, tensor_entry):
  """compose config_dict"""
  cfg_dict = compose_config_obj(cfg_entry)

  if cfg_entry.valid == 1:
    cfg_dict = mysql_to_sqlite_cfg(cfg_dict)

  ext_dict = tensor_entry.to_dict(ommit_valid=True)
  ext_dict.pop('id')
  cfg_dict.update(ext_dict)

  #bias is always 0
  cfg_dict['bias'] = 0

  return dict(cfg_dict)


def insert_perf_db_sqlite(cnx, perf_db_entry, ins_cfg_id):
  """insert perf_db entry into sqlite"""
  perf_db_dict = perf_db_entry.to_dict()
  perf_db_dict['config'] = ins_cfg_id
  perf_db_dict = {
      k: v for k, v in perf_db_dict.items() if k in SQLITE_PERF_DB_COLS
  }
  perf_db_dict['solver'] = ID_SOLVER_MAP[perf_db_dict['solver']]

  insert_solver_sqlite(cnx, perf_db_dict)

  return perf_db_dict


def export_pdb(dbt: MIOpenDBTables, args: argparse.Namespace,
               logger: logging.Logger):
  """ export perf db from mysql to sqlite """
  cnx, local_path = create_sqlite_tables(args.arch, args.num_cu, args.filename)
  num_perf = 0
  cfg_map = {}
  db_entries = get_pdb_query(dbt, args, logger).all()
  total_entries = len(db_entries)
  logger.info("pdb query returned: %s", total_entries)

  for perf_db_entry, cfg_entry in db_entries:
    populate_sqlite(cfg_map, num_perf, cnx, perf_db_entry, cfg_entry,
                    total_entries, logger)

  cnx.commit()
  logger.warning("Total number of entries in Perf DB: %s", num_perf)

  return local_path


def populate_sqlite(cfg_map, num_perf, cnx, perf_db_entry, cfg_entry,
                    total_entries, logger: logging.Logger):
  """Analyze perf_dv entry"""
  if cfg_entry.id in cfg_map:
    ins_cfg_id = cfg_map[cfg_entry.id]
  else:
    cfg_dict = get_cfg_dict(cfg_entry, cfg_entry.input_t)

    #override cfg layout with fdb key layout
    if perf_db_entry.fdb_key:
      fds, vals, _, _ = parse_pdb_key(perf_db_entry.fdb_key)
      key_layout = vals[fds.index('out_layout')]
      if cfg_dict['layout'] != key_layout:
        raise ValueError("Out layout doesn't match fdb_key"\
                         f" {cfg_dict['layout']} != {key_layout}")

    #filters cfg_dict by SQLITE_CONFIG_COLS, inserts cfg if missing
    ins_cfg_id = get_config_sqlite(cnx, cfg_dict)
    cfg_map[cfg_entry.id] = ins_cfg_id

  pdb_dict = insert_perf_db_sqlite(cnx, perf_db_entry, ins_cfg_id)
  num_perf += 1

  if num_perf % (total_entries // 10) == 0:
    cnx.commit()
    logger.info("PDB count: %s, mysql cfg: %s, pdb: %s", num_perf, cfg_entry.id,
                pdb_dict)


def run_export_db(args: argparse.Namespace, logger: logging.Logger):
  """run export db script"""
  result_file = ''
  dbt = MIOpenDBTables(session_id=args.session_id)

  if args.session_id:
    try:
      args.arch = dbt.session.arch
      args.num_cu = dbt.session.num_cu
    except ValueError as terr:
      logger.error(terr)

  if args.find_db:
    result_file = export_fdb(dbt, args, logger)
  elif args.kern_db:
    result_file = export_kdb(dbt, args, logger)
  elif args.perf_db:
    result_file = export_pdb(dbt, args, logger)

  print(result_file)


def main():
  """Main module function"""
  parser = get_export_db_parser()
  args = parser.parse_args()
  run_export_db(args, setup_logger('export_db'))


if __name__ == '__main__':
  main()
