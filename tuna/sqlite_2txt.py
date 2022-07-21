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
"""Module to dump SQLite entries to txt files"""
import argparse
import os
import sqlite3

from tuna.utils.logger import setup_logger
from tuna.metadata import SQLITE_CONFIG_COLS
from tuna.parsing import get_pdb_key

LOGGER = setup_logger('SQLite2Txt')


def parse_args():
  """Function to parse arguments"""
  parser = argparse.ArgumentParser(
      description='Convert SQLite3 perf db to txt perf db')
  parser.add_argument('sqlite_file',
                      type=str,
                      help='path to sqlite perf db file')
  return parser.parse_args()


def main():
  """Main module function"""
  args = parse_args()
  cnx = sqlite3.connect(args.sqlite_file)
  cur = cnx.cursor()
  # get all the arch/num_cu pairs
  for arch, num_cu in [('gfx803', 36), ('gfx803', 64), ('gfx900', 56),
                       ('gfx900', 64), ('gfx906', 60), ('gfx906', 64),
                       ('gfx908', 120), ('gfx1030', 36), ('gfx90a', 110)]:
    LOGGER.info('Processing %s_%s', arch, num_cu)
    cur.execute(
        "SELECT " + ','.join(SQLITE_CONFIG_COLS) +
        ",perf_db.solver, perf_db.params FROM config INNER JOIN perf_db ON \
        config.id = perf_db.config WHERE perf_db.arch = ? AND perf_db.num_cu = ? \
        ORDER by config.id;", (arch, num_cu))
    perf_db = {}
    for vals in cur.fetchall():
      params = vals[-1]
      solver = vals[-2]
      vals = vals[:-2]
      fds = {k: v for k, v in zip(SQLITE_CONFIG_COLS, vals)}
      key = get_pdb_key(fds, fds['data_type'], fds['direction'])
      if key in perf_db:
        vals = perf_db[key]
        vals.append(':'.join([solver, params]))
        perf_db[key] = vals
      else:
        perf_db[key] = [':'.join([solver, params])]
    LOGGER.info('Writing file for %s_%s', arch, num_cu)
    filename = '{}_{}.cd.pdb.txt'.format(arch, num_cu)
    f_file = open(filename, 'w')
    cnt = 0
    for key, vals in perf_db.items():
      if not vals:
        continue
      solvers_str = ';'.join(vals)
      cnt += 1
      if cnt % 500 == 0:
        LOGGER.info('%s lines written', cnt)
      f_file.write('{}={}\n'.format(key, solvers_str))
    LOGGER.info('Done writing %s lines for %s_%s', cnt, arch, num_cu)
    f_file.flush()
    os.fsync(f_file)
    f_file.close()
  cur.close()


if __name__ == '__main__':
  main()
