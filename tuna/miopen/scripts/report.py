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
"""script for detecting find db entries with missing perf db entries"""

import numpy as np
import pandas as pd
from tuna.parse_args import TunaArgs, setup_arg_parser
from tuna.utils.logger import setup_logger
from tuna.miopen.db.tables import MIOpenDBTables
from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.db_utility import get_id_solvers

LOGGER = setup_logger('report')


def parse_args():
  """command line parsing"""
  parser = setup_arg_parser(
      'Post tuning report on config performance for current session',
      [TunaArgs.CONFIG_TYPE])
  parser.add_argument(
      '--session_id',
      required=True,
      dest='session_id',
      type=int,
      help='Session id to be used for comaprison against golden_v')
  parser.add_argument('--golden_v',
                      dest='golden_v',
                      required=True,
                      type=int,
                      default=None,
                      help='Target golden miopen version')

  args = parser.parse_args()
  return args


def get_data(args, dbt, arch, num_cu):
  """Get data from DB based on args.session_id and optional golden_v"""

  with DbSession() as session:
    query = f"select config, solver, kernel_time from {dbt.find_db_table.__tablename__} "\
            f"where session={args.session_id} order by config"
    pd.options.display.max_rows = 100
    query_data = session.execute(query).fetchall()
    all_cfgs = [x[0] for x in query_data]
    configs = set(all_cfgs)
    session_data = pd.DataFrame(data=query_data)
    query = f"select config, solver, kernel_time from conv_golden where golden_miopen_v="\
            f"{args.golden_v} and arch='{arch}' and num_cu={num_cu} and config in "\
            f"{tuple(configs)} order by config"
    golden_data = pd.DataFrame(data=session.execute(query).fetchall())
    session_data.columns = golden_data.columns = ['config', 'solver', 'ktime']

    dfr = pd.merge(session_data,
                   golden_data,
                   on=['config', 'solver'],
                   how='outer')
    return dfr, session_data, golden_data


def check_missing_configs(args, dbt, session_data, golden_data):
  """Check for configs that are in the session tuning but not in the golden_v tuning"""
  #get number of configs that are in golden_v but not in session

  sess_configs = set(session_data['config'].unique().flatten().tolist())
  golden_configs = set(golden_data['config'].unique().flatten().tolist())

  sess_miss = sess_configs.difference(golden_configs)
  gv_miss = golden_configs.difference(sess_configs)

  print_driver_cmds(args, dbt, list(sess_miss), "Missing commands", 'session')
  print_driver_cmds(args, dbt, list(gv_miss), "Missing commands", 'conv_golden')


def print_driver_cmds(args, dbt, ids_list, text, table1):
  """Print configs present in @table1 but missing from @table1"""
  with DbSession() as session:
    query = session.query(dbt.config_table.id, dbt.config_table.driver)\
                   .filter(dbt.config_table.id.in_(ids_list))
    drivers = query.all()
    LOGGER.info("%s from %s:  %s", text, table1, len(drivers))
    LOGGER.info("Driver cmds written to missing_%s_sess%s_gv%s.txt", table1,
                args.session_id, args.golden_v)
    missing_drivers = []
    with open(f"missing_{table1}_sess{args.session_id}_gv{args.golden_v}.txt",
              'w',
              encoding='utf-8') as fout:
      for entry in drivers:
        if entry[1] is not None:
          fout.write(f"{entry[1]}\n")
        else:
          missing_drivers.append(entry[0])
    if missing_drivers:
      LOGGER.warning(
          'Configs with missing drivers in db: %s that could not be written to file',
          len(missing_drivers))


def summary_report(args, data_frame):
  """Print tuning summary"""
  #dfr cols = [id, config, solver, ktime_x, ktime_y]
  dfr = data_frame.copy(deep=True)

  #copy of only entires where ktime=-1
  dfr_null = dfr.loc[dfr[['ktime_x', 'ktime_y']].eq(-1).any(axis=1)].copy()
  dfr_null.to_csv('null.csv')
  LOGGER.info("#configs with k_time=-1 in session_id= %s: %s", args.session_id,
              dfr_null['ktime_x'].eq(-1).sum())
  LOGGER.info("#configs with k_time=-1 in miopen_golden_v=%s : %s",
              args.golden_v, dfr_null['ktime_y'].eq(-1).sum())

  #remove entries where k_time=-1
  dfr = dfr.loc[~dfr[['ktime_x', 'ktime_y']].eq(-1).any(axis=1)].copy()
  dfr.to_csv('data.csv')

  dfr['diff'] = dfr['ktime_x'] - dfr['ktime_y']
  dfr.to_csv('data.csv')

  #prct configs faster or slower
  prct_positive = (dfr['diff'] > 0).sum() / dfr.shape[0] * 100
  prct_equal = (dfr['diff'] == 0).sum() / dfr.shape[0] * 100
  prct_negative = (dfr['diff'] < 0).sum() / dfr.shape[0] * 100
  #pylint: disable=logging-format-truncated
  LOGGER.info("configs with faster kernel_time: %f %%", round(prct_negative, 4))
  LOGGER.info("configs with equal kernel_time: %f %%", round(prct_equal, 4))
  LOGGER.info("configs with slower kernel_time: %f %% \n",
              round(prct_positive, 4))

  #averages
  avg_positive = (dfr['diff'] > 0).mean()
  avg_negative = (dfr['diff'] < 0).mean()
  LOGGER.info("Mean for configs with faster kernel_time: %s %%", avg_negative)
  LOGGER.info("Mean for configs with slower kernel_time: %s %%", avg_positive)
  LOGGER.info("Mean for all configs: %s %%", dfr['diff'].mean())

  prct_speedup_per_config = (dfr['ktime_x'] - dfr['ktime_y']) / (
      (dfr['ktime_x'] + dfr['ktime_y']) / 2) * 100
  LOGGER.info("Overall speed-up: %s %%", round(prct_speedup_per_config.mean(),
                                               4))
  speed_up = f"speed_up_sess{args.session_id}_gv{args.golden_v}.csv"
  LOGGER.info("Speed-up per config has been written to file: %s", speed_up)
  prct_speedup_per_config.to_csv(speed_up)

  db_data = f"db_data_sess{args.session_id}_gv{args.golden_v}.csv"
  LOGGER.info("Raw DB data has been written to file: %s\n", db_data)
  dfr.to_csv(db_data)


def detailed_report(args, dfr):
  """Print detailed tuning analysis"""

  LOGGER.info('Detailed solver report:')

  df_compare = dfr.replace(-1, np.nan).groupby('config')[['ktime_x',
                                                          'ktime_y']].idxmin()
  df_compare.columns = ['idx_x', 'idx_y']

  df_compare['solver_x'] = df_compare['idx_x'].apply(dfr['solver'].get)
  df_compare['solver_y'] = df_compare['idx_y'].apply(dfr['solver'].get)

  df_compare['ktime_x'] = df_compare['idx_x'].apply(dfr['ktime_x'].get)
  df_compare['ktime_y'] = df_compare['idx_y'].apply(dfr['ktime_y'].get)

  #dataframe where solvers have changed
  dfr_diff_solvers = df_compare.loc[df_compare['solver_x'].ne(
      df_compare['solver_y'])]
  #dataframe where solvers are the same
  dfr_same_solvers = df_compare.loc[df_compare['solver_x'].eq(
      df_compare['solver_y'])]
  dfr_same_solvers = dfr_same_solvers.drop(columns=['idx_x', 'idx_y'])
  dfr_same_solvers['%diff'] = (dfr_same_solvers['ktime_x'] - dfr_same_solvers['ktime_y'])\
                    / ((dfr_same_solvers['ktime_x'] + dfr_same_solvers['ktime_x'])/2) * 100
  LOGGER.info('Mean %%change for same solver: %s',
              dfr_same_solvers.loc[:, '%diff'].mean())
  report_file = f"same_solvers_report_sess{args.session_id}_gv{args.golden_v}.csv"
  LOGGER.info("Same solvers detailed report has been written to file: %s",
              report_file)
  dfr_same_solvers.to_csv(report_file)

  #Percentage difference formula
  diff_mean = dfr_diff_solvers.groupby(['solver_x', 'solver_y'])\
                  .apply(lambda grp: ((grp['ktime_x'] - grp['ktime_y'])
                    / ((grp['ktime_x'] + grp['ktime_x'])/2) * 100 ).mean())
  count = dfr_diff_solvers.groupby(['solver_x',
                                    'solver_y']).apply(lambda grp: grp.shape[0])
  # pylint: disable=unsupported-assignment-operation
  # pylint: disable=unsubscriptable-object
  dfr_detailed_summary = pd.DataFrame({
      'diff_mean%': diff_mean,
      'count': count
  }).reset_index()

  _, id_solver_map = get_id_solvers()
  dfr_detailed_summary['solver_x'] = dfr_detailed_summary['solver_x'].apply(
      id_solver_map.get)
  dfr_detailed_summary['solver_y'] = dfr_detailed_summary['solver_y'].apply(
      id_solver_map.get)
  LOGGER.info('Mean %%change for the solvers that have changed: %s',
              dfr_detailed_summary.loc[:, 'diff_mean%'].mean())
  report_file = f"different_solvers_report_sess{args.session_id}_gv{args.golden_v}.csv"
  LOGGER.info("Diff solvers detailed report has been written to file: %s",
              report_file)
  dfr_detailed_summary.rename(columns={
      'solver_x': 'session_solver',
      'solver_y': 'golden_solver'
  },
                              inplace=True)
  dfr_detailed_summary.to_csv(report_file)


def main():
  """main"""
  pd.options.display.max_rows = 500
  args = parse_args()
  dbt = MIOpenDBTables(session_id=args.session_id, config_type=args.config_type)
  with DbSession() as session:
    sess = session.query(dbt.session_table).filter(
        dbt.session_table.id == args.session_id).all()
    arch = sess[0].arch
    num_cu = sess[0].num_cu

  dfr, session_data, golden_data = get_data(args, dbt, arch, num_cu)
  check_missing_configs(args, dbt, session_data, golden_data)
  summary_report(args, dfr)
  detailed_report(args, dfr)


if __name__ == '__main__':
  main()
