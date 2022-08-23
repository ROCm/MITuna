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
"""
Script for adding jobs to the MySQL database
"""

import mysql.connector  # pylint: disable=unused-import
from sqlalchemy.exc import IntegrityError  #pylint: disable=wrong-import-order
from sqlalchemy.sql.expression import true

from tuna.metadata import ALG_SLV_MAP, get_solver_ids, TENSOR_PRECISION
from tuna.utils.logger import setup_logger
from tuna.parse_args import TunaArgs, setup_arg_parser
from tuna.db_tables import connect_db
from tuna.miopen_tables import Solver
from tuna.dbBase.sql_alchemy import DbSession
from tuna.config_type import ConfigType
from tuna.tables import DBTables

LOGGER = setup_logger('load_jobs')
LOG_FREQ = 100


def parse_args():
  """ Argument input for the module """
  #pylint: disable=duplicate-code
  parser = setup_arg_parser(
      'Insert jobs into MySQL db by tag from" \
      " config_tags table.',
      [TunaArgs.ARCH, TunaArgs.NUM_CU, TunaArgs.VERSION, TunaArgs.CONFIG_TYPE])
  config_filter = parser.add_mutually_exclusive_group(required=True)
  solver_filter = parser.add_mutually_exclusive_group()
  config_filter.add_argument(
      '-t',
      '--tag',
      type=str,
      dest='tag',
      help='All configs with this tag will be added to the job table. \
                        By default adds jobs with no solver specified (all solvers).'
  )
  config_filter.add_argument('--all_configs',
                             dest='all_configs',
                             action='store_true',
                             help='Add all convolution jobs')
  solver_filter.add_argument(
      '-A',
      '--algo',
      type=str,
      dest='algo',
      default=None,
      help='Add job for each applicable solver+config in Algorithm.',
      choices=ALG_SLV_MAP.keys())
  solver_filter.add_argument('-s',
                             '--solvers',
                             type=str,
                             dest='solvers',
                             default=None,
                             help='add jobs with only these solvers '\
                               '(can be a comma separated list)')
  parser.add_argument(
      '-o',
      '--only_applicable',
      dest='only_app',
      action='store_true',
      help='Use with --tag to create a job for each applicable solver.')
  parser.add_argument('--tunable',
                      dest='tunable',
                      action='store_true',
                      help='Use to add only tunable solvers.')
  parser.add_argument('-c',
                      '--cmd',
                      type=str,
                      dest='cmd',
                      default=None,
                      required=False,
                      help='Command precision for config',
                      choices=['conv', 'convfp16', 'convbfp16'])
  parser.add_argument('-l',
                      '--label',
                      type=str,
                      dest='label',
                      required=True,
                      help='Label to annontate the jobs.',
                      default='new')
  parser.add_argument('--fin_steps', dest='fin_steps', type=str, default=None)
  parser.add_argument(
      '--session_id',
      action='store',
      required=True,
      type=int,
      dest='session_id',
      help=
      'Session ID to be used as tuning tracker. Allows to correlate DB results to tuning sessions'
  )

  args = parser.parse_args()

  if args.fin_steps:
    steps = [x.strip() for x in args.fin_steps.split(',')]
    args.fin_steps = set(steps)

  solver_id_map, _ = get_solver_ids()
  solver_arr = None
  if args.solvers:
    solver_arr = args.solvers.split(',')
  elif args.algo:
    solver_arr = ALG_SLV_MAP[args.algo]

  if solver_arr:
    solver_ids = []
    for solver in solver_arr:
      sid = solver_id_map.get(solver, None)
      if not sid:
        parser.error('Invalid solver: {}'.format(solver))
      solver_ids.append((solver, sid))
    args.solvers = solver_ids
  else:
    args.solvers = [('', None)]

  return args


def test_tag_name(tag, dbt):
  """ test if a tag name is in config_tags table """
  with DbSession() as session:
    query = session.query(dbt.config_tags_table.tag).distinct()
  tag_names = []
  for row in query.all():
    tag_names.append(row.tag)

  if tag not in tag_names:
    raise ValueError("tag '{}' not in config_tags".format(tag))

  return True


def insert_job_all(args, counts, cfg_query, dbt):
  """ insert all jobs for the given session for applicable solvers"""
  do_commit = False
  with DbSession() as session:
    while True:  #pylint: disable=too-many-nested-blocks
      for config_entry in cfg_query.all():
        for solver_name, _ in args.solvers:
          if counts['cnt_jobs'] % LOG_FREQ == 0:
            print('.', flush=True, end='')
          try:
            job = dbt.job_table()
            job.config = config_entry.id
            job.state = 'new'
            job.valid = True
            job.reason = args.label
            job.fin_step = args.fin_steps
            job.solver = solver_name
            job.session = args.session_id
            session.add(job)
            if do_commit:
              session.commit()
            counts['cnt_jobs'] += 1
          except IntegrityError as err:
            session.rollback()
            LOGGER.warning("Integrity Error: %s", err)
      if not do_commit:
        try:
          session.commit()
        except IntegrityError as err:
          session.rollback()
          counts['cnt_jobs'] = 0
          do_commit = True
          LOGGER.warning(
              "Quick update failed, rolling back to add one by one: %s", err)
          continue
      break
  return True


def config_query(args, session, dbt):
  """ Produce config query for new style config table"""
  cfg_query = session.query(dbt.config_table)\
      .filter(dbt.config_table.valid == 1)

  if args.tag:
    tag_query = session.query(dbt.config_tags_table.config)\
      .filter(dbt.config_tags_table.tag == args.tag).subquery()
    cfg_query = cfg_query.filter(dbt.config_table.id.in_(tag_query))

  if args.cmd:
    cfg_query = cfg_query.filter(
        dbt.config_table.input_t.data_type == TENSOR_PRECISION[args.cmd])

  return cfg_query


def compose_query(args, session, dbt, cfg_query):
  """Compose query based on args"""
  query = session.query(dbt.solver_app, Solver)\
    .filter(dbt.solver_app.session == args.session_id)\
    .filter(dbt.solver_app.solver == Solver.id)\
    .filter(dbt.solver_app.applicable == true())\
    .filter(Solver.valid == true())
  if args.solvers[0][1]:  #check none
    solver_ids = [x for _, x in args.solvers]
    query = query.filter(dbt.solver_app.solver.in_(solver_ids))
  if args.tunable:
    query = query.filter(Solver.tunable == true())
  if args.config_type is ConfigType.batch_norm:
    query = query.filter(Solver.config_type == ConfigType('batch_norm').name)
  else:
    query = query.filter(Solver.config_type == ConfigType('convolution').name)

  cfg_ids = [config.id for config in cfg_query.all()]
  query = query.filter(dbt.solver_app.config.in_(cfg_ids))

  return query


def add_jobs(args, counts, dbt):
  """ Add jobs based on solver or defer to all jobs function if no solver
      query specified"""
  with DbSession() as session:
    cfg_query = config_query(args, session, dbt)
    if args.only_app:
      query = compose_query(args, session, dbt, cfg_query)
      do_commit = False
      while True:
        for solv_app, slv in query.all():
          if counts['cnt_jobs'] % LOG_FREQ == 0:
            print('.', flush=True, end='')
          try:
            job = dbt.job_table()
            job.config = solv_app.config
            job.state = 'new'
            job.valid = 1
            job.reason = args.label
            job.solver = slv.solver
            job.fin_step = args.fin_steps
            job.session = args.session_id
            session.add(job)
            if do_commit:
              session.commit()
            counts['cnt_jobs'] += 1
          except IntegrityError as err:
            session.rollback()
            LOGGER.warning('Integrity Error: %s', err)
        if not do_commit:
          try:
            session.commit()
          except IntegrityError as err:
            session.rollback()
            counts['cnt_jobs'] = 0
            do_commit = True
            LOGGER.warning(
                'Quick update failed, rolling back to add one by one : %s', err)
            continue
        break

    else:
      insert_job_all(args, counts, cfg_query, dbt)


def main():
  """ main """
  args = parse_args()
  connect_db()

  counts = {}
  counts['cnt_jobs'] = 0

  dbt = DBTables(session_id=None, config_type=args.config_type)
  if args.tag:
    try:
      test_tag_name(args.tag, dbt)
    except ValueError as terr:
      LOGGER.error(terr)

  add_jobs(args, counts, dbt)

  print('New jobs added: {}'.format(counts['cnt_jobs']))


if __name__ == '__main__':
  main()
