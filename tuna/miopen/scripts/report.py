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

from sqlalchemy import func

import pandas as pd
from tuna.parse_args import TunaArgs, setup_arg_parser
from tuna.utils.logger import setup_logger
from tuna.miopen.db.tables import MIOpenDBTables
from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.db_utility import get_id_solvers

LOGGER = setup_logger('report')


def parse_args():
  """command line parsing"""
  parser = setup_arg_parser('Post tuning report on config performance for current session',
                            [TunaArgs.CONFIG_TYPE])
  parser.add_argument(
      '--session_id',
      required=True,
      dest='session_id',
      type=int,
      help=
      'Session id to be used for comaprison against golden_v'
  )
  parser.add_argument('--golden_v',
                      dest='golden_v',
                      required=True,
                      type=int,
                      default=None,
                      help='Target golden miopen version')

  args = parser.parse_args()
  return args


def get_data(args, dbt):
  """Get data from DB based on args.session_id and optional golden_v"""

    query = f"select t1.config as c1, t1.solver as s1, t1.kernel_time as k1,"\
            f"t2.config as c2, t2.solver as s2, t2.kernel_time as k2,"\
            f"t1.kernel_time-t2.kernel_time as diff from {dbt.find_db_table.__tablename__} t1 "\
            f"inner join (select config, solver, kernel_time, golden_miopen_v, session, "\
            f"arch, num_cu from conv_golden) t2 on t1.config=t2.config and t1.solver=t2.solver "\
            f"inner join (select id, arch, num_cu from session) s1 on s1.id={args.session_id} where "\
            f"t1.session={args.session_id} and t2.golden_miopen_v={args.golden_v} and "\
            f"t2.arch=s1.arch and t2.num_cu=s1.num_cu order by t1.config"

    return pd.DataFrame(data=session.execute(query).fetchall())

def check_missing_configs(args, dbt):
  """Check for configs that are in the session tuning but not in the golden_v tuning"""
  arch = None
  num_cu=None

  with DbSession() as session:
    sess = session.query(dbt.session_table).filter(dbt.session_table.id==args.session_id).all()
    arch = sess[0].arch
    num_cu = sess[0].num_cu

    query = f"select distinct config from {dbt.find_db_table.__tablename__} where id={args.session_id} "\
            f"and config not in (select config from {dbt.golden_table.__tablename__} where "\
            f"golden_miopen_v={args.golden_v} and arch='{arch}' and num_cu={num_cu})"
    missing_configs = [x[0] for x in session.execute(query).fetchall()]
    print_driver_cmds(missing_configs, "Missing commands")


def print_driver_cmds(ids_list, text):
  with DbSession() as session:
    query = session.query(dbt.config_table.driver)\
                   .filter(dbt.config_table.id.in_(ids_list))
    drivers = [x[0] for x in query.all()]
    print(f"{text}: {len(drivers)}")
    for cfg in drivers:
      print(cfg)

def summary_report(args, dbt):
  """Print tuning summary"""
  df = get_data(args, dbt)

  #print(df.shape[0])
  df_null = df.loc[df[[2, 5]].eq(-1).any(axis=1)].copy()
  print(f"#configs with k_time=-1 in session_id={args.session_id}: {df_null[2].eq(-1).sum()}")
  print(f"#configs with k_time=-1 in miopen_golden_v={args.golden_v}: {df_null[5].eq(-1).sum()}")
  df = df.loc[~df[[2, 5]].eq(-1).any(axis=1)]
  #df.to_csv('data.csv')
  return df
  #add summary for #configs with -1 k time
  #print(df_null.shape[0])
  #print(df.shape[0])


  df[6] = df[5]-df[2]
  pd.options.display.max_rows = 100
  print(df.tail(100))


  #prct configs faster or slower
  prct_positive = (df[6] > 0).sum() / df.shape[0] *100
  prct_equal = (df[6] == 0).sum() / df.shape[0] *100
  prct_negative = (df[6] < 0).sum() / df.shape[0] *100
  print(f"configs with faster kernel_time: {round(prct_positive,4)}%")
  print(f"configs with equal kernel_time: {round(prct_equal,4)}%")
  print(f"configs with slower kernel_time: {round(prct_negative,4)}%")

  #averages
  avg_positive = (df[6] > 0).mean()
  avg_negative = (df[6] < 0).mean()
  print(f"Mean for configs with faster kernel_time: {avg_positive}")
  print(f"Mean for configs with slower kernel_time: {avg_negative}")
  print(f"Mean for all configs: {df[6].mean()}")

  prct_speedup_per_config = (df[2]-df[5]) / ((df[2]+df[5]) /2) * 100
  print(f"Overall speed-up: {round(prct_speedup_per_config.mean(), 4)}")

  return df

def detailed_report(args, dbt, df):
  """Print detailed tuning analysis"""
  #df = pd.read_csv('data.csv', index_col=0, header=0)
  #df.columns = df.columns.map(int)
  df_new = df.loc[:, 0:2]
  df_old = df.loc[:, 3:5]
  df_new.columns = df_old.columns = ['config', 'solver', 'ktime']
  df_new_unq = df_new.loc[df_new.groupby('config')['ktime'].idxmin()]
  df_old_unq = df_old.loc[df_old.groupby('config')['ktime'].idxmin()]
  df_unq = df_new_unq.merge(df_old_unq, on='config')
  df_diff = df_unq[df_unq['solver_x'] != df_unq['solver_y']]

  #for key, grp in df_diff.groupby(['solver_x', 'solver_y']):
  #  print(key, ((grp['ktime_y'] - grp['ktime_x']) / grp['ktime_x']).mean(), grp.shape[0])

  diff_mean = df_diff.groupby(['solver_x', 'solver_y']).apply(lambda grp: ((grp['ktime_y'] - grp['ktime_x']) / grp['ktime_x']).mean())
  count = df_diff.groupby(['solver_x', 'solver_y']).apply(lambda grp: grp.shape[0])
  df_detailed_summary = pd.DataFrame({'diff_mean': diff_mean, 'count' : count}).reset_index()

  _, id_solver_map = get_id_solvers()
  df_detailed_summary['solver_x'] = df_detailed_summary['solver_x'].apply(id_solver_map.get)
  df_detailed_summary['solver_y'] = df_detailed_summary['solver_y'].apply(id_solver_map.get)
  #print(df_detailed_summary)
  print("Detailed report has been written to file 'detailed_report.csv'")
  df_detailed_summary.to_csv('detailed_report_sess{args.session_id}_gv{args.golden_v}.csv', mode='a')
  #df_detailed_summary.tail(100) 
  

def main():
  """main"""
  args = parse_args()
  dbt = MIOpenDBTables(session_id=args.session_id, config_type=args.config_type)

  #check_missing_configs(args, dbt)
  df = summary_report(args, dbt)
  detailed_report(args, dbt, df)


if __name__ == '__main__':
  main()
