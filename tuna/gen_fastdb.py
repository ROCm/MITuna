import os
import pdb
import argparse

from tuna.utils import logging
import tuna.utils.tools.df as df_tools
import tuna.utils.tools.io as io_tools
from tuna.gen_finddb import load_findDB
from tuna.utils.db_utility import get_id_solvers
from tuna.utils.ANSI_formatting import ANSIColors
from tuna.utils.finddb_like_utils import get_solver_counts
from tuna.utils.helpers import print_heading, filter_out, map_list, \
  is_substr, invert_dict, pretty_list, sort_dict, as_heading

_DEFAULT_INPUT_DIR = os.path.join(os.getcwd(), 'findDB_')
_DEFAULT_OUTPUT_DIR = os.path.join(os.getcwd(), 'findDB_')

_, _ID_TO_SOLVER = get_id_solvers()
_SOLVER_TO_ID = invert_dict(_ID_TO_SOLVER)


def check_findDB(findDB, cols_with_conv_params=['fdb_key'], strict=False):
  NO_ENTRIES, INVALID_ENTRIES, OPENCL_ON, MULTIPLE_SESSIONS, DUPLICATE_ENTRIES = 0, 1, 2, 3, 7
  issues = []

  if len(findDB) == 0:
    if strict:
      raise AssertionError(f'FindDB contains no entry')
    else:
      logging.error(f'FindDB contains no entry')
      issues.append(NO_ENTRIES)

  if (findDB['valid'] != 1).any():
    if strict:
      raise AssertionError(f'FindDB contains invalid entries')
    else:
      logging.warning(f'FindDB contains invalid entries')
      issues.append(INVALID_ENTRIES)

  if findDB['opencl'].any():
    if strict:
      raise AssertionError(f'there are kernels with opencl enabled in FindDB')
    else:
      logging.warning(f'there are kernels with opencl enabled in FindDB')
      issues.append(OPENCL_ON)

  if not df_tools.is_col_unique(findDB, col_name='session'):
    if strict:
      raise AssertionError(
          f'data from multiple tuning sessions present in the FindDB')
    else:
      logging.warning(
          f'data from multiple tuning sessions present in the FindDB')
      issues.append(MULTIPLE_SESSIONS)

  num_duplicates = findDB.duplicated(subset=cols_with_conv_params +
                                     ['solver']).sum()
  if num_duplicates > 0:
    duplicates = findDB[findDB.duplicated(subset=cols_with_conv_params +
                                          ['solver'],
                                          keep=False)]
    duplicates = duplicates.sort_values(cols_with_conv_params +
                                        ['solver', 'kernel_time'])
    duplicates = duplicates.groupby(cols_with_conv_params + ['solver'])

    max_duplicates_to_print = 10
    duplicates_str = as_heading("Duplicates") + '\n'
    for i, (_, df) in enumerate(duplicates):
      for j, (row_id, row) in enumerate(df.iterrows()):
        conv_params_str = "+ " if i % 2 == 0 else "- "
        for colname, val in zip(cols_with_conv_params,
                                row[cols_with_conv_params]):
          conv_params_str += f'{colname} {val}, '
        duplicates_str += f"{conv_params_str}\n  solver: {row['solver']},  kernel_time: {row['kernel_time']}\n\n"

        if j == max_duplicates_to_print - 1:
          duplicates_str += "(truncated)"

      if i == max_duplicates_to_print - 1:
        duplicates_str += f"more duplicates present. displaying only {max_duplicates_to_print} here"

    if strict:
      logging.log(duplicates_str, silent=True)
      raise AssertionError(
          f'{num_duplicates} duplicate entries detected in FindDB')
    else:
      logging.warning(f'{num_duplicates} duplicate entries delected in FindDB')
      logging.log(duplicates_str)
      issues.append(DUPLICATE_ENTRIES)

  return issues


def describe_fastDB(fastDB):
  if len(fastDB) == 0:
    logging.warning('FastDB empty!')
  else:
    logging.info(f'Total entries in FastDB (=unique configs in FindDB): %d' %
                 len(fastDB))
    logging.info(f'Number of unique solvers in FastDB: %d' %
                 len(fastDB['solver'].unique()))


def load_fastDB(fastDB_pickle_filename):
  fastDB = io_tools.safe_load(None, fastDB_pickle_filename,
                              df_tools.from_pickle)
  describe_fastDB(fastDB)
  return fastDB


def findDB_to_nonthresholded_fastDB(findDB,
                                    cols_with_conv_params=['fdb_key'],
                                    n_fastest=1):
  num_duplicates = findDB.duplicated(subset=cols_with_conv_params +
                                     ['solver']).sum()
  if num_duplicates > 0:
    logging.warning( f'{num_duplicates} duplicate (fdb_key, solver)' +\
            ' pairs in FindDB: resolved them by keeping one with fastest solver' )
  sorted_findDB = findDB.sort_values(cols_with_conv_params + ['kernel_time'])
  return sorted_findDB.groupby(cols_with_conv_params).head(n_fastest)


def is_fundamental_solver(solver):
  """defines fundamental solvers"""

  def is_explicit_gemm(solver):
    return is_substr('Gemm', solver) and not is_substr('ImplicitGemm', solver)

  def is_naive(solver):
    return is_substr('Naive', solver)

  return is_explicit_gemm(solver) or is_naive(solver)


def gen_fastDB(findDB, threshold=0, keep_fundamental=False):
  check_findDB(findDB)

  logging.log('getting fastest solvers per config...', end_char='\r')
  fastDB = findDB_to_nonthresholded_fastDB(findDB)
  logging.reset_line()

  if threshold > 0:
    findDB_solver_counts = sort_dict(get_solver_counts(findDB))
    fastDB_solver_counts = sort_dict(get_solver_counts(fastDB))

    logging.log('determining solvers below threshold...', end_char='\r')
    solvers_below_threshold = []
    for solver in findDB_solver_counts:
      if solver in fastDB_solver_counts:
        ratio_in_fastDB = fastDB_solver_counts[solver] / sum(
            fastDB_solver_counts.values())
      else:
        ratio_in_fastDB = 0

      if ratio_in_fastDB < (threshold / 100):
        solvers_below_threshold.append(solver)

    logging.reset_line()
    if len(solvers_below_threshold) == 0:
      logging.warning(
          'threshold too loose: none of the solvers are below threshold')
    else:
      if keep_fundamental:
        logging.log('removing non-fundamental solvers below threshold...',
                    end_char='\r')
        solvers_to_remove = filter_out(solvers_below_threshold,
                                       is_fundamental_solver)
      else:
        logging.log('removing all solvers below threshold...', end_char='\r')
        solvers_to_remove = solvers_below_threshold

      solver_ids_to_remove = map_list(solvers_to_remove, _SOLVER_TO_ID)
      thresholded_findDB = findDB[~findDB['solver'].isin(solver_ids_to_remove)]
      thresholded_fastDB = findDB_to_nonthresholded_fastDB(thresholded_findDB)

      logging.reset_line()
      logging.success('fastDB generated!')
      describe_fastDB(thresholded_fastDB)

      # print summary
      print_heading('SUMMARY', printer=logging.log)
      n = max(len(solver) for solver in findDB_solver_counts)
      m = len('BELOW-THRESHOLD')
      for solver in findDB_solver_counts:
        flagA = 'BELOW-THRESHOLD' if solver in solvers_below_threshold else ''
        flagB = 'FUNDAMENTAL' if is_fundamental_solver(solver) else ''
        string = f'{solver}'.ljust(n + 3) + f'{flagA}'.ljust(m + 3) + f'{flagB}'
        if solver in solvers_to_remove:
          logging.log('- ' + string, formatting=ANSIColors.red)
        else:
          logging.log('+ ' + string)
      logging.log(
          'solver names with a "-" infront got replaced (where a replacement was available)'
      )

      return thresholded_fastDB

  logging.success('fastDB generated!')
  describe_fastDB(fastDB)
  return fastDB


if __name__ == '__main__':
  default_in_filename = os.path.join(_DEFAULT_INPUT_DIR, 'findDB.pkl')
  default_out_dirname = _DEFAULT_OUTPUT_DIR

  parser = argparse.ArgumentParser(description='Generate FastDB from FindDB')
  parser.add_argument(
      '-i',
      '--in',
      type=str,
      default=default_in_filename,
      dest='input',
      help=
      f'filename for the pickled FindDB Pandas dataframe (current: {default_in_filename})'
  )
  parser.add_argument(
      '-o',
      '--out',
      type=str,
      default=default_out_dirname,
      dest='output',
      help=
      f'dir to output the pickled FastDB Pandas dataframe to (current: {default_out_dirname})'
  )
  parser.add_argument(
      '-t',
      '--threshold',
      type=float,
      default=0,
      dest='threshold',
      help=
      f'replace all solvers w/ lesser frequency than the threshold (default: 0)'
  )
  parser.add_argument(
      '--keep_fundamental',
      action='store_true',
      default=False,
      dest='keep_fundamental',
      help=
      f'specify this flag to keep the fundamental solvers despite them being infrequent'
  )

  args = parser.parse_args()

  findDB = load_findDB(args.input)
  fastDB = gen_fastDB(findDB, args.threshold, args.keep_fundamental)

  io_tools.safe_save(fastDB, os.path.join(args.output, 'fastDB.pkl'),
                     df_tools.to_pickle)
  logging.dump_logs(os.path.join(args.output, 'gen_fastdb.log'))
