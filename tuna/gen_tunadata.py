import os
import argparse

from tuna.utils import logging
import tuna.utils.tools.io as io_tools
import tuna.utils.tools.df as df_tools
from tuna.gen_fastdb import load_fastDB
import tuna.utils.tools.json as json_tools
from tuna.utils.tools.df import map_series
from tuna.utils.db_utility import get_id_solvers
from tuna.utils.fdb_key_utils import explode_fdb_keys
from tuna.utils.helpers import pretty_list, get_reverse_map, invert_dict,\
    compose, print_heading, merge_dicts

_, _ID_TO_SOLVER = get_id_solvers()
_SOLVER_TO_ID = invert_dict(_ID_TO_SOLVER)

_OPTIONAL_KEYNAMES = ['GroupSize', 'TBA']

_DEFAULT_INPUT_DIR = os.path.join(os.getcwd(), 'findDB_')
_DEFAULT_OUTPUT_DIR = os.path.join(os.getcwd(), 'findDB_', 'data')


def check_fastDB(fastDB, tag='', strict=False):
  SMALL_FAST_DB = 0
  issues = []

  if len(fastDB) < 50000:
    if strict:
      raise AssertionError(f'{tag}FastDB has less than 50,000 entires')
    else:
      logging.warning(f'{tag}FastDB has less than 50,000 entries')
      issues.append(SMALL_FAST_DB)

  return issues


def describe_mlDB(mlDB, tag=''):
  logging.info(f'number of entries in {tag}MLDB: %d' % len(mlDB))
  print_heading(f'{tag}MLDB COLUMNS', printer=logging.log)

  mlDB_columns, num_conv_params = [], 0
  for colname, dtype in mlDB.dtypes.iteritems():
    mlDB_columns.append(f'{colname} ({dtype})')
    if colname[0].isupper():
      num_conv_params += 1

  logging.info(
      'num of parameters describing each convolution problem: %d (including redundant parameters)'
      % num_conv_params)

  logging.log(pretty_list(mlDB_columns))
  logging.log(
      'Note: column names starting with an uppercase letter represent convolution parameters'
  )

  num_convolution_params = 0


def load_mlDB(mlDB_pickle_filename, tag=''):
  mlDB = io_tools.safe_load(None, mlDB_pickle_filename, df_tools.from_pickle)
  describe_mlDB(mlDB, tag)
  return mlDB


def gen_mlDB(fastDB):
  """ mlDB is just an easy-to-work-on form of fastDB. It
      - basically contains the fdb_key, alg_lib, solver, & kernel_time columns from fastDB 
      - explodes fdb_keys into the respective convolution parameters
      - encodes any columns with strings to numbers
      - renames the columns so that columns representing inputs to ML models
       start with an upper letter and columns representing expected outputs
       from ML models start with a lowercase letter
    mlDB is processed to get tunadata (which TunaNet loads in as TunaDataset)
  """
  check_fastDB(fastDB)

  # explode fdb keys
  conv_params = explode_fdb_keys(fastDB['fdb_key'])

  # encode "Direction", "Precision" and "Layout" columns
  logging.reset_line()
  logging.log(
      'generating Direction, Precision and Layout encodings...', end_char='\r')
  conv_params['Direction'], direction_encoding = df_tools.encode_series(
      conv_params['Direction'])
  conv_params['Precision'], precision_encoding = df_tools.encode_series(
      conv_params['Precision'])
  conv_params['Layout'], layout_encoding = df_tools.encode_series(
      conv_params['Layout'])

  # rename "alg_lib" -> "algorithm",  "solver "->" solver",  "kernel_time" -> "solverTime"
  algos = fastDB['alg_lib'].rename('algorithm')
  solvers = df_tools.map_series(fastDB['solver'],
                                _ID_TO_SOLVER).rename('solver')
  solver_times = fastDB['kernel_time'].rename('solverTime')

  # encode "algorithm" and "solverTime" columns
  logging.reset_line()
  logging.log('generating encodings for Algorithm and Solver...', end_char='\r')
  encoded_algos, algo_encoding = df_tools.encode_series(algos)
  encoded_solvers, solver_encoding = df_tools.encode_series(solvers)

  # create mlDB and pack all encodings
  mlDB = df_tools.combine(conv_params, encoded_algos, encoded_solvers,
                          solver_times)
  mlDB = mlDB.astype('float32')

  mlDB_encodings = {
      'Direction': direction_encoding,
      'Precision': precision_encoding,
      'Layout': layout_encoding,
      'algorithm': algo_encoding,
      'solver': solver_encoding
  }

  logging.reset_line()
  logging.success('MLDB created and encodings packed into single dictionary!')

  describe_mlDB(mlDB)

  return mlDB, mlDB_encodings


def process_mlDB(mlDB, train_ratio, random_split, seed):
  """process mlDB into tunadata"""
  ground_truth_colnames = ['algorithm', 'solver', 'solverTime']

  deleted_cols = df_tools.delete_redundant_cols(
      mlDB, masked_cols=ground_truth_colnames, inplace=True)

  overall_features, overall_gt = df_tools.split(mlDB, ground_truth_colnames)

  train_mlDB, test_mlDB = df_tools.train_test_split(mlDB, train_ratio,
                                                    random_split, seed)
  train_features, train_gt = df_tools.split(train_mlDB, ground_truth_colnames)
  test_features, test_gt = df_tools.split(test_mlDB, ground_truth_colnames)

  # describe mlDB
  logging.log(f'train and test datasets created out of mlDB')

  logging.info(f'number of features: {train_features.shape[1]}')
  logging.info(f'train size: {len(train_mlDB)}')
  logging.info(f'test size: {len(test_mlDB)}')

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


if __name__ == '__main__':
  default_out_dirname = _DEFAULT_OUTPUT_DIR
  default_in_filename = os.path.join(_DEFAULT_INPUT_DIR, 'fastDB.pkl')

  parser = argparse.ArgumentParser(description='Generate MLDB from FastDB')
  parser.add_argument(
      '-i',
      '--in',
      type=str,
      default=default_in_filename,
      dest='input',
      help=
      f'filename for the fastDB Pandas dataframe (current: {default_in_filename})'
  )
  parser.add_argument(
      '-o',
      '--out',
      type=str,
      default=default_out_dirname,
      dest='output',
      help=
      f'dirname for the output mlDB dataframes (current: {default_out_dirname})'
  )
  parser.add_argument(
      '--train_ratio',
      type=float,
      default=0.7,
      help=
      f'a proper fraction (or 0, 1) determining the size of train set (default: 0.7)'
  )
  parser.add_argument(
      '--random',
      action='store_true',
      default=False,
      help=
      f'randomly split into train and test according to train_ratio (default: False)'
  )
  parser.add_argument(
      '--seed', type=int, default=None, help=f'seed (default: None)')

  args = parser.parse_args()

  fastDB = load_fastDB(args.input)
  mlDB, encodings = gen_mlDB(fastDB)
  train_features, train_gt, test_features, test_gt, stats = process_mlDB(
      mlDB, args.train_ratio, args.random, args.seed)

  assert (train_features.columns == test_features.columns).all()
  assert (train_gt.columns == test_gt.columns).all()

  # create metadata
  metadata = {
      'session': fastDB['session'].unique().tolist(),
      'num_algos': len(mlDB['algorithm'].unique()),
      'num_solvers': len(mlDB['solver'].unique()),
      'conv_params_all': mlDB.columns.tolist(),
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
