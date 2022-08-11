import os
import sys
import time
import argparse
import pandas as pd
import matplotlib.pyplot as plt
from collections.abc import Iterable

from tuna.utils import logging
import tuna.utils.tools.io as io_tools
import tuna.utils.tools.df as df_tools
from tuna.gen_finddb import FindDBParsing
from tuna.utils.History import History
import tuna.utils.tools.file as file_tools
import tuna.utils.tools.plot as plot_tools
from tuna.utils.ANSI_formatting import ANSITools
from tuna.utils.progress_bars import ProgressBar
from tuna.utils.db_utility import get_id_solvers
from tuna.utils.fdb_key_utils import explode_fdb_keys
from tuna.utils.finddb_like_utils import get_solver_counts
from tuna.gen_finddb import gen_findDB, load_findDB, describe_findDB
from tuna.gen_fastdb import findDB_to_nonthresholded_fastDB, describe_fastDB, check_findDB
from utils.helpers import sort_dict, invert_dict, print_heading, print_dict_as_table, dict_to_csv, \
    print_title, map_list, proper_dict_of_dicts_to_csv, wierd_ratio, nest, pretty_iterator

_DEFAULT_OUTPUT_DIR = os.path.join(os.getcwd(), 'findDB_')

_, _ID_TO_SOLVER = get_id_solvers()
_SOLVER_TO_ID = invert_dict(_ID_TO_SOLVER)

_DEBUG_FLAGS = {'SHORT_CIRCUIT_COMPREHENSIVE_STATS_CALCULATION': True}


class SolverCountsWriter():

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
    solver_counts_csv = self.header
    for solver, count in solver_counts.items():
      solver_counts_csv += f"\n{self.prefix}{solver}{self.sep}{count}"
    file_tools.write(solver_counts_csv, filename)


class StatsEntry(History):
  conv_params_names = []

  def __init__(self, title):
    super().__init__(*StatsEntry.conv_params_names,
                     'time_diff',
                     'time_ratio',
                     'alternate_solver',
                     title=title,
                     track_stats='auto')


def parse_stats_table(d, out_dir, verbosity=0):
  """
  d: solvers x solvers x {'concise', 'comprehensive'} -> union(H, {<H_i>}),
  where `union(H, {<H_i>})`` is the set of StatsEntry objects and sequences of
  finitely many StatsEntry objects.
  
  d[si][sj]['comprehensive'][k] gives you the sequence of all the convolution
  problems in FindDB for which `si` is the fastest solver and `sj` is the
  kth fastest solver. 

  d[si][sj]['concise'] = union(d[si][sj]['comprehensive'][k]) over all k 

  E.G.
  `d[si][sj]['comprehensive'][k].time_diff` will tell you how much of a slowdown is 
  incurred on all convolution problems solvable by both si and sj, when sj, the kth 
  fastest solver for those problems, is used to solver them instead of si (the fastest
  solver for those problems).

  Use `d[si][sj]['comprehensive'][k].field_names` to see what data, besides `time_diff`,
  is available.
  """
  for i, si in enumerate(d):
    si_name = _ID_TO_SOLVER[si]
    si_replacement_stats = StatsEntry(title=si)
    for j, sj in enumerate(d[si]):
      sj_name = _ID_TO_SOLVER[sj]
      si_replacement_stats.extend(d[si][sj]['comprehensive'][0])
      if verbosity >= 1:
        if len(d[si][sj]['comprehensive'][0]) == 0:
          logging.warning(
              f'no stats: solver {sj} is never the next best alternative to {si}. dumping empty files...'
          )
        d[si][sj]['comprehensive'][0].to_csv(
            filename=os.path.join(out_dir, f'{si}', f'{si}_{sj}.csv'))
        d[si][sj]['comprehensive'][0].plot(filename=os.path.join(
            out_dir, f'{si}', f'{si}_{sj}.png'),
                                           title=f'{si_name} -> {sj_name}',
                                           min_unique_entries=1)

    if len(si_replacement_stats) == 0:
      logging.warning(
          f'no stats: problems that {si} solves best have no alternate solver for. dumping empty files...'
      )

    si_replacement_stats.to_csv(filename=os.path.join(out_dir, f'{si}.csv'))
    si_replacement_stats.plot(
        filename=os.path.join(out_dir, f'{si}.png'),
        title=f'{si_name} replaced by next fastest alternative',
        min_unique_entries=1)
    io_tools.safe_save(si_replacement_stats.get_stats(),
                       os.path.join(out_dir, f'{si}_overall.csv'),
                       proper_dict_of_dicts_to_csv)


def analyze_explodedFindDB(explodedFindDB,
                           cols_with_conv_params,
                           out_dirname,
                           verbosity=0,
                           solver_counts_writer=dict_to_csv):
  logging.log('computing solver counts...')

  solver_counts = get_solver_counts(explodedFindDB)

  check_findDB(explodedFindDB, cols_with_conv_params=cols_with_conv_params)
  explodedFastDB = findDB_to_nonthresholded_fastDB(explodedFindDB,
                                                   cols_with_conv_params)
  describe_fastDB(explodedFastDB)

  fastest_solver_counts = get_solver_counts(explodedFastDB)

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

  temp = explodedFindDB.sort_values(cols_with_conv_params + ['kernel_time'])
  sorted_explodedFindDB = temp.drop_duplicates(cols_with_conv_params +
                                               ['solver'],
                                               keep='first')
  if len(sorted_explodedFindDB) < len(temp):
    logging.warning( f'{len(temp)-len(sorted_explodedFindDB)} duplicate (fdb_key, solver)' +\
            ' pairs in FindDB: resolved them by keeping one with fastest solver' )

  to_numeric_where_possible = lambda arg: pd.to_numeric(arg, errors='ignore')
  sorted_explodedFindDB_numeric = sorted_explodedFindDB.apply(
      to_numeric_where_possible)
  sorted_explodedFindDB_numeric_grouped = sorted_explodedFindDB_numeric.groupby(
      cols_with_conv_params)

  progressbar = ProgressBar(end_val=len(sorted_explodedFindDB_numeric),
                            title='COLLECTING SLOWDOWN STATS')
  entries_processed = 0
  for _, df in sorted_explodedFindDB_numeric_grouped:
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

  x = [_SOLVER_TO_ID[solver] for solver in solver_counts]
  y = solver_counts.values()
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

  x = [_SOLVER_TO_ID[solver] for solver in fastest_solver_counts_verbose]
  y = fastest_solver_counts_verbose.values()
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


def to_explodedFindDB(findDB, direction=None, layout=None, precision=None):
  exploded_fdb_keys = explode_fdb_keys(findDB['fdb_key'])
  rest_of_findDB = findDB.loc[:, findDB.columns != 'fdb_key']
  explodedFindDB = df_tools.combine(exploded_fdb_keys, rest_of_findDB)

  cols_with_conv_params = [x for x in exploded_fdb_keys.columns]

  if direction is not None:
    explodedFindDB = df_tools.select(explodedFindDB, 'Direction', direction)
  if layout is not None:
    explodedFindDB = df_tools.select(explodedFindDB, 'Layout', layout)
  if precision is not None:
    explodedFindDB = df_tools.select(explodedFindDB, 'Precision', precision)

  return explodedFindDB, cols_with_conv_params


def set_explodedFindDB_args(parser):
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


if __name__ == '__main__':
  default_out_dirname = _DEFAULT_OUTPUT_DIR

  parser = argparse.ArgumentParser(
      description='Fetches FindDB and exports it as a Pandas DataFrame')

  parser.add_argument(
      '-o',
      '--out',
      type=str,
      default=default_out_dirname,
      help=
      f'directory for the output pickled Pandas Dataframe (current: {default_out_dirname})'
  )
  parser.add_argument('-i', '--in', type=str, default=None, dest='input',
      help=f'filename for findDB pickle (default: None). \n' +\
      'Note: This overrides the findDB flags for fetching findDB from the database')
  parser.add_argument('-v',
                      '--verbosity',
                      type=int,
                      default=0,
                      help='higher verbosity => more logs and files dumped',
                      choices=[0, 1])
  FindDBParsing.set_findDB_args(parser)
  set_explodedFindDB_args(parser)

  args = parser.parse_args()

  if args.session_ids is None:
    analyzed_findDB_dir = os.path.join(args.out, f'analysis')
  if isinstance(args.session_ids, Iterable):
    analyzed_findDB_dir = os.path.join(
        args.out, f'analysis_{pretty_iterator(args.session_ids, sep="_")}')
  else:
    analyzed_findDB_dir = os.path.join(args.out, f'analysis_{args.session_ids}')

  if args.input is not None:
    findDB = load_findDB(args.input)
  else:
    findDB = gen_findDB(**FindDBParsing.get_findDB_args(args))

  explodedFindDB, cols_with_conv_params = to_explodedFindDB(
      findDB, args.direction, args.layout, args.precision)

  choices = df_tools.unique_combinations(explodedFindDB[[
      'Direction', 'Layout', 'Precision', 'FilterDim0', 'FilterDim1',
      'FilterDim2', 'Padding0', 'Padding1', 'Padding2', 'Stride0', 'Stride1',
      'Stride2', 'Dilation0', 'Dilation1', 'Dilation2'
  ]])

  for choice in choices:
    main_dir_name = f"{choice['Direction']}_{choice['Layout']}_{choice['Precision']}"
    sub_dir_name  = f"F{choice['FilterDim0']}x{choice['FilterDim1']}x{choice['FilterDim2']}_" +\
            f"P{choice['Padding0']}x{choice['Padding1']}x{choice['Padding2']}_" +\
            f"S{choice['Stride0']}x{choice['Stride1']}x{choice['Stride2']}_" +\
            f"D{choice['Dilation0']}x{choice['Dilation1']}x{choice['Dilation2']}"
    out_dir = os.path.join(analyzed_findDB_dir, main_dir_name, sub_dir_name)

    logging.log(main_dir_name + ' :: ' + sub_dir_name, print_title)
    M = df_tools.select_multiple(explodedFindDB, choice)
    describe_findDB(M)
    analyze_explodedFindDB(M,
                           cols_with_conv_params,
                           out_dir,
                           verbosity=args.verbosity,
                           solver_counts_writer=SolverCountsWriter(choice))

    io_tools.safe_save(M, os.path.join(out_dir, 'explodedFindDB.pkl'),
                       df_tools.to_pickle)

  logging.dump_logs(os.path.join(analyzed_findDB_dir, 'analyze_finddb.log'))
