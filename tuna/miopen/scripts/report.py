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

import argparse
import sqlite3
from sqlalchemy import func

import matplotlib.pyplot as plt
import pandas as pd
from tuna.parse_args import TunaArgs, setup_arg_parser
from tuna.miopen.utils.parsing import parse_fdb_line
from tuna.miopen.utils.analyze_parse_db import get_sqlite_table
from tuna.miopen.driver.convolution import DriverConvolution
from tuna.miopen.utils.helper import valid_cfg_dims
from tuna.miopen.subcmd.import_db import get_cfg_driver
from tuna.utils.logger import setup_logger
from tuna.miopen.db.tables import MIOpenDBTables
from tuna.dbBase.sql_alchemy import DbSession

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
                      type=int,
                      default=None,
                      help='Target golden miopen version')

  args = parser.parse_args()
  return args


def get_data(args, dbt):
  """Get data from DB based on args.session_id and optional golden_v"""
  golden_v = None
  with DbSession() as session:
    if args.golden_v is None:
      query = session.query(func.max(dbt.golden_table.golden_miopen_v)) 
      golden_v = session.execute(query).fetchone()[0]
    else:
      golden_v = args.golden_v
      

    query = f"select t1.config as c1, t1.solver as s1, t1.kernel_time as k1,"\
            f"t2.config as c2, t2.solver as s2, t2.kernel_time as k2,"\
            f"t1.kernel_time-t2.kernel_time as diff from {dbt.find_db_table.__tablename__} t1 "\
            f"inner join (select config, solver, kernel_time, golden_miopen_v, session, "\
            f"arch, num_cu from conv_golden) t2 on t1.config=t2.config and t1.solver=t2.solver "\
            f"inner join (select id, arch, num_cu from session) s1 on s1.id={args.session_id} where "\
            f"t1.session={args.session_id} and t2.golden_miopen_v={golden_v} and "\
            f"t2.arch=s1.arch and t2.num_cu=s1.num_cu"

    #print(query)

    return pd.DataFrame(data=session.execute(query).fetchall())



def main():
  """main"""
  args = parse_args()
  dbt = MIOpenDBTables(session_id=args.session_id, config_type=args.config_type)
  df = get_data(args, dbt)
  df[6] = df[5]-df[2]

  prct_positive = (df[6] > 0).sum() / df.shape[0] *100
  prct_equal = (df[6] == 0).sum() / df.shape[0] *100
  prct_negative = (df[6] < 0).sum() / df.shape[0] *100

  print(f"configs with faster kernel_time: {round(prct_positive,4)}%")
  print(f"configs with equal kernel_time: {round(prct_equal,4)}%")
  print(f"configs with slower kernel_time: {round(prct_negative,4)}%")


if __name__ == '__main__':
  main()
