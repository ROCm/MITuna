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
"""Module to parse solver usage"""
from tuna.sql import DbCursor
from tuna.utils.logger import setup_logger

LOGGER = setup_logger('solver_res')
RES_FILENAME = 'solverres.csv'
RES_FILE = open(RES_FILENAME, 'w')


def parse_row(row, count, cfg_cnt, prn_header):
  """Helper function for parsing a row"""
  # get the config params
  config = None
  with DbCursor() as config_cur:
    config_cur.execute("select * from config where id = %s", (row[0],))
    config = config_cur.fetchall()
  # config_cur.column_names has names of the columns

  # get all the solver results for this config
  with DbCursor() as solver_cur:
    solver_cur.execute("select * from solver_search where config = %s",
                       (row[0],))
    if prn_header:
      header = config_cur.column_names + solver_cur.column_names
      header_str = ';'.join(header) + '\n'
      RES_FILE.write(header_str)
      prn_header = False

    for sol in solver_cur:
      count += 1
      if count % 100 == 0:
        LOGGER.info('%s lines written', count)
      row = config[0] + sol
      row = [str(x) for x in row]
      RES_FILE.write(';'.join(row) + '\n')
  cfg_cnt += 1
  LOGGER.warning('%s configs done', cfg_cnt)


def main():
  """Main function"""
  # Setup logging
  solver_name = 'ConvAsm1x1U'
  cmd_name = 'conv'

  with DbCursor() as cur:
    count = 0
    # create the solver map
    cur.execute("select id, name from solver")
    solvers = {}
    for res in cur:
      solvers[res[1]] = res[0]
    # get all the configs
    cur.execute(
        "select distinct config from solver_search inner join config on \
        config.id = solver_search.config where solver = %s and config.cmd = %s;",
        (solvers[solver_name], cmd_name))
    cfg_cnt = 0
    dist_cfg = cur.fetchall()
    prn_header = True
    for row in dist_cfg:
      parse_row(row, count, cfg_cnt, prn_header)


if __name__ == '__main__':
  main()
