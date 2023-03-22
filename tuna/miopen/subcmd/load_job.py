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
import logging
import argparse

from sqlalchemy.exc import IntegrityError  #pylint: disable=wrong-import-order
from sqlalchemy.sql.expression import true

from tuna.miopen.utils.metadata import ALG_SLV_MAP, TENSOR_PRECISION
from tuna.utils.db_utility import get_solver_ids
from tuna.utils.logger import setup_logger
from tuna.parse_args import TunaArgs, setup_arg_parser
from tuna.utils.db_utility import connect_db
from tuna.miopen.db.miopen_tables import Solver
from tuna.dbBase.sql_alchemy import DbSession
from tuna.miopen.utils.config_type import ConfigType
from tuna.miopen.db.tables import MIOpenDBTables
from tuna.miopen.parse_miopen_args import get_load_job_parser


def arg_fin_steps(args: argparse.Namespace):
  """fin steps for load jobs"""
  if args.fin_steps:
    steps = [x.strip() for x in args.fin_steps.split(',')]
    args.fin_steps = set(steps)


def arg_solvers(
    args: argparse.Namespace,
    logger: logging.Logger,
):
  """solvers """
  solver_id_map = get_solver_ids()
  solver_arr = None
  if args.solvers:
    solver_arr = args.solvers.split(',')
  elif args.algo:
    solver_arr = ALG_SLV_MAP[args.algo]

  solver_ids = []
  if solver_arr:
    for solver in solver_arr:
      sid = solver_id_map.get(solver, None)
      if not sid:
        logger.error(f'Invalid solver: {solver}')
      solver_ids.append((solver, sid))
  else:
    solver_ids.append(('', None))

  args.solvers = solver_ids if solver_ids else []


def test_tag_name(tag: str, dbt: MIOpenDBTables):
  """ test if a tag name is in config_tags table """
  with DbSession() as session:
    query = session.query(dbt.config_tags_table.tag)\
            .filter(dbt.config_tags_table.tag == tag)
    res = query.all()

  if not res:
    raise ValueError(f"tag '{tag}' not in config_tags")

  return True


def config_query(args: argparse.Namespace, session, dbt: MIOpenDBTables):
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


def compose_query(args: argparse.Namespace, session, dbt: MIOpenDBTables,
                  cfg_query):
  """Compose query based on args"""
  query = session.query(dbt.solver_app, Solver)\
    .filter(dbt.solver_app.session == args.session_id)\
    .filter(dbt.solver_app.solver == Solver.id)\
    .filter(dbt.solver_app.applicable == true())\
    .filter(Solver.valid == true())
  if any(x[1] for x in args.solvers):
    solver_ids = [x[1] for x in args.solvers if x[1] is not None]
    #if args.solvers[0][1]:  #check none
    #solver_ids = [x for _, x in args.solvers]
    query = query.filter(dbt.solver_app.solver.in_(solver_ids))
  if args.tunable:
    query = query.filter(Solver.tunable == true())
  if args.config_type is ConfigType.batch_norm:
    query = query.filter(Solver.config_type == ConfigType('batch_norm').name)
  else:
    query = query.filter(Solver.config_type == ConfigType('convolution').name)

  if args.only_dynamic:
    query = query.filter(Solver.is_dynamic == true())

  cfg_ids = [config.id for config in cfg_query.all()]
  query = query.filter(dbt.solver_app.config.in_(cfg_ids))

  return query


def add_jobs(
    args: argparse.Namespace,
    dbt: MIOpenDBTables,
    logger: logging.Logger,
):
  """ Add jobs based on solver or defer to all jobs function if no solver
      query specified"""
  counts = 0
  with DbSession() as session:
    cfg_query = config_query(args, session, dbt)
    query = compose_query(args, session, dbt, cfg_query)
    res = query.all()
    if not res:
      logger.error('No applicable solvers found for args %s', args.__dict__)

    fin_step_str = 'not_fin'
    if args.fin_steps:
      fin_step_str = ','.join(args.fin_steps)
    query = f"select * from {dbt.job_table.__tablename__} where session={args.session_id} and fin_step='{fin_step_str}' and reason='{args.label}'"
    logger.info(query)
    ret = session.execute(query)
    pre_ex = {}
    for obj in ret:
      if obj['config'] not in pre_ex:
        pre_ex[obj['config']] = {}
      pre_ex[obj['config']][obj['solver']] = True

    do_commit = False
    while True:
      for solv_app, slv in res:
        try:
          job = dbt.job_table()
          job.config = solv_app.config
          job.state = 'new'
          job.valid = 1
          job.reason = args.label
          job.solver = slv.solver
          job.fin_step = args.fin_steps
          job.session = args.session_id

          if job.config in pre_ex:
            if job.solver in pre_ex[job.config]:
              logger.warning("Job exists (skip): %s : %s", job.config,
                             job.solver)
              continue

          session.add(job)
          if do_commit:
            session.commit()
          counts += 1
        except IntegrityError as err:
          session.rollback()
          logger.warning('Integrity Error: %s', err)
      if not do_commit:
        try:
          session.commit()
        except IntegrityError as err:
          session.rollback()
          counts = 0
          do_commit = True
          logger.warning(
              'Quick update failed, rolling back to add one by one : %s', err)
          continue
      break

  return counts


def run_load_job(args: argparse.Namespace, logger: logging.Logger):
  """trigger the script run in miopen lib"""

  connect_db()

  dbt = MIOpenDBTables(session_id=None, config_type=args.config_type)
  if args.tag:
    try:
      test_tag_name(args.tag, dbt)
    except ValueError as terr:
      logger.error(terr)

  cnt = add_jobs(args, dbt, logger)
  print(f"New jobs added: {cnt}")


def main():
  """ main """
  parser = get_load_job_parser()
  args = parser.parse_args()
  run_load_job(args, setup_logger('load_job'))


if __name__ == '__main__':
  main()
