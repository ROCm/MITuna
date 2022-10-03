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
"""! @brief Script to populate the golden table based on session_id"""
import functools
from sqlalchemy.sql.expression import func

from tuna.parse_args import TunaArgs, setup_arg_parser
from tuna.utils.logger import setup_logger
from tuna.tables import DBTables
from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.db_utility import session_retry
from tuna.session import Session

# Setup logging
LOGGER = setup_logger('update_golden')


def parse_args():
  """! Function to parse arguments"""
  parser = setup_arg_parser('Populate golden table based on session_id',
                            [TunaArgs.CONFIG_TYPE])
  parser.add_argument(
      '--session_id',
      dest='session_id',
      action='store',
      type=int,
      required=True,
      help=
      'Session ID to be used as tuning tracker. Allows to correlate DB results to tuning sessions'
  )
  parser.add_argument('--golden_v',
                      dest='golden_v',
                      action='store',
                      type=int,
                      default=None,
                      required=True,
                      help='target golden miopen version to write')
  parser.add_argument('--base_golden_v',
                      dest='base_golden_v',
                      action='store',
                      type=int,
                      default=None,
                      required=False,
                      help='previous golden miopen version for initialization')
  parser.add_argument('-o',
                      '--overwrite',
                      dest='overwrite',
                      action='store_true',
                      default=False,
                      help='Write over existing golden version.')

  args = parser.parse_args()

  if args.overwrite:
    if args.base_golden_v is not None:
      parser.error('--base_golden_v must not be set with --overwrite')
  elif args.base_golden_v is None:
    dbt = DBTables(session_id=args.session_id, config_type=args.config_type)
    ver = latest_golden_v(dbt)
    if ver != -1:
      parser.error(
          'When using --golden_v to create a new version, specify --base_golden_v'
      )

  return args


def get_fdb_query(dbt):
  """! Compose query to get all fdb entries for the session"""
  with DbSession() as session:
    query = session.query(dbt.find_db_table)\
            .filter(dbt.find_db_table.session == dbt.session_id)\
            .filter(dbt.find_db_table.valid == 1)

  return query


def get_golden_query(dbt, golden_version):
  """! Compose query to get all entries for a golden miopen version"""
  with DbSession() as session:
    query = session.query(dbt.golden_table)\
            .filter(dbt.golden_table.golden_miopen_v == golden_version)\
            .filter(dbt.golden_table.valid == 1)

  return query


def latest_golden_v(dbt):
  """Get highest golden version in the table """
  version = -1
  with DbSession() as session:
    query = session.query(func.max(dbt.golden_table.golden_miopen_v))
    obj = query.first()
    if obj:
      version = obj[0]

  if version is None:
    version = -1
  LOGGER.warning(version)

  return version


def get_gold_query(session, gold_table, gold_entry):
  """Construct a Db query for the golden entry
  """
  query = session.query(gold_table).filter(
      gold_table.golden_miopen_v == gold_entry.golden_miopen_v,
      gold_table.config == gold_entry.config,
      gold_table.solver == gold_entry.solver,
      gold_table.arch == gold_entry.arch,
      gold_table.num_cu == gold_entry.num_cu)

  return query


def update_gold_entry(session, golden_table, gold_entry):
  """ Add a new entry to golden table if there isnt one already """
  gold_query = get_gold_query(session, golden_table, gold_entry)
  obj = gold_query.first()
  if obj:  # existing entry in db
    ret = obj
  else:
    # Insert the above entry
    session.add(gold_entry)
    ret = gold_entry
  return ret


def sess_info(session):
  """ get map for session id to arch / num_cu """
  sess_map = {}
  query = session.query(Session.id, Session.arch, Session.num_cu)
  for entry in query.all():
    sess_map[entry.id] = (entry.arch, entry.num_cu)

  return sess_map


def init_gold_entry(dbt, golden_v, config, solver, arch, num_cu):
  """ initialize golden_table entry with key values """
  gold_entry = dbt.golden_table()
  #unique identifiers
  gold_entry.golden_miopen_v = golden_v
  gold_entry.config = config
  gold_entry.solver = solver
  gold_entry.arch = arch
  gold_entry.num_cu = num_cu
  return gold_entry


def copy_gold_data(gold_entry, entry):
  """ copy data fields for a golden_table entry """
  gold_entry.valid = 1
  gold_entry.session = entry.session

  gold_entry.fdb_key = entry.fdb_key
  gold_entry.params = entry.params
  gold_entry.kernel_time = entry.kernel_time
  gold_entry.workspace_sz = entry.workspace_sz
  gold_entry.alg_lib = entry.alg_lib
  gold_entry.opencl = entry.opencl

  gold_entry.kernel_group = entry.kernel_group


def merge_golden_entries(session, dbt, golden_v, entries, simple_copy=False):
  """! Retrieve fdb entries and populate golden table"""
  sess_map = sess_info(session)
  count = 0
  print_interval = len(entries) // 10
  for copy_entry in entries:
    arch, num_cu = sess_map[copy_entry.session]
    golden_entry = init_gold_entry(dbt, golden_v, copy_entry.config,
                                   copy_entry.solver, arch, num_cu)

    if simple_copy:
      session.add(golden_entry)
    else:
      #resolve to existing entry if present
      golden_entry = update_gold_entry(session, dbt.golden_table, golden_entry)

    copy_gold_data(golden_entry, copy_entry)

    count += 1
    if count % print_interval == 0:
      gld = golden_entry
      t_str = f"{count}: {gld.golden_miopen_v}-{gld.config}-{gld.solver}-{gld.arch}-{gld.num_cu}"
      LOGGER.info(t_str)

  session.commit()

  return count


def process_merge_golden(dbt, golden_v, entries, s_copy=False):
  """" retry loop for merging into golden table """
  num_packs = 0
  pack_sz = 10000
  pack = []
  all_packs = []
  for elem in entries:
    pack.append(elem)
    num_packs += 1
    if num_packs % pack_sz == 0:
      all_packs.append(pack)
      pack = []
  if pack:
    all_packs.append(pack)

  pcnt = 0
  prev_pcnt = 0
  with DbSession() as session:
    num_packs = len(all_packs)

    callback = merge_golden_entries

    def actuator(func, pack):
      return func(session, dbt, golden_v, pack, s_copy)

    for i, pack in enumerate(all_packs):
      ret = session_retry(session, callback, functools.partial(actuator, pack),
                          LOGGER)

      if not ret:
        LOGGER.error("Failed to merge db pack %s", i)
        return False
      pcnt = int((i + 1) * 100 / num_packs)
      if pcnt > prev_pcnt:
        prev_pcnt = pcnt
        LOGGER.info("Merged: %s%%", pcnt)

  return num_packs


def main():
  """! Main function"""
  args = parse_args()
  dbt = DBTables(session_id=args.session_id, config_type=args.config_type)

  gold_db = get_golden_query(dbt, args.golden_v).first()
  if not gold_db:
    if args.overwrite:
      raise ValueError(f'Target golden version {args.golden_v} does not exist.')
  elif not args.overwrite:
    raise ValueError(
        f'Target golden version {args.golden_v} exists, but --overwrite is not specified.'
    )

  if args.base_golden_v is not None:
    base_gold_db = get_golden_query(dbt, args.base_golden_v).all()
    if not base_gold_db:
      ver = latest_golden_v(dbt)
      if ver == -1:
        LOGGER.warning('No golden versions, starting from scratch.')
      else:
        raise ValueError(
            f'Base golden version {args.base_golden_v} does not exist.')
    else:
      process_merge_golden(dbt, args.golden_v, base_gold_db, s_copy=True)

  query = get_fdb_query(dbt)
  total = process_merge_golden(dbt, args.golden_v, query.all())

  LOGGER.info("Merged: %s", total)


if __name__ == '__main__':
  main()
