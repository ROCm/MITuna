import re
import pandas as pd

from tuna.utils import logging
from tuna.utils.Mold import Mold
import tuna.utils.tools.df as df_tools
from tuna.utils.tools.df import map_series
from tuna.utils.helpers import list_replace, get_reverse_map

# PRIVATE CONSTS
_2D_FDB_KEY_PTRN = 'InChannels-InHeight-InWidth-FilterDim-OutChannels-OutHeight-OutWidth-' +\
         'BatchSize-Padding-Stride-Dilation-BiasFlag-Layout-Precision-' +\
         'DirectionAndUnderscoreSeperatedOptionals'

_3D_FDB_KEY_PTRN = 'InChannels-InDepth-InHeight-InWidth-FilterDim-OutChannels-OutDepth-' +\
         'OutHeight-OutWidth-BatchSize-Padding-Stride-Dilation-BiasFlag-Layout-' +\
         'Precision-DirectionAndUnderscoreSeperatedOptionals'

_OPTIONAL_KEYS = ['GroupSize', 'TBA']

_2D_TO_3D_FDB_KEY = Mold(from_ptrn=_2D_FDB_KEY_PTRN,
                         to_ptrn=_3D_FDB_KEY_PTRN,
                         from_sep='-',
                         to_sep='-',
                         filler=1)

_NAMES_OF_2D_FDB_KEYS = _2D_FDB_KEY_PTRN.split('-')
_NAMES_OF_3D_FDB_KEYS = _3D_FDB_KEY_PTRN.split('-')

_NUM_2D_FDB_KEYS = len(_NAMES_OF_2D_FDB_KEYS)
_NUM_3D_FDB_KEYS = len(_NAMES_OF_3D_FDB_KEYS)


# ATOMIC FDB-KEY UTILS
def get_compulsory_2D_fdb_keynames():
  return list_replace(_NAMES_OF_2D_FDB_KEYS,
                      'DirectionAndUnderscoreSeperatedOptionals', 'Direction')


def get_compulsory_3D_fdb_keynames():
  return list_replace(_NAMES_OF_3D_FDB_KEYS,
                      'DirectionAndUnderscoreSeperatedOptionals', 'Direction')


def is_2D_fdb_key(fdb_key):
  return len(fdb_key.split('-')) == _NUM_2D_FDB_KEYS


def is_3D_fdb_key(fdb_key):
  return len(fdb_key.split('-')) == _NUM_3D_FDB_KEYS


def to_3D_fdb_key(fdb_key):
  if is_3D_fdb_key(fdb_key):
    return fdb_key
  elif is_2D_fdb_key(fdb_key):
    return _2D_TO_3D_FDB_KEY(fdb_key)
  else:
    raise ValueError('fdb_key is neither 2D nor 3D')


# COMPOUND FDB-KEY UTILS
def explode_fdb_keys(fdb_keys: pd.Series):
  """ explodes fdb keys into convolution parameters.
  fdb_keys: pandas.series object """
  # convert fdb keys to 3D fdb keys
  logging.log('mapping all fdb_keys to 3D fdb_keys...', end_char='\r')
  fdb_keys = map_series(fdb_keys, to_3D_fdb_key)
  logging.reset_line()

  # parse the fdb keys into convolution parameters
  logging.log('parsing fdb_keys...', end_char='\r')
  A = fdb_keys.str.split('-', expand=True)
  B = A.iloc[:, -1].str.split('_', expand=True)
  conv_params = df_tools.combine(A.iloc[:, :-1], B)
  conv_params = df_tools.renumber_cols(conv_params)

  # rename the columns in conv_params to the proper parameter names
  compulsory_keynames = get_compulsory_3D_fdb_keynames()
  num_optional_keys_present = conv_params.shape[1] - len(compulsory_keynames)
  optional_keynames = _OPTIONAL_KEYS[:num_optional_keys_present]
  keynames = compulsory_keynames + optional_keynames
  conv_params = conv_params.rename(columns=get_reverse_map(keynames))

  # fix the "GroupSize" column by removing the trailing 'g' & replacing any None by 1
  def fix_group_size(group_size):
    if group_size is None:
      return 1
    return int(group_size[1:])

  if 'GroupSize' in conv_params:
    logging.reset_line()
    logging.log('fixing group sizes...', end_char='\r')
    conv_params['GroupSize'] = map_series(conv_params['GroupSize'],
                                          fix_group_size)

  # explode tensor descriptors: "23x43x14" -> 23, 43, 14
  def explode_tensor_descriptors(tensor_descriptors):
    tensor_descriptors_3D = map_series(tensor_descriptors,
                                       to_3D_tensor_descriptor)
    tensor_descriptors_3D = tensor_descriptors_3D.str.split('x', expand=True)
    column_names = {n: f'{tensor_descriptors.name}{n}' for n in range(3)}
    return tensor_descriptors_3D.rename(columns=column_names)

  cols_with_tensor_descriptors = ['FilterDim', 'Padding', 'Stride', 'Dilation']
  exploded_conv_params = []
  for colname in conv_params:
    if colname in cols_with_tensor_descriptors:
      logging.reset_line()
      logging.log(f'exploding tensor descriptors in {colname}...',
                  end_char='\r')
      exploded_conv_params.append(
          explode_tensor_descriptors(conv_params[colname]))
    else:
      exploded_conv_params.append(conv_params[colname])

  conv_params = df_tools.combine(*exploded_conv_params)

  logging.reset_line()
  logging.success(
      f'fdb keys processed and exploded into convolution parameters')

  return conv_params


# TENSOR DESCRIPTOR (i.e. a string like "2x43x4") UTILS
def tensor_descriptor_dim(tensor_descriptor):
  return tensor_descriptor.count('x') + 1


def to_3D_tensor_descriptor(tensor_descriptor):
  dimensionality = tensor_descriptor_dim(tensor_descriptor)
  if dimensionality == 3:
    return tensor_descriptor
  elif 0 < dimensionality < 3:
    return to_3D_tensor_descriptor('1x' + tensor_descriptor)
  else:
    raise NotImplemented(f'{tensor_descriptor} has dimensionality > 3')
