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
"""Module to easily query the DB"""

import os
from tuna.utils.logger import setup_logger
from tuna.find_db import ConvolutionFindDB

from tuna.dbBase.sql_alchemy import DbSession
from tuna.parse_args import TunaArgs, setup_arg_parser
from tuna.miopen_tables import ConvolutionJob, ConvolutionConfig
from tuna.parsing import get_pdb_key
from tuna.parsing import get_fds_from_cmd

LOGGER = setup_logger('QuerDB')


def parse_args():
  """Parsing arguments"""
  parser = setup_arg_parser('Query DBs for tuned info',
                            [TunaArgs.ARCH, TunaArgs.NUM_CU])
  parser.add_argument('-s',
                      '--skip_db',
                      action='store_true',
                      dest='skip_db',
                      help='Skip DB access and only print the db keys')
  parser.add_argument(
      '-j',
      '--job_info',
      action='store_true',
      dest='job_info',
      help='Report on the various jobs which touched this config')
  parser.add_argument('-d',
                      '--fdb_info',
                      action='store_true',
                      dest='fdb_info',
                      help='Report on the variation in find db')
  parser.add_argument('driver_cmd',
                      default=None,
                      nargs='*',
                      help='Driver command to parse')
  parser.add_argument('-f',
                      '--file_name',
                      dest='file_name',
                      default=None,
                      help='Path to file containing driver commands')
  parser.add_argument('--fdb_filename',
                      dest='fdb_filename',
                      default=None,
                      help='Path to the fdb filename to parse')
  args = parser.parse_args()

  if args.file_name:  # a file was supplied and no driver commands on the command line
    if args.driver_cmd:
      LOGGER.error('driver commands cannot be specified when filename is given')

    infile = open(os.path.expanduser(args.file_name), "r")
    args.driver_cmd = []
    for cmd in infile:
      if 'conv' in cmd:
        args.driver_cmd.append(cmd)
  return args


def print_alchemy_results(results):
  """ Utility function to print results from SQLAlchemy """
  if not results:
    return False
  for kinder in results:
    labels = kinder.keys()
    for idx, item in enumerate(kinder):
      dkt = {
          labels[idx] + '.' + k: str(v)
          for k, v in item.__dict__.items()
          if k[0] != '_'
      }
      print(dkt, end='')
    print(' ')
    print('-' * 80)
  return True


def print_results(db_cursor):
  """Helper function to print results"""
  widths = []
  columns = []
  tavnit = '|'
  separator = '+'
  results = db_cursor.fetchall()

  if not results:
    print('Config not found')
    return False

  for index, cd_var in enumerate(db_cursor.description):
    max_col_length = max(
        list(map(lambda x, idx=index: len(str(x[idx])), results)))
    widths.append(max(max_col_length, len(cd_var[0])))
    columns.append(cd_var[0])

  for width in widths:
    tavnit += " %-" + "%ss |" % (width,)
    separator += '-' * width + '--+'

  print(separator)
  print(tavnit % tuple(columns))
  print(separator)
  for row in results:
    print(tavnit % row)
  print(separator)
  return True


def parse_fdb_value(val):
  """ Helper function to parse FDB values """
  lst = val.split(';')
  res = []
  for kinder in lst:
    algo, specs = kinder.split(':')
    solver, kernel_time, wksp_size, _, _ = specs.split(',')
    res.append((algo, solver, kernel_time, wksp_size))
  res = sorted(res, key=lambda x: float(x[2]))
  return res


def print_fdb_res(prefix, fdb_store, key):
  """ Helper function to print FDB results """
  fdb = fdb_store.get(key, None)
  if fdb:
    vals = parse_fdb_value(fdb)[0]
    print('{}:{}: Algo: {}, Solver: {}, Kernel_Time: {}, "\
      "Workspace_Size: {} '.format(prefix, key, vals[0], vals[1], vals[2],
                                   vals[3]))
  else:
    print('{}:{}: Key Not present'.format(prefix, key))


def dev_fil_query(query, args, table):
  """ Filter query for device characteristics (arch, num_cu) """
  if args.arch:
    query = query.filter(table.arch == args.arch)
  if args.num_cu:
    query = query.filter(table.num_cu == args.num_cu)
  return query


def main():
  """Main module function"""
  args = parse_args()
  fdb_store = {}
  if args.fdb_filename:
    fdbfile = open(os.path.expanduser(args.fdb_filename), "r")
    for line in fdbfile:
      if not line:
        continue
      lst = line.split('=')
      if len(lst) == 2:
        key, value = lst
        fdb_store[key] = value.strip()
      else:
        print('WARNING: Ill formed fdb line; ', line)

  for cmd in args.driver_cmd:
    main_impl(args, cmd, fdb_store)


def main_impl(args, cmd, fdb_store):
  """ Implementation of main functionality """
  print('*' * 80)
  print(cmd.strip())
  print('*' * 80)
  fds, precision, _ = get_fds_from_cmd(cmd)
  if not args.skip_db:
    if args.job_info:
      with DbSession() as session:
        query = session.query(
            ConvolutionJob, ConvolutionConfig).filter(ConvolutionJob.valid == 1)
        query = dev_fil_query(query, args, ConvolutionJob)
        for attr, value in fds.items():
          query = query.filter(getattr(ConvolutionConfig, attr) == value)
        query = query.filter(ConvolutionConfig.id == ConvolutionJob.config)
        if not print_alchemy_results(query.all()):
          print('No ConvolutionJob results')

    if args.fdb_info:
      for fdb_key in [
          get_pdb_key(fds, precision, 'F'),
          get_pdb_key(fds, precision, 'B'),
          get_pdb_key(fds, precision, 'W')
      ]:
        with DbSession() as session:
          query = session.query(ConvolutionFindDB).filter(ConvolutionFindDB.fdb_key == fdb_key, \
                                               ConvolutionFindDB.valid == 1)
          query = dev_fil_query(query, args, ConvolutionFindDB)
          if not print_alchemy_results(query.all()):
            print('No ConvolutionFindDB results')

  if cmd.find('=') != -1:
    print(fds)
  else:
    print_fdb_res('PDB Key(Forward):          ', fdb_store,
                  get_pdb_key(fds, precision, 'F'))
    print_fdb_res('PDB Key(Backward-Data):    ', fdb_store,
                  get_pdb_key(fds, precision, 'B'))
    print_fdb_res('PDB Key(Backward-Weights): ', fdb_store,
                  get_pdb_key(fds, precision, 'W'))


if __name__ == '__main__':
  main()
