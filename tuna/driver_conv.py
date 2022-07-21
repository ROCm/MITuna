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
"""Module that a convolution MIOpenDriver cmd"""
from tuna.driver_base import DriverBase
from tuna.metadata import CONV_CONFIG_COLS
from tuna.helper import get_db_id
from tuna.miopen_tables import ConvolutionConfig
from tuna.metadata import CONV_2D_DEFAULTS, SUPPORTED_CONV_CMDS
from tuna.metadata import CONV_3D_DEFAULTS, TENSOR_COLS, TABLE_COLS_CONV_MAP
from tuna.metadata import DIRECTION, DIR_MAP, CONV_SKIP_ARGS
from tuna.parsing import get_fd_name, conv_arg_valid, get_fds_from_cmd


#pylint: disable=too-many-instance-attributes
class DriverConvolution(DriverBase):
  """Represents an MIOpenDriver convolution command"""

  def __init__(self, line, cmd=None):

    self.batchsize = None
    self.spatial_dim = None
    self.pad_h = None
    self.pad_w = None
    self.pad_d = None
    self.conv_stride_h = None
    self.conv_stride_w = None
    self.conv_stride_d = None
    self.dilation_h = None
    self.dilation_w = None
    self.dilation_d = None
    self.group_count = None
    self.conv_mode = None
    self.pad_mode = None
    self.trans_output_pad_h = None
    self.trans_output_pad_w = None
    self.trans_output_pad_d = None
    self.out_layout = None
    self.in_layout = None
    self.fil_layout = None
    self.in_d = None
    self.in_h = None
    self.in_w = None
    self.fil_d = None
    self.fil_h = None
    self.fil_w = None
    self.in_channels = None
    self.out_channels = None
    self.num_dims = None
    self.direction = None
    self._cmd = None

    super().__init__(line)
    #allow cmd input to override driver line
    if cmd:
      self._cmd = cmd

  @property
  def cmd(self):
    """Setting 'private' variable"""
    return self._cmd

  @cmd.setter
  def cmd(self, value):
    """Checking for allowed conv values"""
    if value not in SUPPORTED_CONV_CMDS:
      raise ValueError(
          f'Cannot instantiate convolution Driver class. Supported cmds are: {SUPPORTED_CONV_CMDS}'
      )
    self._cmd = value

  def parse_fdb_key(self, line):
    """import config attributes from fdb key line"""
    fds, _, direction = get_fds_from_cmd(line)
    setattr(self, 'direction', DIR_MAP[direction])
    for key, val in fds.items():
      setattr(self, key, val)

  def parse_driver_line(self, line):
    super().parse_driver_line(line)

    if self.direction and self.direction in DIRECTION:
      self.direction = DIR_MAP[self.direction]
    else:
      raise ValueError(
          f"Can't import driver commmand line, needs direction: '{line}'")

  def compose_tensors(self, keep_id=False):
    """Get tensors needed for DB table based on config type"""
    c_dict = self.get_conv_dict()

    if keep_id:
      c_dict['id'] = get_db_id(c_dict, ConvolutionConfig)

    return c_dict

  def get_conv_dict(self):
    """Populate c_dict with conv table elems"""
    c_dict = {}
    for key, val in self.to_dict().items():
      if key in CONV_CONFIG_COLS:
        c_dict[key] = val

    c_dict['input_tensor'] = super().get_input_t_id()
    c_dict['weight_tensor'] = super().get_weight_t_id()

    return c_dict

  def config_set_defaults(self):
    """Setting config DB defaults to avoid duplicates through SELECT"""
    if self.spatial_dim == 3:
      self.set_defaults(CONV_3D_DEFAULTS)
    else:
      self.set_defaults(CONV_2D_DEFAULTS)

  def set_defaults(self, defaults):
    """Set fds defaults"""
    for k, val in self.to_dict().items():
      if val is None and k in defaults.keys():
        setattr(self, k, defaults[k])

  @staticmethod
  def get_params(tok1):
    """Get full arg name"""
    return get_fd_name(tok1, TABLE_COLS_CONV_MAP)

  @staticmethod
  def get_check_valid(tok1, tok2):
    """Check if valid conv arg"""
    return conv_arg_valid(tok1, tok2)

  def get_db_obj(self, keep_id=False):
    """Return the DB representation of this object"""
    return ConvolutionConfig(**self.compose_tensors(keep_id))

  def __str__(self):
    return "./bin/MIOpenDriver " + self.cmd + " " + " ".join(
        '--{} {}'.format(key, val)
        for key, val in self.to_dict().items()
        if key in CONV_CONFIG_COLS or key in TENSOR_COLS or
        key in self.get_common_cols())

  @staticmethod
  def test_skip_arg(tok1):
    """Check if token is skipable"""
    if tok1 in CONV_SKIP_ARGS:
      return True
    return False
