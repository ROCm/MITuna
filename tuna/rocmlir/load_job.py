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
"""
Script for adding jobs to the MySQL database
"""

# pylint: disable=duplicate-code
from sqlalchemy.exc import IntegrityError

from tuna.utils.logger import setup_logger
from tuna.parse_args import TunaArgs, setup_arg_parser
from tuna.utils.db_utility import connect_db
from tuna.dbBase.sql_alchemy import DbSession
from tuna.rocmlir.rocmlir_tables import RocMLIRDBTables

LOGGER = setup_logger('rocmlir_load_jobs')


def parse_args():
  """ Argument input for the module """
  #pylint: disable=duplicate-code
  parser = setup_arg_parser(
      'Insert jobs into MySQL db',
      [TunaArgs.VERSION, TunaArgs.ARCH, TunaArgs.NUM_CU, TunaArgs.SESSION_ID])
  parser.add_argument('-l',
                      '--label',
                      type=str,
                      dest='label',
                      required=True,
                      help='Label to annotate the jobs.',
                      default='new')
  parser.add_argument(
      '--config_type',
      dest='config_type',
      help='Specify configuration type',
      default='convolution',
      choices=['convolution', 'gemm'],  # +++pf: eventually an Enum
      type=str)

  args = parser.parse_args()
  if not args.session_id:
    parser.error('session_id must be specified')

  return args


def add_jobs(args, dbt):
  """ Add jobs based on args query specified"""
  counts = 0
  with DbSession() as session:
    query = session.query(dbt.session_table.reason) \
                   .filter(dbt.session_table.valid == 1,
                           dbt.session_table.id == args.session_id)
    reasons = query.all()
    if not reasons:
      raise ValueError(f"No session matching ID {args.session_id}")
    if len(reasons) > 1:
      raise ValueError(f"More than one session matching ID {args.session_id}")
    reason = reasons[0].reason

    query = session.query(dbt.config_table.id)\
                   .filter(dbt.config_table.valid == 1)
    configs = query.all()

    if not configs:
      LOGGER.error('No applicable configs found for args %s', args.__dict__)

    # pylint: disable=duplicate-code
    for config in configs:
      try:
        job = dbt.job_table(state='new',
                            valid=1,
                            reason=reason,
                            session=args.session_id,
                            config=config.id)
        session.add(job)
        session.commit()
        counts += 1
      except IntegrityError as err:
        session.rollback()
        LOGGER.warning('Integrity Error while adding new job: %s', err)

    return counts


def main():
  """ main """

  args = parse_args()
  dbt = RocMLIRDBTables(session_id=None, config_type=args.config_type)
  connect_db()
  cnt = add_jobs(args, dbt)
  print(f"New jobs added: {cnt}")


if __name__ == '__main__':
  main()
