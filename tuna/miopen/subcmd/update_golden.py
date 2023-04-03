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
from sqlalchemy.sql.expression import func as sqlfunc
from sqlalchemy.exc import OperationalError

from tuna.parse_args import TunaArgs, setup_arg_parser
from tuna.dbBase.sql_alchemy import DbSession
from tuna.miopen.db.tables import MIOpenDBTables
from tuna.miopen.db.session import Session
from tuna.utils.db_utility import session_retry
from tuna.utils.logger import setup_logger
from tuna.db_engine import ENGINE

# Setup logging
LOGGER = setup_logger('update_golden')


def parse_args():
  """! Function to parse arguments"""
  parser = setup_arg_parser('Populate golden table based on session_id',
                            [TunaArgs.CONFIG_TYPE])
  parser.add_argument('--golden_v',
                      dest='golden_v',
                      type=int,
                      default=None,
                      required=True,
                      help='target golden miopen version to write')
  parser.add_argument('--base_golden_v',
                      dest='base_golden_v',
                      type=int,
                      default=None,
                      required=False,
                      help='previous golden miopen version for initialization')
  parser.add_argument('--session_id',
                      required=False,
                      dest='session_id',
                      type=int,
                      help='Tuning session to be imported to golden table.')
  parser.add_argument('-o',
                      '--overwrite',
                      dest='overwrite',
                      action='store_true',
                      default=False,
                      help='Write over existing golden version.')
  parser.add_argument('--create_perf_table',
                      dest='create_perf_table',
                      action='store_true',
                      default=False,
                      help='Create performance table.')

  args = parser.parse_args()

  if not args.base_golden_v and not args.session_id:
    dbt = MIOpenDBTables(session_id=args.session_id,
                         config_type=args.config_type)
    ver = latest_golden_v(dbt)
    if ver != -1:
      parser.error(
          'Specify --base_golden_v or --session_id to select tuning data to use for update'
      )

  return args


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
    query = session.query(sqlfunc.max(dbt.golden_table.golden_miopen_v))
    obj = query.first()
    if obj:
      version = obj[0]

  if version is None:
    version = -1
  LOGGER.warning(version)

  return version


def sess_info(session):
  """ get map for session id to arch / num_cu """
  sess_map = {}
  query = session.query(Session.id, Session.arch, Session.num_cu)
  for entry in query.all():
    sess_map[entry.id] = (entry.arch, entry.num_cu)

  return sess_map


def verify_no_duplicates(entries):
  """ check entries for duplicates (error in fdb) """
  with DbSession() as session:
    sess_map = sess_info(session)
  test_set = {}
  for entry in entries:
    arch, num_cu = sess_map[entry.session]
    key = f"{entry.config}-{entry.solver}-{arch}-{num_cu}"
    if key in test_set:
      LOGGER.error(
          "Overlap on key! %s (fdb_key %s, params %s) vs (fdb_key %s, params %s)",
          key, test_set[key].fdb_key, test_set[key].params, entry.fdb_key,
          entry.params)
      return False
    test_set[key] = entry

  return True


def get_perf_str(args, table_name):
  """Create perf table SQL query and return"""
  new_table = f"""
  create table {table_name} as select a.config, a.num_cu, a.arch, b.k1 as k1, c.k1 as k2,
    d.k1 as k3, c.k1-b.k1 as gv4_5, d.k1-c.k1 as gv5_6 from conv_golden a
    inner join(select config, min(kernel_time) as k1, arch, num_cu from conv_golden
    where golden_miopen_v={args.golden_v-2} and kernel_time!=-1 group by config, arch, num_cu)
      as b on a.config=b.config and a.arch=b.arch and a.num_cu=b.num_cu
    inner join(select config, min(kernel_time) as k1, arch, num_cu from conv_golden
    where golden_miopen_v={args.golden_v-1} and kernel_time!=-1 group by config, arch, num_cu)
      as c on a.config=c.config and a.arch=c.arch and a.num_cu=c.num_cu
    inner join(select config, min(kernel_time) as k1, arch, num_cu from conv_golden
    where golden_miopen_v={args.golden_v} and kernel_time!=-1 group by config, arch, num_cu)
      as d on a.config=d.config and a.arch=d.arch and a.num_cu=d.num_cu
  where a.golden_miopen_v={args.golden_v} group by a.config, a.arch, a.num_cu, b.k1, c.k1, d.k1;
  """
  return new_table


def create_perf_table(args):
  """Create new perf_table"""
  if args.golden_v == 0:
    table_name = "conv_gv0"
  elif args.golden_v == 1:
    table_name = "conv_gv10"
  else:
    vm1 = str(args.golden_v - 1)
    vm2 = str(args.golden_v - 2)
    table_name = f"conv_gv{vm2}{vm1}{args.golden_v}"
  print(table_name)
  with ENGINE.connect() as conn:
    try:
      conn.execute(f'drop table if exists {table_name}')
      LOGGER.info('Creating new performance table %s', table_name)
      conn.execute(get_perf_str(args, table_name))
      LOGGER.info('Done creating new performance table %s', table_name)
    except OperationalError as oerr:
      LOGGER.info('%s \n', oerr)
      return False

  return True


def gold_base_update(session: DbSession,
                     gold_v: int,
                     base_gold_v: int,
                     overwrite: bool = False):
  """copy over data in conv_golden from previous golden version"""
  if overwrite:
    LOGGER.info("Updating golden version %s -> %s.", base_gold_v, gold_v)
    update_q = "update conv_golden as cg inner join conv_golden as ps on cg.config=ps.config"\
    " and cg.fdb_key=ps.fdb_key and cg.alg_lib=ps.alg_lib and cg.opencl=ps.opencl"\
    " and cg.solver=ps.solver and ps.arch=cg.arch and ps.num_cu=cg.num_cu"\
    " set cg.valid=ps.valid, cg.params=ps.params, cg.workspace_sz=ps.workspace_sz"\
    ", cg.kernel_time=ps.kernel_time, cg.kernel_group=ps.kernel_group, cg.session=ps.session"\
    f" where cg.golden_miopen_v={gold_v} and ps.golden_miopen_v={base_gold_v} and ps.valid=1"\
    " and ps.kernel_time>=0;"
    LOGGER.info(update_q)
    session.execute(update_q)

  LOGGER.info("Inserting golden version %s -> %s.", base_gold_v, gold_v)
  insert_q = "insert ignore into conv_golden (valid, golden_miopen_v, arch, num_cu, config, fdb_key"\
  ", params, kernel_time, workspace_sz, alg_lib, opencl, kernel_group, session, solver)"\
  f" select valid, {gold_v}, arch, num_cu, config, fdb_key, params, kernel_time"\
  ", workspace_sz, alg_lib, opencl, kernel_group, session, solver"\
  f" from conv_golden where golden_miopen_v={base_gold_v} and valid=1 and kernel_time>=0;"
  LOGGER.info(insert_q)
  session.execute(insert_q)
  session.commit()

  return True


def gold_session_update(session: DbSession,
                        gold_v: int,
                        tune_s: int,
                        overwrite: bool = True):
  """copy data to conv_golden from tuning session in conv_find_db"""
  if overwrite:
    LOGGER.info("Gold %s Update with session %s.", gold_v, tune_s)
    update_q = "update conv_golden as cg inner join conv_find_db as ps on cg.config=ps.config"\
    " and cg.fdb_key=ps.fdb_key and cg.alg_lib=ps.alg_lib and cg.opencl=ps.opencl"\
    " and cg.solver=ps.solver"\
    " inner join session as s on ps.session=s.id and s.arch=cg.arch and s.num_cu=cg.num_cu"\
    " set cg.valid=ps.valid, cg.params=ps.params, cg.workspace_sz=ps.workspace_sz"\
    ", cg.kernel_time=ps.kernel_time, cg.kernel_group=ps.kernel_group, cg.session=ps.session"\
    f" where cg.golden_miopen_v={gold_v} and ps.session={tune_s} and ps.valid=1"\
    " and ps.kernel_time>=0;"
    session.execute(update_q)

  LOGGER.info("Gold %s Insert session %s.", gold_v, tune_s)
  insert_q = "insert ignore into conv_golden (valid, golden_miopen_v, arch, num_cu, config, fdb_key"\
  ", params, kernel_time, workspace_sz, alg_lib, opencl, kernel_group, session, solver)"\
  f" select cfd.valid, {gold_v}, arch, num_cu, config, fdb_key, params, kernel_time"\
  ", workspace_sz, alg_lib, opencl, kernel_group, session, solver"\
  " from conv_find_db as cfd inner join session as s on cfd.session=s.id"\
  f" where session={tune_s} and cfd.valid=1 and kernel_time>=0;"
  session.execute(insert_q)
  session.commit()

  return True


def main():
  """! Main function"""
  args = parse_args()
  dbt = MIOpenDBTables(session_id=args.session_id, config_type=args.config_type)

  gold_db = get_golden_query(dbt, args.golden_v).first()
  if gold_db and not args.overwrite:
    raise ValueError(
        f'Target golden version {args.golden_v} exists, but --overwrite is not specified.'
    )

  with DbSession() as session:
    if args.base_golden_v:

      def actuator(func):
        return func(session, args.golden_v, args.base_golden_v, args.overwrite)

      session_retry(session, gold_base_update, functools.partial(actuator),
                    LOGGER)

    if args.session_id:

      def actuator(func):
        return func(session, args.golden_v, args.session_id, args.overwrite)

      session_retry(session, gold_session_update, functools.partial(actuator),
                    LOGGER)

  if args.create_perf_table:
    LOGGER.info('Updating conv perf DB table')
    create_perf_table(args)

  return True


if __name__ == '__main__':
  main()
