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
""" generate dataset for training tunadata """

import os
import argparse

from tuna.utils import logging
import tuna.utils.tools.io as io_tools
import tuna.utils.tools.df as df_tools
from tuna.gen_fastdb import load_fastdb
import tuna.utils.tools.json as json_tools
from tuna.utils.db_utility import get_id_solvers
from tuna.utils.fdb_key_utils import explode_fdb_keys
from tuna.utils.helpers import pretty_list, invert_dict, print_heading

_, _ID_TO_SOLVER = get_id_solvers()
_SOLVER_TO_ID = invert_dict(_ID_TO_SOLVER)

_OPTIONAL_KEYNAMES = ['GroupSize', 'TBA']

_DEFAULT_INPUT_DIR = os.path.join(os.getcwd(), 'finddb_')
_DEFAULT_OUTPUT_DIR = os.path.join(os.getcwd(), 'finddb_', 'data')


def check_fastdb(fastdb, tag='', strict=False):
  """ check fastdb for any consistencies """
  SMALL_FAST_DB = 0  # pylint: disable=invalid-name; @saud will create an enum later
  issues = []

  if len(fastdb) < 50000:
    if strict:
      raise AssertionError(f'{tag}fastdb has less than 50,000 entires')
    logging.warning(f'{tag}fastdb has less than 50,000 entries')
    issues.append(SMALL_FAST_DB)

  return issues


def describe_mldb(mldb, tag=''):
  """ log a brief description of mldb """
  logging.info(f'number of entries in {tag}MLDB: %d' % len(mldb))
  print_heading(f'{tag}MLDB COLUMNS', printer=logging.log)

  mldb_columns, num_conv_params = [], 0
  for colname, dtype in mldb.dtypes.iteritems():
    mldb_columns.append(f'{colname} ({dtype})')
    if colname[0].isupper():
      num_conv_params += 1

  logging.info('num of parameters describing each convolution problem: '
               f'{num_conv_params} (including redundant parameters)')

  logging.log(pretty_list(mldb_columns))
  logging.log(
      'Note: column names starting with an uppercase letter represent convolution parameters'
  )


def load_mldb(mldb_pickle_filename, tag=''):
  """ load the mldb dataframe from a pickle """
  mldb = io_tools.safe_load(None, mldb_pickle_filename, df_tools.from_pickle)
  describe_mldb(mldb, tag)
  return mldb


def gen_mldb(fastdb):
  """ mldb is just an easy-to-work-on form of fastdb. It
      - basically contains the fdb_key, alg_lib, solver, & kernel_time columns from fastdb
      - explodes fdb_keys into the respective convolution parameters
      - encodes any columns with strings to numbers
      - renames the columns so that columns representing inputs to ML models
       start with an upper letter and columns representing expected outputs
       from ML models start with a lowercase letter
    mldb is processed to get tunadata (which TunaNet loads in as TunaDataset)
  """
  check_fastdb(fastdb)

  # explode fdb keys
  conv_params = explode_fdb_keys(fastdb['fdb_key'])

  # encode "Direction", "Precision" and "Layout" columns
  logging.reset_line()
  logging.log('generating Direction, Precision and Layout encodings...',
              end_char='\r')
  conv_params['Direction'], direction_encoding = df_tools.encode_series(
      conv_params['Direction'])
  conv_params['Precision'], precision_encoding = df_tools.encode_series(
      conv_params['Precision'])
  conv_params['Layout'], layout_encoding = df_tools.encode_series(
      conv_params['Layout'])

  # rename "alg_lib" -> "algorithm",  "solver "->" solver",  "kernel_time" -> "solverTime"
  algos = fastdb['alg_lib'].rename('algorithm')
  solvers = df_tools.map_series(fastdb['solver'],
                                _ID_TO_SOLVER).rename('solver')
  solver_times = fastdb['kernel_time'].rename('solverTime')

  # encode "algorithm" and "solverTime" columns
  logging.reset_line()
  logging.log('generating encodings for Algorithm and Solver...', end_char='\r')
  encoded_algos, algo_encoding = df_tools.encode_series(algos)
  encoded_solvers, solver_encoding = df_tools.encode_series(solvers)

  # create mldb and pack all encodings
  mldb = df_tools.combine(conv_params, encoded_algos, encoded_solvers,
                          solver_times)
  mldb = mldb.astype('float32')

  mldb_encodings = {
      'Direction': direction_encoding,
      'Precision': precision_encoding,
      'Layout': layout_encoding,
      'algorithm': algo_encoding,
      'solver': solver_encoding
  }

  logging.reset_line()
  logging.success('MLDB created and encodings packed into single dictionary!')

  describe_mldb(mldb)

  return mldb, mldb_encodings


# pylint: disable=too-many-locals
def process_mldb(mldb, train_ratio, random_split, seed):
  """process mldb into tunadata"""
  ground_truth_colnames = ['algorithm', 'solver', 'solverTime']

  df_tools.delete_redundant_cols(mldb,
                                 masked_cols=ground_truth_colnames,
                                 inplace=True)

  overall_features, overall_gt = df_tools.split(mldb, ground_truth_colnames)

  train_mldb, test_mldb = df_tools.train_test_split(mldb, train_ratio,
                                                    random_split, seed)
  train_features, train_gt = df_tools.split(train_mldb, ground_truth_colnames)
  test_features, test_gt = df_tools.split(test_mldb, ground_truth_colnames)

  # describe mldb
  logging.log('train and test datasets created out of mldb')

  logging.info(f'number of features: {train_features.shape[1]}')
  logging.info(f'train size: {len(train_mldb)}')
  logging.info(f'test size: {len(test_mldb)}')

  # compute statistics
  logging.log('computing means and stds...', end_char='\r')

  train_features_stats = {
      'mean': df_tools.to_dict(train_features.mean(axis=0)),
      'std': df_tools.to_dict(train_features.std(axis=0))
  }
  test_features_stats = {
      'mean': df_tools.to_dict(test_features.mean(axis=0)),
      'std': df_tools.to_dict(test_features.std(axis=0))
  }
  overall_features_stats = {
      'mean': df_tools.to_dict(overall_features.mean(axis=0)),
      'std': df_tools.to_dict(overall_features.std(axis=0))
  }

  train_gt_stats = {
      'mean': df_tools.to_dict(train_gt.mean(axis=0)),
      'std': df_tools.to_dict(train_gt.std(axis=0))
  }
  test_gt_stats = {
      'mean': df_tools.to_dict(test_gt.mean(axis=0)),
      'std': df_tools.to_dict(test_gt.std(axis=0))
  }
  overall_gt_stats = {
      'mean': df_tools.to_dict(overall_gt.mean(axis=0)),
      'std': df_tools.to_dict(overall_gt.std(axis=0))
  }

  stats = {
      'train': {
          'features': train_features_stats,
          'gt': train_gt_stats
      },
      'test': {
          'features': test_features_stats,
          'gt': test_gt_stats
      },
      'overall': {
          'features': overall_features_stats,
          'gt': overall_gt_stats
      }
  }

  logging.success('statistics computed and compiled!')

  return train_features, train_gt, test_features, test_gt, stats


def main():
  """ main """
  default_output_dirname = _DEFAULT_OUTPUT_DIR
  default_input_filename = os.path.join(_DEFAULT_INPUT_DIR, 'fastdb.pkl')

  parser = argparse.ArgumentParser(description='Generate MLDB from fastdb')
  parser.add_argument(
      '-i',
      '--in',
      type=str,
      default=default_input_filename,
      dest='input',
      help=
      f'filename for the fastdb Pandas dataframe (current: {default_input_filename})'
  )
  parser.add_argument(
      '-o',
      '--out',
      type=str,
      default=default_output_dirname,
      dest='output',
      help=
      f'dirname for the output mldb dataframes (current: {default_output_dirname})'
  )
  parser.add_argument(
      '--train_ratio',
      type=float,
      default=0.7,
      help=
      'a proper fraction (or 0, 1) determining the size of train set (default: 0.7)'
  )
  parser.add_argument(
      '--random',
      action='store_true',
      default=False,
      help=
      'randomly split into train and test according to train_ratio (default: False)'
  )
  parser.add_argument('--seed',
                      type=int,
                      default=None,
                      help='seed (default: None)')

  args = parser.parse_args()

  fastdb = load_fastdb(args.input)
  mldb, encodings = gen_mldb(fastdb)
  train_features, train_gt, test_features, test_gt, stats = process_mldb(
      mldb, args.train_ratio, args.random, args.seed)

  assert (train_features.columns == test_features.columns).all()
  assert (train_gt.columns == test_gt.columns).all()

  # create metadata
  metadata = {
      'session': fastdb['session'].unique().tolist(),
      'num_algos': len(mldb['algorithm'].unique()),
      'num_solvers': len(mldb['solver'].unique()),
      'conv_params_all': mldb.columns.tolist(),
      'conv_params_used_as_features': train_features.columns.tolist(),
      'encodings': encodings,
      'stats': stats
  }

  # dump
  train_dir = os.path.join(args.output, 'train')
  test_dir = os.path.join(args.output, 'test')

  io_tools.safe_save(train_features, os.path.join(train_dir, 'features.csv'),
                     df_tools.to_csv)
  io_tools.safe_save(train_gt, os.path.join(train_dir, 'gt.csv'),
                     df_tools.to_csv)
  io_tools.safe_save(test_features, os.path.join(test_dir, 'features.csv'),
                     df_tools.to_csv)
  io_tools.safe_save(test_gt, os.path.join(test_dir, 'gt.csv'), df_tools.to_csv)

  io_tools.safe_save(metadata, os.path.join(args.output, 'metadata.json'),
                     json_tools.save)

  logging.dump_logs(os.path.join(args.output, 'gen_mldb.log'))


if __name__ == '__main__':
  main()
