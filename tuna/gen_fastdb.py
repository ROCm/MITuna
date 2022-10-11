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
"""generate a fastdb dataframe from a finddb dataframe

finddb contains convolution problems and the solvers that solve them.
finddb may list multiple solvers per convolution problem, some solving the
problem faster than the others. fastdb is generated from finddb by looking
at each convolution problem in finddb and keeping only the fastest solver
for it.
"""

import os
import argparse
from enum import Enum

from tuna.utils import logging
import tuna.utils.tools.df as df_tools
import tuna.utils.tools.io as io_tools
from tuna.gen_finddb import load_finddb
from tuna.utils.db_utility import get_id_solvers
from tuna.utils.ANSI_formatting import ANSIColors
from tuna.utils.finddb_like_utils import get_solver_counts, log_duplicates
from tuna.utils.helpers import print_heading, filter_out, map_list, \
  is_substr, invert_dict, sort_dict

_DEFAULT_INPUT_DIR = os.path.join(os.getcwd(), 'finddb_')
_DEFAULT_OUTPUT_DIR = os.path.join(os.getcwd(), 'finddb_')

_, _ID_TO_SOLVER = get_id_solvers()
_SOLVER_TO_ID = invert_dict(_ID_TO_SOLVER)
_DEFAULT_COLS_WITH_CONV_PARAMS = ['fdb_key']


class FINDDB_ERRORS(Enum):  # pylint: disable=invalid-name
  """defines error codes thrown by check_finddb function"""
  NO_ENTRIES = 0
  INVALID_ENTRIES = 1
  OPENCL_ON = 2
  MULTIPLE_SESSIONS = 3
  DUPLICATE_ENTRIES = 7


def check_finddb(finddb,
                 cols_with_conv_params=None,
                 strict=False,
                 verbosity=0,
                 tag=''):
  """check finddb and raise erros or log warnings"""
  if cols_with_conv_params is None:
    cols_with_conv_params = _DEFAULT_COLS_WITH_CONV_PARAMS

  issues = []

  logging.log(f'checking {tag}finddb...', end_char='\r')

  if len(finddb) == 0:
    logging.report_error(f'{tag}finddb contains no entry', strict=strict)
    issues.append(FINDDB_ERRORS.NO_ENTRIES)

  if (finddb['valid'] != 1).any():
    logging.report_warning(f'{tag}finddb contains invalid entries',
                           strict=strict)
    issues.append(FINDDB_ERRORS.INVALID_ENTRIES)

  if finddb['opencl'].any():
    logging.report_warning(
        f'there are kernels with opencl enabled in {tag}finddb', strict=strict)
    issues.append(FINDDB_ERRORS.OPENCL_ON)

  if not df_tools.is_col_unique(finddb, col_name='session'):
    logging.report_warning(
        f'data from multiple tuning sessions present in the {tag}finddb',
        strict=strict)
    issues.append(FINDDB_ERRORS.MULTIPLE_SESSIONS)

  num_duplicates = finddb.duplicated(subset=cols_with_conv_params +
                                     ['solver']).sum()
  if num_duplicates > 0:
    if verbosity >= 1:
      logging.log(f'{num_duplicates} duplicates found! generating report...',
                  end_char='\r')
      log_duplicates(finddb, cols_with_conv_params)

    logging.report_warning(
        f'{num_duplicates} duplicate entries delected in {tag}finddb',
        strict=strict)
    issues.append(FINDDB_ERRORS.DUPLICATE_ENTRIES)

  if not issues:
    logging.success(f'{tag}finddb passed all checks!')

  return issues


def describe_fastdb(fastdb, tag=''):
  """ describe fastdb (num. of entries in it, etc.) """
  if len(fastdb) == 0:
    logging.warning(f'{tag}fastdb empty!')
  else:
    logging.info(
        f'Total entries in {tag}fastdb (=unique configs in {tag}finddb): %d' %
        len(fastdb))
    logging.info(f'Number of unique solvers in {tag}fastdb: %d' %
                 len(fastdb['solver'].unique()))


def load_fastdb(fastdb_pickle_filename):
  """ load fastdb from pickle """
  fastdb = io_tools.safe_load(None, fastdb_pickle_filename,
                              df_tools.from_pickle)
  describe_fastdb(fastdb)
  return fastdb


def finddb_to_nonthresholded_fastdb(finddb,
                                    cols_with_conv_params=None,
                                    n_fastest=1,
                                    tag=''):
  """ generate fastdb from finddb without thresholding/removing out any solvers """
  if cols_with_conv_params is None:
    cols_with_conv_params = _DEFAULT_COLS_WITH_CONV_PARAMS

  num_duplicates = finddb.duplicated(subset=cols_with_conv_params +
                                     ['solver']).sum()
  if num_duplicates > 0:
    logging.warning(f'resolved the {num_duplicates} duplicate (fdb_key, solver)' +\
            f' pairs found in {tag}finddb by keeping the entries with fastest solver')
  sorted_finddb = finddb.sort_values(cols_with_conv_params + ['kernel_time'])
  return sorted_finddb.groupby(cols_with_conv_params).head(n_fastest)


def is_fundamental_solver(solver):
  """defines fundamental solvers"""

  def is_explicit_gemm(solver):
    return is_substr('Gemm', solver) and not is_substr('ImplicitGemm', solver)

  def is_naive(solver):
    return is_substr('Naive', solver)

  return is_explicit_gemm(solver) or is_naive(solver)


def get_solvers_below_threshold(finddb_solver_counts, fastdb_solver_counts,
                                threshold):
  """get all solvers that have lower representation than given threshold"""
  logging.log('determining solvers below threshold...', end_char='\r')
  solvers_below_threshold = []
  for solver in finddb_solver_counts:
    if solver in fastdb_solver_counts:
      ratio_in_fastdb = fastdb_solver_counts[solver] / sum(
          fastdb_solver_counts.values())
    else:
      ratio_in_fastdb = 0

    if ratio_in_fastdb < (threshold / 100):
      solvers_below_threshold.append(solver)

  logging.reset_line()
  return solvers_below_threshold


def get_solvers_to_remove(solvers_below_threshold, keep_fundamental=True):
  """filters out fundamental solvers from solvers_below_threshold"""
  if keep_fundamental:
    solvers_to_remove = filter_out(solvers_below_threshold,
                                   is_fundamental_solver)
    logging.log(
        f'marked {len(solvers_to_remove)} non-fundamental solvers below threshold'
    )
  else:
    solvers_to_remove = solvers_below_threshold
    logging.log(
        f'marked all of {len(solvers_to_remove)} solvers below threshold')

  return solvers_to_remove


def print_thresholding_summary(finddb_solver_counts, solvers_below_threshold,
                               solvers_to_remove):
  """prints summary of which solvers are below threshold and which ones will be removed"""
  print_heading('SUMMARY', printer=logging.log)
  n = max(len(solver) for solver in finddb_solver_counts)  # pylint: disable=invalid-name
  m = len('BELOW-THRESHOLD')  # pylint: disable=invalid-name
  for solver in finddb_solver_counts:
    flag_a = 'BELOW-THRESHOLD' if solver in solvers_below_threshold else ''
    flag_b = 'FUNDAMENTAL' if is_fundamental_solver(solver) else ''
    string = f'{solver}'.ljust(n + 3) + f'{flag_a}'.ljust(m + 3) + f'{flag_b}'
    if solver in solvers_to_remove:
      logging.log('- ' + string, formatting=ANSIColors.red)
    else:
      logging.log('+ ' + string)
  logging.log(
      'solver names with a "-" infront got replaced (where a replacement was available)'
  )


def gen_fastdb(finddb, threshold=0, keep_fundamental=False, verbosity=0):
  """ generate fastdb with all solvers below threshold removed """
  check_finddb(finddb, verbosity=verbosity)

  logging.log('getting fastest solvers per config...', end_char='\r')
  fastdb = finddb_to_nonthresholded_fastdb(finddb)
  logging.reset_line()

  if threshold > 0:
    finddb_solver_counts = sort_dict(get_solver_counts(finddb))
    fastdb_solver_counts = sort_dict(get_solver_counts(fastdb))
    solvers_below_threshold = get_solvers_below_threshold(
        finddb_solver_counts, fastdb_solver_counts, threshold)

    if len(solvers_below_threshold) == 0:
      logging.warning(
          'threshold too loose: none of the solvers are below threshold')
    else:
      solvers_to_remove = get_solvers_to_remove(solvers_below_threshold,
                                                keep_fundamental)
      solver_ids_to_remove = map_list(solvers_to_remove, _SOLVER_TO_ID)

      thresholded_finddb = finddb[~finddb['solver'].isin(solver_ids_to_remove)]
      logging.log(
          'thresholded-findb generated by removing the marked solvers from finddb'
      )

      thresholded_fastdb = finddb_to_nonthresholded_fastdb(thresholded_finddb,
                                                           tag='thresholded-')
      logging.success('thresholded-fastdb generated from thresholded-finddb!')

      describe_fastdb(thresholded_fastdb, tag='thresholded-')

      # print summary
      if verbosity >= 1:
        print_thresholding_summary(finddb_solver_counts,
                                   solvers_below_threshold, solvers_to_remove)

      return thresholded_fastdb

  logging.success('fastdb generated!')
  describe_fastdb(fastdb)
  return fastdb


def main():
  """ main """
  default_in_file = os.path.join(_DEFAULT_INPUT_DIR, 'finddb.pkl')
  default_out_dir = _DEFAULT_OUTPUT_DIR

  parser = argparse.ArgumentParser(description='Generate fastdb from finddb')
  parser.add_argument(
      '-i',
      '--in',
      type=str,
      default=default_in_file,
      dest='input',
      help=
      f'filename for the pickled finddb Pandas dataframe (current: {default_in_file})'
  )
  parser.add_argument(
      '-o',
      '--out',
      type=str,
      default=default_out_dir,
      dest='output',
      help=
      f'dir to output pickled fastdb pandas-dataframe to (current: {default_out_dir})'
  )
  parser.add_argument(
      '-t',
      '--threshold',
      type=float,
      default=0,
      dest='threshold',
      help=
      'replace all solvers w/ lesser frequency than the threshold (default: 0)')
  parser.add_argument(
      '--keep_fundamental',
      action='store_true',
      default=False,
      dest='keep_fundamental',
      help=
      'specify this flag to keep the fundamental solvers despite them being infrequent'
  )
  parser.add_argument('-v',
                      '--verbosity',
                      type=int,
                      default=0,
                      help='higher verbosity => more detailed logs',
                      choices=[0, 1, 2])

  args = parser.parse_args()

  finddb = load_finddb(args.input)
  fastdb = gen_fastdb(finddb, args.threshold, args.keep_fundamental,
                      args.verbosity)

  io_tools.safe_save(fastdb, os.path.join(args.output, 'fastdb.pkl'),
                     df_tools.to_pickle)
  logging.dump_logs(os.path.join(args.output, 'gen_fastdb.log'))


if __name__ == '__main__':
  main()
