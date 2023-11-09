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

from tuna.utils.logger import setup_logger
from tuna.miopen.driver.base import DriverBase
from tuna.miopen.utils.metadata import BN_CONFIG_COLS, IN_TENSOR_COLS, PREC_TO_CMD
from tuna.miopen.utils.metadata import SUPPORTED_BN_CMDS, TABLE_COLS_BN_MAP, BN_DEFAULTS
from tuna.miopen.utils.metadata import DIRECTION, DIR_MAP, BN_SKIP_ARGS
from tuna.miopen.db.miopen_tables import BNConfig
from tuna.miopen.utils.parsing import get_fd_name, arg_valid
from tuna.miopen.utils.helper import get_db_id
from tuna.miopen.utils.config_type import ConfigType

LOGGER = setup_logger('driver_bn')


#pylint: disable=too-many-instance-attributes
class DriverBatchNorm(DriverBase):
  """Represents db tables based on ConfigType"""

  def __init__(self,
               line: str = str(),
               cmd: str = str(),
               db_obj: BNConfig = None) -> None:
    self.batchsize: int = 0
    self.alpha: int = 1
    self.beta: int = 0
    self.forw: int = 1
    self.back: int = 0
    self.mode: int = 0
    self.run: int = 0
    self.in_d: int = 1
    self.in_h: int = 1
    self.in_w: int = 1
    self.in_channels: int = 1
    self.in_layout: str = 'NCHW'
    self.num_dims: int = 2
    self.direction: str = 'F'
    self.save: int = 0
    self.verify: int = 1
    self._cmd: str = 'bnorm'

    super().__init__(line, db_obj)
    #allow cmd input to override driver line
    if cmd:
      self._cmd = cmd

  @property
  def cmd(self) -> str:
    """Setting 'private' attribute"""
    return self._cmd

  @cmd.setter
  def cmd(self, value: str) -> None:
    """Checking allowed BN cmd values"""
    if value not in SUPPORTED_BN_CMDS:
      raise ValueError(f'Cannot instantiate batch normalization Driver class. \
           Supported cmds are: {SUPPORTED_BN_CMDS}')
    self._cmd = value

  def parse_driver_line(self, line: str) -> None:
    super().parse_driver_line(line)
    self.compute_direction()

  def parse_fdb_key(self, line):
    """ Overidden Method"""
    raise NotImplementedError("Not implemented")

  def compose_weight_t(self):
    """ Overridden Method """
    raise NotImplementedError("Not implemented")

  def compute_direction(self) -> None:
    """Setting BN direction based on forw and back"""
    direction_t: int
    direction_t = int(self.forw) + 4 * int(self.back)

    if direction_t and direction_t in DIRECTION:
      self.direction = DIR_MAP[direction_t]
    else:
      raise ValueError("Can't import driver commmand line, \
          one and only one of forw or back must be set")

  def parse_row(self, db_obj: BNConfig) -> None:
    """Overwritting base class function for batch_norm"""
    self.parse_bn_row(db_obj)

  def parse_bn_row(self, db_obj: BNConfig) -> None:
    """Compose obj from bn_config row"""
    for key, value in db_obj.to_dict(ommit_ts=True, ommit_valid=True).items():
      if key not in ('id', 'input_t', 'driver'):
        setattr(self, key, value)
    self.compute_direction()
    self.in_layout = db_obj.in_layout

  def compose_tensors(self, keep_id: bool = False) -> dict:
    """Get tensors needed for DB table based on config type"""
    c_dict = self.get_bn_dict()

    if keep_id:
      c_dict['id'] = get_db_id(c_dict, BNConfig)

    return c_dict

  def get_layouts(self):
    """Get batch norm layouts"""
    return ["in_layout"]

  def get_bn_dict(self) -> dict:
    """Populate c_dict with conv table elems"""
    c_dict = {}
    for key, val in self.to_dict().items():
      if key in BN_CONFIG_COLS:
        c_dict[key] = val

    c_dict['input_tensor'] = super().get_input_t_id()
    c_dict['driver'] = str(self)

    return c_dict

  def config_set_defaults(self) -> None:
    """Setting config DB defaults to avoid duplicates through SELECT"""
    self.set_defaults(BN_DEFAULTS)

  def set_defaults(self, defaults) -> None:
    """Set fds defaults"""
    for k, val in self.to_dict().items():
      if val is None and k in defaults.keys():
        setattr(self, k, defaults[k])

  @staticmethod
  def get_params(tok1: str) -> str:
    """Get full arg name"""
    return get_fd_name(tok1, TABLE_COLS_BN_MAP)

  @staticmethod
  def get_check_valid(tok1: str, tok2: str) -> bool:
    """Check if valid BN arg"""
    return arg_valid(tok1, tok2)

  def get_db_obj(self, keep_id: bool = False) -> BNConfig:
    """Return the DB representation of this object"""
    return BNConfig(**self.compose_tensors(keep_id))

  def __str__(self):
    return "./bin/MIOpenDriver " + self.cmd + " " + " ".join(
        f'--{key} {val}' for key, val in vars(self).items()
        if key in BN_CONFIG_COLS or key in IN_TENSOR_COLS or
        key in self.get_common_cols())

  @staticmethod
  def test_skip_arg(tok1: str) -> bool:
    """Check if token is skipable"""
    if tok1 in BN_SKIP_ARGS:
      return True
    return False

  def set_cmd(self, data_type: str) -> None:
    """Set cmd based on tensor data type"""
    self.cmd = PREC_TO_CMD[ConfigType.batch_norm][data_type]
