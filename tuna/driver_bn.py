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
"""Module that encapsulates the DB representation of a batch_normDriver cmd"""
from tuna.driver_base import DriverBase
from tuna.metadata import BN_CONFIG_COLS, IN_TENSOR_COLS
from tuna.metadata import SUPPORTED_BN_CMDS, TABLE_COLS_BN_MAP, BN_DEFAULTS
from tuna.metadata import DIRECTION, DIR_MAP, BN_SKIP_ARGS
from tuna.miopen_tables import BNConfig
from tuna.parsing import get_fd_name, arg_valid
from tuna.helper import get_db_id


#pylint: disable=too-many-instance-attributes
class DriverBatchNorm(DriverBase):
  """Represents db tables based on ConfigType"""

  def __init__(self, line, cmd=None):
    self.batchsize = 0
    self.alpha = 1
    self.beta = 0
    self.forw = 1
    self.back = 0
    self.mode = 0
    self.run = 0
    self.in_d = 1
    self.in_h = 1
    self.in_w = 1
    self.in_channels = 1
    self.in_layout = 'NCHW'
    self._cmd = cmd
    self.num_dims = None
    self.direction = None
    self._cmd = 'bnorm'

    super().__init__(line)
    #allow cmd input to override driver line
    if cmd:
      self._cmd = cmd

  @property
  def cmd(self):
    """Setting 'private' attribute"""
    return self._cmd

  @cmd.setter
  def cmd(self, value):
    """Checking allowed BN cmd values"""
    print(value)
    if value not in SUPPORTED_BN_CMDS:
      raise ValueError(f'Cannot instantiate batch normalization Driver class. \
           Supported cmds are: {SUPPORTED_BN_CMDS}')
    self._cmd = value

  def parse_driver_line(self, line):
    super().parse_driver_line(line)

    self.direction = str(int(self.forw) + 4 * int(self.back))

    if self.direction and self.direction in DIRECTION:
      self.direction = DIR_MAP[self.direction]
    else:
      raise ValueError(f"Can't import driver commmand line, \
          one and only one of forw or back must be set: '{line}'")

  def compose_tensors(self, keep_id=False):
    """Get tensors needed for DB table based on config type"""
    c_dict = self.get_bn_dict()

    if keep_id:
      c_dict['id'] = get_db_id(c_dict, BNConfig)

    return c_dict

  def get_bn_dict(self):
    """Populate c_dict with conv table elems"""
    c_dict = {}
    for key, val in self.to_dict().items():
      if key in BN_CONFIG_COLS:
        c_dict[key] = val

    c_dict['input_tensor'] = super().get_input_t_id()

    return c_dict

  def config_set_defaults(self):
    """Setting config DB defaults to avoid duplicates through SELECT"""
    self.set_defaults(BN_DEFAULTS)

  def set_defaults(self, defaults):
    """Set fds defaults"""
    for k, val in self.to_dict().items():
      if val is None and k in defaults.keys():
        setattr(self, k, defaults[k])

  @staticmethod
  def get_params(tok1):
    """Get full arg name"""
    return get_fd_name(tok1, TABLE_COLS_BN_MAP)

  @staticmethod
  def get_check_valid(tok1, tok2):
    """Check if valid BN arg"""
    return arg_valid(tok1, tok2)

  def get_db_obj(self, keep_id=False):
    """Return the DB representation of this object"""
    return BNConfig(**self.compose_tensors(keep_id))

  def __str__(self):
    return "./bin/MIOpenDriver " + self.cmd + " " + " ".join(
        '--{} {}'.format(key, val)
        for key, val in self.__dict__.items()
        if key in BN_CONFIG_COLS or key in IN_TENSOR_COLS or
        key in self.get_common_cols())

  @staticmethod
  def test_skip_arg(tok1):
    """Check if token is skipable"""
    if tok1 in BN_SKIP_ARGS:
      return True
    return False
