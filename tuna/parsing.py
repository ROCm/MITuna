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
"""parsing functions for fdb key strings etc"""

from re import search

from tuna.metadata import CONV_SKIP_ARGS
from tuna.metadata import TABLE_COLS_FUSION_MAP, TABLE_COLS_CONV_MAP, TABLE_COLS_BN_MAP
from tuna.metadata import INVERS_DIR_MAP, FDS_3D, FDS_2D, DIR_MAP
from tuna.utils.logger import setup_logger
from tuna.helper import config_set_defaults
from tuna.metadata import CMD_TO_PREC, PREC_TO_CMD
from tuna.config_type import ConfigType

LOGGER = setup_logger()


def parse_pdb_key(key, version='1.0.0'):
  """return network parameters from fdb key string"""
  if key.find('=') != -1:
    raise ValueError('Invalid 2D PDB key: {}'.format(key))
  tensors = {}

  pattern_3d = '[0-9]x[0-9]x[0-9]'
  group_count = '1'
  if key.find('_') != -1:
    optional_prt = key[key.find('_') + 1:]
    key = key[:key.find('_')]
    if optional_prt[0] != 'g':
      raise ValueError('Only group count in optional part is supported')
    group_count = optional_prt[1:]
    if not group_count.isdigit():
      raise ValueError('Group count has to be integer')

  if search(pattern_3d, key):
    vals, precision, direction = parse_3d(key, group_count)
    fds = FDS_3D
  else:
    if version == '1.0.0':
      vals, precision, direction, tensors = parse_2d_v2(key, group_count)
    else:
      vals, precision, direction = parse_2d(key, group_count)
    fds = FDS_2D

  vals2 = []
  for val in vals:
    if val.isdigit():
      val = int(val)
    vals2.append(val)

  return fds, vals2, precision, INVERS_DIR_MAP[direction], tensors


def parse_2d_v2(key, group_count):  #pylint: disable=too-many-locals
  """parse key values for 2d network"""
  tmp = key.split('-')
  #len(tensor) could be 1 or 3
  #<input tensor><weight tensor><output tensor>
  tensors = {}
  if len(tmp) == 15:
    #same layout for all tensors
    tensors['input_tensor'] = tmp[12]
    tensors['weight_tensor'] = tmp[12]
    tensors['output_tensor'] = tmp[12]
  else:
    #when len=17 all 3 tensor are specified
    tensors['input_tensor'] = tmp[12]
    tensors['weight_tensor'] = tmp[13]
    tensors['output_tensor'] = tmp[14]

  direction = tmp[len(tmp) - 1]
  precision = tmp[len(tmp) - 2]

  if direction == 'F':
    in_channels = tmp[0]
    in_h = tmp[1]
    in_w = tmp[2]
    out_channels = tmp[4]
    # tmp[5], tmp[6]:  outputsize is ignored in db
  else:
    out_channels = tmp[0]
    in_h = tmp[5]
    in_w = tmp[6]
    in_channels = tmp[4]

  fil_h, fil_w = tmp[3].split('x')
  batchsize = tmp[7]
  pad_h, pad_w = tmp[8].split('x')
  conv_stride_w, conv_stride_h = tmp[9].split('x')
  dilation_h, dilation_w = tmp[10].split('x')
  # unused bias = tmp[11]
  # unused layout = tmp[12]
  #precision = tmp[13]

  vals_2d = [
      pad_h, pad_w, out_channels, fil_w, fil_h, dilation_w, dilation_h,
      conv_stride_w, conv_stride_h, in_channels, in_w, in_h, batchsize,
      group_count
  ]

  return vals_2d, precision, direction, tensors


def parse_2d(key, group_count):  #pylint: disable=too-many-locals
  """parse key values for 2d network"""
  tmp = key.split('-')
  direction = tmp[14]
  if direction == 'F':
    in_channels = tmp[0]
    in_h = tmp[1]
    in_w = tmp[2]
    out_channels = tmp[4]
    # tmp[5], tmp[6]:  outputsize is ignored in db
  else:
    out_channels = tmp[0]
    in_h = tmp[5]
    in_w = tmp[6]
    in_channels = tmp[4]

  fil_h, fil_w = tmp[3].split('x')
  batchsize = tmp[7]
  pad_h, pad_w = tmp[8].split('x')
  conv_stride_w, conv_stride_h = tmp[9].split('x')
  dilation_h, dilation_w = tmp[10].split('x')
  # unused bias = tmp[11]
  # unused layout = tmp[12]
  precision = tmp[13]

  vals_2d = [
      pad_h, pad_w, out_channels, fil_w, fil_h, dilation_w, dilation_h,
      conv_stride_w, conv_stride_h, in_channels, in_w, in_h, batchsize,
      group_count
  ]

  return vals_2d, precision, direction


def parse_3d(key, group_count):  #pylint: disable=too-many-locals
  """parse key values for 3d network"""
  #sample 3D
  #256-16-56-56-1x1x1-64-16-56-56-4-0x0x0-1x1x1-1x1x1-0-NCHW-FP32-F=
  tmp = key.split('-')
  direction = tmp[16]
  if direction == 'F':
    in_channels = tmp[0]
    in_d = tmp[1]
    in_h = tmp[2]
    in_w = tmp[3]
    out_channels = tmp[5]
    # tmp[5], tmp[6]:  outputsize is ignored in db
  else:
    out_channels = tmp[0]
    in_d = tmp[6]
    in_h = tmp[7]
    in_w = tmp[8]
    in_channels = tmp[5]

  fil_d, fil_h, fil_w = tmp[4].split('x')
  batchsize = tmp[9]
  pad_d, pad_h, pad_w = tmp[10].split('x')
  conv_stride_d, conv_stride_w, conv_stride_h = tmp[11].split('x')
  dilation_d, dilation_h, dilation_w = tmp[12].split('x')
  # unused bias = tmp[13]
  # unused layout = tmp[14]
  precision = tmp[15]

  vals_3d = [
      pad_d, pad_h, pad_w, out_channels, fil_d, fil_w, fil_h, dilation_d,
      dilation_w, dilation_h, conv_stride_d, conv_stride_w, conv_stride_h,
      in_channels, in_d, in_w, in_h, batchsize, group_count
  ]

  return vals_3d, precision, direction


def build_driver_cmd(fds, vals, precision, direction):
  """make a driver command for a value set"""
  arg_names = fds[:]
  args = dict(zip(arg_names, vals))
  args['forw'] = INVERS_DIR_MAP[direction]
  conv = 'conv'
  if precision == 'FP16':
    conv = 'convfp16'

  arg_strs = ['--{} {}'.format(key, args[key]) for key in sorted(args)]
  cmd = 'MIOpenDriver {} {}'.format(conv, ' '.join(arg_strs))
  return cmd


def build_driver_cmd_from_config(conv_config, non_driver_cols):
  """Take 1 config row from DB and return MIOpenDriver cmd"""

  cc_dict = conv_config.to_dict()
  if 'conv_mode' in cc_dict.keys():
    cc_dict['mode'] = cc_dict.pop('conv_mode')

  fusion_cols = ['fusion_mode', 'activMode']
  for fusion_col in fusion_cols:
    if fusion_col in cc_dict.keys():
      cc_dict.pop(fusion_col)
  arg_strs = [
      '--{} {}'.format(key, value)
      for key, value in cc_dict.items()
      if key not in non_driver_cols
  ]
  conv = cc_dict['cmd']
  cmd = 'MIOpenDriver {} {}'.format(conv, ' '.join(arg_strs))
  return cmd


def parse_pdb_value(value):
  """return array of solver[parameters] for a db entry"""
  tmp = value.split(';')
  res = []
  for sol in tmp:
    solver, params = sol.split(':')
    res.append((solver, params))
  return res


def set_forward_dir(lst, fds_dict, output_h, output_w, precision):
  """Compose lst of pdb key from fdb_dict for F dir"""
  lst.append(str(fds_dict['in_channels']))
  lst.append(str(fds_dict['in_h']))
  lst.append(str(fds_dict['in_w']))
  lst.append('{}x{}'.format(fds_dict['fil_h'], fds_dict['fil_w']))
  lst.append(str(fds_dict['out_channels']))
  lst.append(str(int(output_h)))
  lst.append(str(int(output_w)))
  lst.append(str(fds_dict['batchsize']))
  lst.append('{}x{}'.format(fds_dict['pad_h'], fds_dict['pad_w']))
  lst.append('{}x{}'.format(fds_dict['conv_stride_w'],
                            fds_dict['conv_stride_h']))
  lst.append('{}x{}'.format(fds_dict['dilation_h'], fds_dict['dilation_w']))
  lst.append('0')  # bias
  lst.append('NCHW')  # only supported format
  lst.append(precision)
  lst.append('F')

  return lst


def set_nonforward_dir(lst, fds_dict, output_h, output_w, precision, direction):
  """Compose lst of pdb key from fdb_dict for B and W dir"""
  lst.append(str(fds_dict['out_channels']))
  lst.append(str(int(output_h)))
  lst.append(str(int(output_w)))
  lst.append('{}x{}'.format(fds_dict['fil_h'], fds_dict['fil_w']))
  lst.append(str(fds_dict['in_channels']))
  lst.append(str(fds_dict['in_h']))
  lst.append(str(fds_dict['in_w']))
  lst.append(str(fds_dict['batchsize']))
  lst.append('{}x{}'.format(fds_dict['pad_h'], fds_dict['pad_w']))
  lst.append('{}x{}'.format(fds_dict['conv_stride_w'],
                            fds_dict['conv_stride_h']))
  lst.append('{}x{}'.format(fds_dict['dilation_h'], fds_dict['dilation_w']))
  lst.append('0')  # bias
  lst.append('NCHW')  # only supported format
  lst.append(precision)
  lst.append(direction)

  return lst


def get_pdb_key(fds_dict, precision, direction='F'):
  """create a key for a network description"""
  lst = []
  in_h = int(fds_dict['in_h'])
  in_w = int(fds_dict['in_w'])
  fil_h = int(fds_dict['fil_h'])
  fil_w = int(fds_dict['fil_w'])
  pad_h = int(fds_dict['pad_h'])
  pad_w = int(fds_dict['pad_w'])
  conv_stride_w = int(fds_dict['conv_stride_w'])
  conv_stride_h = int(fds_dict['conv_stride_h'])

  try:
    output_h = ((in_h - fil_h + 2 * pad_h) / conv_stride_w) + 1
    output_w = ((in_w - fil_w + 2 * pad_w) / conv_stride_h) + 1
  except ZeroDivisionError as zerr:
    LOGGER.error(zerr)
    raise ValueError('Zero Division Error caught')

  if precision not in ('FP32', 'FP16', 'BF16'):
    assert False & 'Invalid precision specified for PDB key generation'
  if direction not in ['F', 'W', 'B']:
    assert False & 'Incorrect direction'
  if direction == 'F':
    lst = set_forward_dir(lst, fds_dict, output_h, output_w, precision)
  else:
    lst = set_nonforward_dir(lst, fds_dict, output_h, output_w, precision,
                             direction)

  if int(fds_dict['group_count']) != 1:
    return '{}_g{}'.format('-'.join(lst), fds_dict['group_count'])

  return '-'.join(lst)


def get_fds_from_cmd(cmd):
  """Return dict of db var to value from MIOpenDriver cmd"""
  if cmd.find('=') != -1:
    f_val, v_val, p_val, direction, _ = parse_pdb_key(cmd.split('=')[0])
    fds = dict(zip(f_val, v_val))
    fds['cmd'] = PREC_TO_CMD.get(ConfigType.convolution).get(p_val, None)
    if not fds['cmd']:
      LOGGER.error('Invalid precision in perf db key')
  else:
    fds, direction = parse_driver_line(cmd)
  config_set_defaults(fds)
  cmd = fds['cmd']

  return fds, CMD_TO_PREC.get(cmd, None), direction


def get_fdb_dict(cmd):
  """return fdb_keys from cmd"""
  fds, precision, direction = get_fds_from_cmd(cmd)
  config_set_defaults(fds)
  fdb_keys = {}
  if direction is None:
    fdb_keys['F'] = get_pdb_key(fds, precision, 'F')
    fdb_keys['B'] = get_pdb_key(fds, precision, 'B')
    fdb_keys['W'] = get_pdb_key(fds, precision, 'W')
  else:
    fdb_keys[DIR_MAP[direction]] = get_pdb_key(fds, precision,
                                               DIR_MAP[direction])
  return fdb_keys


def get_fd_name(tok1, cols_map):
  """return the full name for the argument"""
  if tok1 in cols_map:
    return cols_map[tok1]
  fd_list = [val for _, val in cols_map.items()]

  if tok1 in fd_list:
    return tok1

  LOGGER.error('Unknown parameter: %s', tok1)
  raise Exception('Unknown parameter: {}'.format(tok1))


def conv_arg_valid(arg, val):
  """check validity of conv argument"""
  if arg == 'conv_mode':
    return val in ['conv', 'trans']
  return True


#ALEX_NOTE: Do we have options here for batch norm or fusion?
def arg_valid(arg, val):
  """check validity of argument"""
  if arg or val:
    pass
  return True


def parse_driver_line(line):
  """return network parameters from driver invocation"""
  fds = {}
  line = line.strip()
  start = line.find('MIOpenDriver')
  if start == -1:
    raise ValueError("Invalid driver commmand line: '{}'".format(line))

  line = line[start:]
  direction = None
  if line.find('-F') != -1:
    direction = line.partition("-F")[2][:2].strip()

  tok = line.split()
  fds['cmd'] = tok[1]
  assert tok[1] != ''

  fds = compose_fds(fds, tok, line)
  return fds, direction


def compose_fds(fds, tok, line):
  """Compose fds from driver line"""

  for (tok1, tok2) in zip(tok[2::2], tok[3::2]):
    # the following would not work for a full name argument
    if tok1[0] == '-':
      tok1 = tok1[1:]
    if tok1 in CONV_SKIP_ARGS:
      continue
    tok2 = tok2.strip()
    if fds['cmd'] in ['conv', 'convfp16', 'convbfp16']:
      tok1 = get_fd_name(tok1, TABLE_COLS_CONV_MAP)
      if conv_arg_valid(tok1[0], tok2):
        fds[tok1[0]] = tok2
      else:
        raise ValueError('Invalid command line arg: {} - {} line: {}'.format(
            tok1[0], tok2, line))
    elif fds['cmd'] in ['CBAInfer', 'CBAInferfp16']:
      tok1 = get_fd_name(tok1, TABLE_COLS_FUSION_MAP)
      if arg_valid(tok1[0], tok2):
        fds[tok1[0]] = tok2
    elif fds['cmd'] in ['bnorm', 'bnormfp16']:
      tok1 = get_fd_name(tok1, TABLE_COLS_BN_MAP)
      if arg_valid(tok1[0], tok2):
        fds[tok1[0]] = tok2
      else:
        raise ValueError('Invalid command line arg: {} - {} line: {}'.format(
            tok1[0], tok2, line))
    else:
      return {}

  return fds
