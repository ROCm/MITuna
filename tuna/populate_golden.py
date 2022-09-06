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
from sqlalchemy.exc import IntegrityError, OperationalError  #pylint: disable=wrong-import-order
from tuna.parse_args import TunaArgs, setup_arg_parser
from tuna.utils.logger import setup_logger
from tuna.tables import DBTables
from tuna.dbBase.sql_alchemy import DbSession
from tuna.session import Session

# Setup logging
LOGGER = setup_logger('populate_golden')


def parse_args():
  """! Function to parse arguments"""
  parser = setup_arg_parser('Populate golden table based on session_id',
                            [TunaArgs.CONFIG_TYPE])
  parser.add_argument(
      '--session_id',
      action='store',
      type=int,
      dest='session_id',
      help=
      'Session ID to be used as tuning tracker. Allows to correlate DB results to tuning sessions'
  )
  parser.add_argument('--golden_v',
                      action='store',
                      type=int,
                      dest='golden_v',
                      help='Golden miopen version')
  args = parser.parse_args()
  return args


def get_query(dbt):
  """! Compose query to get all fdb entries"""
  with DbSession() as session:
    query = session.query(dbt.find_db_table)\
            .filter(dbt.find_db_table.session == dbt.session.id)\
            .filter(dbt.find_db_table.valid == 1)

  return query


def add_golden_entries(args, dbt):
  """! Retrieve fdb entries and populate golden table"""
  query = get_query(dbt)
  with DbSession() as session:
    session_entry = session.query(Session).filter(
        Session.id == args.session_id).one()
    for fdb_entry in query.all():
      golden_entry = dbt.golden_table()
      golden_entry.session = args.session_id
      golden_entry.config = fdb_entry.config
      golden_entry.fdb_key = fdb_entry.fdb_key
      golden_entry.params = fdb_entry.params
      golden_entry.kernel_time = fdb_entry.kernel_time
      golden_entry.workspace_sz = fdb_entry.workspace_sz
      golden_entry.golden_miopen_v = args.golden_v
      golden_entry.solver_id = fdb_entry.solver
      golden_entry.arch = session_entry.arch
      golden_entry.num_cu = session_entry.num_cu
      try:
        session.add(golden_entry)
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
  add_golden_entries(args, dbt)


if __name__ == '__main__':
  main()
