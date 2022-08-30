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
from tuna.parse_args import TunaArgs, setup_arg_parser
from tuna.utils.logger import setup_logger
from tuna.tables import DBTables
from tuna.dbBase.sql_alchemy import DbSession
from sqlalchemy.exc import IntegrityError, OperationalError  #pylint: disable=wrong-import-order

# Setup logging
LOGGER = setup_logger('populate_golden')


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
    if not args.golden_v:
      parser.error('--golden_v must be set with --overwrite')
    if args.base_golden_v:
      parser.error('--base_golden_v must not be set with --overwrite')
  elif not args.base_golden_v:
    parser.error(
        'When using --golden_v to create a new version, specify --base_golden_v'
    )

  return args


def get_fdb_query(dbt):
  """! Compose query to get all fdb entries for the session"""
  with DbSession() as session:
    query = session.query(dbt.find_db_table)\
            .filter(dbt.find_db_table.session == dbt.session.id)\
            .filter(dbt.find_db_table.kernel_time != -1)\
            .filter(dbt.find_db_table.valid == 1)

  return query


def get_golden_query(dbt, golden_version):
  """! Compose query to get all entries for a golden miopen version"""
  with DbSession() as session:
    query = session.query(dbt.golden_table)\
            .filter(dbt.golden_table.golden_miopen_v == golden_version)\
            .filter(dbt.find_db_table.valid == 1)

  return query


def latest_golden_v(dbt):
  """Get highest golden version in the table """
  version = -1
  with DbSession() as session:
    query = session.query(dbt.golden_table).order_by(
        dbt.golden_table.golden_miopen_v.max())
    obj = query.first()
    if obj:
      version = obj.golden_miopen_v

  return version


def merge_golden_entries(dbt, golden_v, entries):
  """! Retrieve fdb entries and populate golden table"""
  with DbSession() as session:
    for copy_entry in entries:
      golden_entry = dbt.golden_table()
      golden_entry.session = copy_entry.session

      #unique identifiers
      golden_entry.golden_miopen_v = golden_v
      golden_entry.config = copy_entry.config
      golden_entry.solver = copy_entry.solver
      golden_entry.arch = dbt.session.arch
      golden_entry.num_cu = dbt.session.num_cu

      golden_entry.fdb_key = copy_entry.fdb_key
      golden_entry.params = copy_entry.params
      golden_entry.kernel_time = copy_entry.kernel_time
      golden_entry.workspace_sz = copy_entry.workspace_sz
      golden_entry.alg_lib = copy_entry.alg_lib
      golden_entry.opencl = copy_entry.opencl

      golden_entry.kernel_group = copy_entry.kernel_group

      try:
        session.merge(golden_entry)
        session.commit()
      except OperationalError as oerror:
        LOGGER.warning('DB error: %s', oerror)
      except IntegrityError as ierror:
        LOGGER.warning('DB error: %s', ierror)
        session.rollback()
        continue

  return True


def main():
  """! Main function"""
  args = parse_args()
  dbt = DBTables(session_id=args.session_id, config_type=args.config_type)

  gold_db = get_golden_query(dbt, args.golden_v).all()
  if not gold_db:
    if args.overwrite:
      raise ValueError(f'Target golden version {args.golden_v} does not exist.')
  elif not args.overwrite:
    raise ValueError(
        f'Target golden version {args.golden_v} exists, but --overwrite is not specified.'
    )

  if args.base_golden_v:
    base_gold_db = get_golden_query(dbt, args.base_golden_v).all()
    if not base_gold_db:
      raise ValueError(
          f'Base golden version {args.base_golden_v} does not exist.')
    merge_golden_entries(dbt, args.golden_v, base_gold_db)

  query = get_fdb_query(dbt)
  merge_golden_entries(dbt, args.golden_v, query.all())


if __name__ == '__main__':
  main()
