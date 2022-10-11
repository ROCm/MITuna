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
"""generates analytics pertaining to the solvers in finddb.

finddb contains various convolution problems and the different solvers that can
be used to solve them, along with those solvers' runtime. this script analyses this
data to generate:
(1) what solvers are present in finddb
(2) how many convolution problems does each solver solve
(3) how many convolution problems is each solver the fastest solver for
(4) if solve a convolution problem by the second-fastest solver instead of the
    fastest one, how much slowdown would we incur

The above data is summarized in plots, and detailed records are available in
the corresponding csv files.
"""

import os
import argparse
from collections.abc import Iterable

import pandas as pd
import matplotlib.pyplot as plt

from tuna.utils import logging
import tuna.utils.tools.io as io_tools
import tuna.utils.tools.df as df_tools
from tuna.gen_finddb import FinddbParsing
from tuna.utils.History import History
import tuna.utils.tools.file as file_tools
import tuna.utils.tools.plot as plot_tools
from tuna.utils.progress_bars import ProgressBar
from tuna.utils.db_utility import get_id_solvers
from tuna.utils.fdb_key_utils import explode_fdb_keys
from tuna.utils.finddb_like_utils import get_solver_counts
from tuna.gen_finddb import gen_finddb, load_finddb, describe_finddb
from tuna.gen_fastdb import finddb_to_nonthresholded_fastdb, describe_fastdb, check_finddb
from tuna.utils.helpers import sort_dict, invert_dict, print_heading, print_dict_as_table, \
    dict_to_csv, print_title, map_list, proper_dict_of_dicts_to_csv, wierd_ratio, \
    pretty_iterator

_DEFAULT_OUTPUT_DIR = os.path.join(os.getcwd(), 'finddb_')

_, _ID_TO_SOLVER = get_id_solvers()
_SOLVER_TO_ID = invert_dict(_ID_TO_SOLVER)

_DEBUG_FLAGS = {'SHORT_CIRCUIT_COMPREHENSIVE_STATS_CALCULATION': True}


# pylint: disable-next=too-few-public-methods
class SolverCountsWriter():
  """writes solver counts to a csv

  Attributes:
    choice: a dictionary-like object mapping convolution parameters to their values
    sep: seperator to use in csv
  """

  def __init__(self, choice, sep=","):
    self.choice = choice
    self.sep = str(sep)
    divider = "" if len(choice) == 0 else self.sep
    self.header = self.sep.join(
        (str(key)
         for key, val in choice.items())) + divider + f"solver{self.sep}count"
    self.prefix = self.sep.join(
        (f"{val}" for key, val in choice.items())) + divider

  def __call__(self, solver_counts, filename):
    """dump solver counts to csv file

    the csv file will look like:

               convolution params
                       |
    |^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^|
     InputDim0, InputDim1, InputDim2, ...,  solver,   count
     64,        64,        64,        ...,  Naive,    77
     64,        32,        32,        ...,  ConvASM,  23
      :          :          :         ...     :        :

    Attributes:
      solver_counts: a dictionary mapping solvers to their counts
      filename: csv filename
    """
    solver_counts_csv = self.header
    for solver, count in solver_counts.items():
      solver_counts_csv += f"\n{self.prefix}{solver}{self.sep}{count}"
    file_tools.write(solver_counts_csv, filename)


class StatsEntry(History):
  """History object for tracking of slowdown analytics

  Each event in this history corresponds to the slowdown resulting from replacing
  the fastest_solver for some convolution problem by some alternate_solver. The
  slowdown is reported in terms of the time difference in absolute units, and the
  relative time increase.

  Attributes:
    title: the title of the history, e.g. "Slowdown from replacing Solver A"
  """
  conv_params_names = []

  def __init__(self, title):
    super().__init__(*StatsEntry.conv_params_names,
                     'time_diff',
                     'time_ratio',
                     'alternate_solver',
                     title=title,
                     track_stats='auto')


def parse_stats_table(d, out_dir, verbosity=0):  # pylint: disable=invalid-name
  """parses the solver statistics table into a detailed slowdown analysis

  d: Solvers x Solvers x {'concise', 'comprehensive'} -> union(H, {<H_i>}),
  where `union(H, {<H_i>})`` is the set of StatsEntry objects and sequences of
  finitely many StatsEntry objects.

  d[si][sj]['comprehensive'][k] gives you the sequence of all the convolution
  problems in finddb for which `si` is the fastest solver and `sj` is the
  kth fastest solver.

  d[si][sj]['concise'] = union(d[si][sj]['comprehensive'][k]) over all k

  E.G.
  `d[si][sj]['comprehensive'][k].time_diff` will tell you how much of a slowdown is
  incurred on all convolution problems solvable by both si and sj, when sj, the kth
  fastest solver for those problems, is used to solve them instead of si -- the fastest
  solver for those problems.

  Use `d[si][sj]['comprehensive'][k].field_names` to see what data, besides `time_diff`,
  is available.

  Attributes:
    d: solver statistics dictionary
    verbosity: controls the level-of-detail of analytics
  """
  for si in d:  # pylint: disable=invalid-name
    si_name = _ID_TO_SOLVER[si]
    si_replacement_stats = StatsEntry(title=si)
    for sj in d[si]:  # pylint: disable=invalid-name
      sj_name = _ID_TO_SOLVER[sj]
      si_replacement_stats.extend(d[si][sj]['comprehensive'][0])
      if verbosity >= 1:
        if len(d[si][sj]['comprehensive'][0]) == 0:
          logging.warning(
              f'no stats: solver {sj} is never the next best alternative to {si}.'
              'dumping empty files...')
        d[si][sj]['comprehensive'][0].to_csv(
            filename=os.path.join(out_dir, f'{si}', f'{si}_{sj}.csv'))
        d[si][sj]['comprehensive'][0].plot(filename=os.path.join(
            out_dir, f'{si}', f'{si}_{sj}.png'),
                                           title=f'{si_name} -> {sj_name}',
                                           min_unique_entries=1)

    if len(si_replacement_stats) == 0:
      logging.warning(
          f'no stats: problems that {si} solves best have no alternate solver for.'
          'dumping empty files...')

    si_replacement_stats.to_csv(filename=os.path.join(out_dir, f'{si}.csv'))
    si_replacement_stats.plot(
        filename=os.path.join(out_dir, f'{si}.png'),
        title=f'{si_name} replaced by next fastest alternative',
        min_unique_entries=1)
    io_tools.safe_save(si_replacement_stats.get_stats(),
                       os.path.join(out_dir, f'{si}_overall.csv'),
                       proper_dict_of_dicts_to_csv)


# pylint: disable-next=too-many-locals, too-many-statements
def analyze_explodedfinddb(explodedfinddb,
                           cols_with_conv_params,
                           out_dirname,
                           verbosity=0,
                           solver_counts_writer=dict_to_csv):
  """analyze finddb

  Attributes:
    explodedfinddb: finddb with finddb['fdb_key'] exploded into tokens
    cols_with_conv_params: names of explodedfinddb columns that contain convolution
                           parameters
    out_dirname: directory to dump results in
    verbosity: level-of-detail of analytics
    solver_counts_writer: a callable that takes in a dictionary (representing solver
                          counts) and a path, and writes the dictionary to the
                          file at the path
  """
  logging.log('computing solver counts...')

  solver_counts = get_solver_counts(explodedfinddb)

  check_finddb(explodedfinddb, cols_with_conv_params=cols_with_conv_params)
  explodedfastdb = finddb_to_nonthresholded_fastdb(explodedfinddb,
                                                   cols_with_conv_params)
  describe_fastdb(explodedfastdb)

  fastest_solver_counts = get_solver_counts(explodedfastdb)

  fastest_solver_counts_verbose = {}
  for solver in solver_counts:
    if solver in fastest_solver_counts:
      fastest_solver_counts_verbose[solver] = fastest_solver_counts[solver]
    else:
      fastest_solver_counts_verbose[solver] = 0
  fastest_solver_counts_verbose = sort_dict(fastest_solver_counts_verbose)

  # compute slowdown stats
  StatsEntry.conv_params_names = cols_with_conv_params

  solver_ids = map_list(solver_counts.keys(), _SOLVER_TO_ID)
  stats_table = {
      si: {
          sj: {
              'concise':
                  StatsEntry(title='concise'),
              'comprehensive': [
                  StatsEntry(title=i) for i in range(1, len(solver_counts))
              ]
          } for sj in solver_ids
      } for si in solver_ids
  }

  temp = explodedfinddb.sort_values(cols_with_conv_params + ['kernel_time'])
  sorted_explodedfinddb = temp.drop_duplicates(cols_with_conv_params +
                                               ['solver'],
                                               keep='first')
  if len(sorted_explodedfinddb) < len(temp):
    logging.warning(f'{len(temp)-len(sorted_explodedfinddb)} duplicate (fdb_key, solver)' +\
            ' pairs in finddb: resolved them by keeping one with fastest solver')

  # pylint: disable-next=unnecessary-lambda-assignment; for clarity
  to_numeric_where_possible = lambda arg: pd.to_numeric(arg, errors='ignore')
  sorted_explodedfinddb_numeric = sorted_explodedfinddb.apply(
      to_numeric_where_possible)
  sorted_explodedfinddb_numeric_grouped = sorted_explodedfinddb_numeric.groupby(
      cols_with_conv_params)

  progressbar = ProgressBar(end_val=len(sorted_explodedfinddb_numeric),
                            title='COLLECTING SLOWDOWN STATS')
  entries_processed = 0
  for _, df in sorted_explodedfinddb_numeric_grouped:  # pylint: disable=invalid-name
    fastest = df.iloc[0, :]
    conv_params = fastest[cols_with_conv_params].to_dict()
    entries_processed += 1
    for i in range(1, len(df)):
      alternate = df.iloc[i, :]
      stats_entry_concise = stats_table[fastest['solver']][
          alternate['solver']]['concise']
      stats_entry_comprehensive = stats_table[fastest['solver']][
          alternate['solver']]['comprehensive'][i - 1]

      for stats_entry in [stats_entry_concise, stats_entry_comprehensive]:
        stats_entry.add(
            **conv_params,
            time_diff=alternate['kernel_time'] - fastest['kernel_time'],
            time_ratio=wierd_ratio(alternate['kernel_time'],
                                   fastest['kernel_time']),
            alternate_solver=alternate['solver'],
        )

      entries_processed += 1
      progressbar.display(progress=entries_processed)

      if _DEBUG_FLAGS['SHORT_CIRCUIT_COMPREHENSIVE_STATS_CALCULATION']:
        entries_processed += len(df) - 2
        break

  # logging/dumping solver counts results
  if len(solver_counts) > 0:
    print_heading('SOLVER COUNTS', printer=logging.log)
    print_dict_as_table(solver_counts, printer=logging.log)

  io_tools.safe_save(solver_counts,
                     os.path.join(out_dirname, 'solver_counts.csv'),
                     solver_counts_writer)

  x = [_SOLVER_TO_ID[solver] for solver in solver_counts]  # pylint: disable=invalid-name
  y = solver_counts.values()  # pylint: disable=invalid-name
  plt.bar(range(len(y)), y, align='center', color='black', edgecolor='black')
  plt.title('Times each solver occurs in the dataset')
  plt.xlabel('Solver ID')
  plt.xticks(range(len(y)), labels=x, rotation='vertical', fontsize=7)
  io_tools.safe_save(plt, os.path.join(out_dirname, 'solver_histogram.png'),
                     plot_tools.save)
  plt.close('all')

  # logging/dumping fastest solver counts results
  if len(fastest_solver_counts_verbose) > 0:
    print_heading('FASTEST SOLVER COUNTS', printer=logging.log)
    print_dict_as_table(fastest_solver_counts_verbose, printer=logging.log)

  io_tools.safe_save(fastest_solver_counts_verbose,
                     os.path.join(out_dirname, 'fastest_solver_counts.csv'),
                     solver_counts_writer)

  # pylint: disable-next=invalid-name
  x = [_SOLVER_TO_ID[solver] for solver in fastest_solver_counts_verbose]
  y = fastest_solver_counts_verbose.values()  # pylint: disable=invalid-name
  plt.bar(range(len(y)), y, align='center', color='black', edgecolor='black')
  plt.title('Times each solver occurs as the fastest solver in the dataset')
  plt.xlabel('Solver ID')
  plt.xticks(range(len(y)), labels=x, rotation='vertical', fontsize=7)
  io_tools.safe_save(plt,
                     os.path.join(out_dirname, 'fastest_solver_histogram.png'),
                     plot_tools.save)
  plt.close('all')

  # dumping the _ID_TO_SOLVER map for easy lookup
  io_tools.safe_save(_ID_TO_SOLVER,
                     os.path.join(out_dirname, 'id_to_solver_map.csv'),
                     dict_to_csv)

  # parse stats_table and log/dump results
  parse_stats_table(stats_table,
                    os.path.join(out_dirname, 'slowdown_analysis'),
                    verbosity=verbosity)


def to_explodedfinddb(finddb, direction=None, layout=None, precision=None):
  """ converts finddb to explodedfinddb

  explodedfinddb is generated by exploding the 'fdb_key' column in finddb
  into the respective tokens

  Attributes:
    finddb: pandas finddb
    direction: if specified, explodedfinddb will only contain entries with this direction
    layout: if specified, explodedfinddb will only contain entries with this layout
    precision: if specified, explodedfinddb will only contain entries with this precision

  Return:
    explodedfinddb: the explodedfinddb dataframe
    cols_with_conv_params: names of explodedfinddb columns containing the
                           convolution parameters
  """
  exploded_fdb_keys = explode_fdb_keys(finddb['fdb_key'])
  rest_of_finddb = finddb.loc[:, finddb.columns != 'fdb_key']
  explodedfinddb = df_tools.combine(exploded_fdb_keys, rest_of_finddb)

  cols_with_conv_params = list(exploded_fdb_keys.columns)

  if direction is not None:
    explodedfinddb = df_tools.select(explodedfinddb, 'Direction', direction)
  if layout is not None:
    explodedfinddb = df_tools.select(explodedfinddb, 'Layout', layout)
  if precision is not None:
    explodedfinddb = df_tools.select(explodedfinddb, 'Precision', precision)

  return explodedfinddb, cols_with_conv_params


def set_explodedfinddb_args(parser):
  """sets arguments to allow one to specify convolution parameters

  Attributes:
    parser: a parser object
  """
  parser.add_argument('--direction',
                      type=str,
                      default=None,
                      help='convolution direction (default: all directions)',
                      choices=['F', 'B', 'W'])
  parser.add_argument('--layout',
                      type=str,
                      default=None,
                      help='tensor layout (default: all layouts)')
  parser.add_argument('--precision',
                      type=str,
                      default=None,
                      help='precision (default: all precisions)')


def main():
  """ main """
  default_out_dirname = _DEFAULT_OUTPUT_DIR

  parser = argparse.ArgumentParser(
      description='Analyzes finddb and dumps solver statistics')

  parser.add_argument(
      '-o',
      '--out',
      type=str,
      default=default_out_dirname,
      help=f'directory to output statistics results to {default_out_dirname})')
  parser.add_argument('-i', '--in', type=str, default=None, dest='input',
                      help='filename for finddb pickle (default: None). \n' +\
                      'Note: This overrides the finddb flags for fetching finddb from the database')
  parser.add_argument(
      '-v',
      '--verbosity',
      type=int,
      default=0,
      help='higher verbosity => more logs and files dumped (current: 0)',
      choices=[0, 1])
  FinddbParsing.set_finddb_args(parser)
  set_explodedfinddb_args(parser)

  args = parser.parse_args()

  if args.session_ids is None:
    analyzed_finddb_dir = os.path.join(args.out, 'analysis')
  if isinstance(args.session_ids, Iterable):
    analyzed_finddb_dir = os.path.join(
        args.out, f'analysis_{pretty_iterator(args.session_ids, sep="_")}')
  else:
    analyzed_finddb_dir = os.path.join(args.out, f'analysis_{args.session_ids}')

  if args.input is not None:
    finddb = load_finddb(args.input)
  else:
    finddb = gen_finddb(**FinddbParsing.get_finddb_args(args))

  explodedfinddb, cols_with_conv_params = to_explodedfinddb(
      finddb, args.direction, args.layout, args.precision)

  choices = df_tools.unique_combinations(explodedfinddb[[
      'Direction', 'Layout', 'Precision', 'FilterDim0', 'FilterDim1',
      'FilterDim2', 'Padding0', 'Padding1', 'Padding2', 'Stride0', 'Stride1',
      'Stride2', 'Dilation0', 'Dilation1', 'Dilation2'
  ]])

  for choice in choices:
    main_dir_name = f"{choice['Direction']}_{choice['Layout']}_{choice['Precision']}"
    sub_dir_name = f"F{choice['FilterDim0']}x{choice['FilterDim1']}x{choice['FilterDim2']}_" +\
            f"P{choice['Padding0']}x{choice['Padding1']}x{choice['Padding2']}_" +\
            f"S{choice['Stride0']}x{choice['Stride1']}x{choice['Stride2']}_" +\
            f"D{choice['Dilation0']}x{choice['Dilation1']}x{choice['Dilation2']}"
    out_dir = os.path.join(analyzed_finddb_dir, main_dir_name, sub_dir_name)

    logging.log(main_dir_name + ' :: ' + sub_dir_name, print_title)
    M = df_tools.select_multiple(explodedfinddb, choice)  # pylint: disable=invalid-name
    describe_finddb(M)
    analyze_explodedfinddb(M,
                           cols_with_conv_params,
                           out_dir,
                           verbosity=args.verbosity,
                           solver_counts_writer=SolverCountsWriter(choice))

    io_tools.safe_save(M, os.path.join(out_dir, 'explodedfinddb.pkl'),
                       df_tools.to_pickle)

  logging.dump_logs(os.path.join(analyzed_finddb_dir, 'analyze_finddb.log'))


if __name__ == '__main__':
  main()
