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
""" utils to process fdb_key """

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
# pylint: disable-next=invalid-name
def get_compulsory_2D_fdb_keynames():
  """ returns names of compulsory 3D fdb keys """
  return list_replace(_NAMES_OF_2D_FDB_KEYS,
                      'DirectionAndUnderscoreSeperatedOptionals', 'Direction')


# pylint: disable-next=invalid-name
def get_compulsory_3D_fdb_keynames():
  """ returns names of compulsory 3D fdb keys """
  return list_replace(_NAMES_OF_3D_FDB_KEYS,
                      'DirectionAndUnderscoreSeperatedOptionals', 'Direction')


# pylint: disable-next=invalid-name
def is_2D_fdb_key(fdb_key):
  """ does given fdb_key represent 2D convolution """
  return len(fdb_key.split('-')) == _NUM_2D_FDB_KEYS


# pylint: disable-next=invalid-name
def is_3D_fdb_key(fdb_key):
  """ does given fdb_key represent 3D convolution """
  return len(fdb_key.split('-')) == _NUM_3D_FDB_KEYS


# pylint: disable-next=invalid-name
def to_3D_fdb_key(fdb_key):
  """ casts a given key to a 3D fdb key """
  if is_3D_fdb_key(fdb_key):
    return fdb_key
  if is_2D_fdb_key(fdb_key):
    return _2D_TO_3D_FDB_KEY(fdb_key)
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
  A = fdb_keys.str.split('-', expand=True)  # pylint: disable=invalid-name
  B = A.iloc[:, -1].str.split('_', expand=True)  # pylint: disable=invalid-name
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
    # pylint: disable-next=invalid-name
    tensor_descriptors_3D = map_series(tensor_descriptors,
                                       to_3D_tensor_descriptor)
    # pylint: disable-next=invalid-name
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
  logging.success('fdb keys processed and exploded into convolution parameters')

  return conv_params


# TENSOR DESCRIPTOR (i.e. a string like "2x43x4") UTILS
def tensor_descriptor_dim(tensor_descriptor):
  """ returns the dimensionality of a tensor descriptor """
  return tensor_descriptor.count('x') + 1


# pylint: disable-next=invalid-name
def to_3D_tensor_descriptor(tensor_descriptor):
  """ convert to a 3D tensor descriptor """
  dimensionality = tensor_descriptor_dim(tensor_descriptor)
  if dimensionality == 3:
    return tensor_descriptor
  if 0 < dimensionality < 3:
    return to_3D_tensor_descriptor('1x' + tensor_descriptor)
  raise NotImplementedError(f'{tensor_descriptor} has dimensionality > 3')
