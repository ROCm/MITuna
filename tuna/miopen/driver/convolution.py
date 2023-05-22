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

from typing import Dict, Set, Optional, Any
from re import search
from tuna.utils.logger import setup_logger
from tuna.miopen.driver.base import DriverBase
from tuna.miopen.utils.metadata import CONV_CONFIG_COLS
from tuna.miopen.utils.helper import get_db_id
from tuna.miopen.db.miopen_tables import ConvolutionConfig
from tuna.miopen.utils.metadata import CONV_2D_DEFAULTS, SUPPORTED_CONV_CMDS, PREC_TO_CMD
from tuna.miopen.utils.metadata import CONV_3D_DEFAULTS, TENSOR_COLS
from tuna.miopen.utils.metadata import TABLE_COLS_CONV_MAP, TENSOR_PRECISION
from tuna.miopen.utils.metadata import DIRECTION, DIR_MAP, CONV_SKIP_ARGS, INVERS_DIR_MAP
from tuna.miopen.utils.parsing import get_fd_name, conv_arg_valid, get_fds_from_cmd
from tuna.miopen.utils.config_type import ConfigType

LOGGER = setup_logger('driver_conv')


#pylint: disable=too-many-instance-attributes
class DriverConvolution(DriverBase):
  """Represents an MIOpenDriver convolution command"""

  def __init__(self,
               line: str = str(),
               cmd: str = str(),
               db_obj: ConvolutionConfig = None,
               kwargs: Optional[Dict] = None):

    allowed_keys: Set = set([
        'batchsize', 'spatial_dim', 'pad_h', 'pad_w', 'pad_d', 'conv_stride_h',
        'conv_stride_w', 'conv_stride_d', 'dilation_h', 'dilation_w',
        'dilation_d', 'group_count', 'mode', 'pad_mode', 'trans_output_pad_h',
        'trans_output_pad_w', 'trans_output_pad_d', 'out_layout', 'in_layout',
        'fil_layout', 'in_d', 'in_h', 'in_w', 'fil_d', 'fil_h', 'fil_w',
        'in_channels', 'out_channels', 'direction', 'cmd'
    ])

    self.batchsize: int = 32
    self.spatial_dim: int = 2
    self.pad_h: int = 0
    self.pad_w: int = 0
    self.pad_d: int = 0
    self.conv_stride_h: int = 1
    self.conv_stride_w: int = 1
    self.conv_stride_d: int = 0
    self.dilation_h: int = 1
    self.dilation_w: int = 1
    self.dilation_d: int = 0
    self.group_count: int = 1
    self.mode: str = 'conv'
    self.pad_mode: str = 'default'
    self.trans_output_pad_h: int = 0
    self.trans_output_pad_w: int = 0
    self.trans_output_pad_d: int = 0
    self.out_layout: str = 'NCHW'
    self.in_layout: str = 'NCHW'
    self.fil_layout: str = 'NCHW'
    self.in_d: int = 1
    self.in_h: int = 32
    self.in_w: int = 32
    self.fil_d: int = 1
    self.fil_h: int = 3
    self.fil_w: int = 3
    self.in_channels: int = 3
    self.out_channels: int = 32
    self.num_dims: int = 2
    self.direction: str = 'F'
    self._cmd: str = 'conv'

    if kwargs:
      self.__dict__.update(
          (key, value) for key, value in kwargs.items() if key in allowed_keys)
      self.config_set_defaults()
    else:
      super().__init__(line, db_obj)

    #allow cmd input to override driver line
    if cmd:
      self._cmd = cmd

  @property
  def cmd(self) -> str:
    """Setting 'private' variable"""
    return self._cmd

  @cmd.setter
  def cmd(self, value: str) -> None:
    """Checking for allowed conv values"""
    if value not in SUPPORTED_CONV_CMDS:
      raise ValueError(
          f'Cannot instantiate convolution Driver class. Supported cmds are: {SUPPORTED_CONV_CMDS}'
      )
    self._cmd = value

  def parse_fdb_key(self, line: str) -> None:
    """import config attributes from fdb key line"""
    fds: str
    direction: str
    fds, _, direction = get_fds_from_cmd(line)
    setattr(self, 'direction', DIR_MAP[direction])
    for key in self.to_dict():
      if key in fds:
        setattr(self, key, fds[key])

    pattern_3d = '[0-9]x[0-9]x[0-9]'
    if search(pattern_3d, line):
      setattr(self, 'spatial_dim', 3)

  def parse_driver_line(self, line: str) -> None:
    """Parse MIOpenDriver line"""
    super().parse_driver_line(line)

    if self.direction and self.direction in DIRECTION:
      self.direction = DIR_MAP[self.direction]
    else:
      raise ValueError(
          f"Can't import driver commmand line, needs direction: '{line}'")

  def parse_row(self, db_obj: ConvolutionConfig) -> bool:
    """Overwritting base class function for conv"""
    return self.parse_conv_row(db_obj)

  def parse_conv_row(self, db_obj: ConvolutionConfig) -> bool:
    """Compose obj from conv_config row"""
    self.decompose_weight_t(db_obj)
    key: str
    value: int
    for key, value in db_obj.to_dict(ommit_ts=True, ommit_valid=True).items():
      if key not in ('id', 'input_t', 'weight_t', 'driver'):
        setattr(self, key, value)

    return True

  def compose_tensors(self, keep_id: bool = False) -> dict:
    """Get tensors needed for DB table based on config type"""
    c_dict: dict = self.get_conv_dict()

    if keep_id:
      dict_copy = c_dict.copy()
      dict_copy.pop('driver', None)
      c_dict['id'] = get_db_id(dict_copy, ConvolutionConfig)

    return c_dict

  def get_conv_dict(self) -> dict:
    """Populate c_dict with conv table elems"""
    c_dict: Dict[str, Any] = {}
    key: str
    val: int
    for key, val in self.to_dict().items():
      if key in CONV_CONFIG_COLS:
        c_dict[key] = val

    c_dict['input_tensor'] = super().get_input_t_id()
    c_dict['weight_tensor'] = super().get_weight_t_id()
    c_dict['driver'] = str(self)

    return c_dict

  def config_set_defaults(self) -> None:
    """Setting config DB defaults to avoid duplicates through SELECT"""
    if self.spatial_dim == 3:
      self.set_defaults(CONV_3D_DEFAULTS)
      self.num_dims = 3
    else:
      self.set_defaults(CONV_2D_DEFAULTS)
      self.num_dims = 2

  def set_defaults(self, defaults) -> None:
    """Set fds defaults"""
    k: str
    val: int
    for k, val in self.to_dict().items():
      if k in defaults.keys():
        if val is None:
          setattr(self, k, defaults[k])
          LOGGER.info("Set default %s: %s", k, defaults[k])
        #for 2d configs filter out 3rd dimensional paramaters from unscrupulous users
        elif self.spatial_dim != 3 and k.endswith('_d'):
          setattr(self, k, defaults[k])
          LOGGER.warning("Using default for key %s, because spatial_dim is %s.",
                         k, self.spatial_dim)

    if self.spatial_dim == 3 and len(self.out_layout) != 5:
      raise ValueError(
          f"Layout string {self.out_layout} should be 5 characters"\
          f" for spatial_dim {self.spatial_dim}"
      )
    if self.spatial_dim == 2 and len(self.out_layout) != 4:
      raise ValueError(
          f"Layout string {self.out_layout} should be 4 characters"\
          f" for spatial_dim {self.spatial_dim}"
      )

  @staticmethod
  def get_params(tok1: str) -> str:
    """Get full arg name"""
    return get_fd_name(tok1, TABLE_COLS_CONV_MAP)

  @staticmethod
  def get_check_valid(tok1: str, tok2: str) -> bool:
    """Check if valid conv arg"""
    return conv_arg_valid(tok1, tok2)

  def get_db_obj(self, keep_id: bool = False) -> ConvolutionConfig:
    """Return the DB representation of this object"""
    return ConvolutionConfig(**self.compose_tensors(keep_id))

  def __str__(self) -> str:

    #NOTE: when DB col direction is renamed to forw, col_dict should be removed
    #and replaced with vars(self), but value still needs to map to 1,2 or 4.
    col_dict: dict = vars(self).copy()
    if "direction" in col_dict.keys():
      col_dict["forw"] = int(INVERS_DIR_MAP[col_dict["direction"]])
      col_dict.pop("direction")

    return "./bin/MIOpenDriver " + self.cmd + " " + " ".join(  # type: ignore[operator]
        f'--{key} {val}' for key, val in col_dict.items()
        if key in CONV_CONFIG_COLS or key in TENSOR_COLS or
        key in self.get_common_cols() or key == "forw")

  @staticmethod
  def test_skip_arg(tok1: str) -> bool:
    """Check if token is skipable"""
    if tok1 in CONV_SKIP_ARGS:
      return True
    return False

  def compose_weight_t(self) -> dict:
    """Build weight_tensor"""
    w_dict: dict = {}
    w_dict['data_type'] = TENSOR_PRECISION[self.cmd]
    w_dict['num_dims'] = self.num_dims

    if self.fil_layout in ('NCHW', 'NCDHW'):
      w_dict['dim0'] = self.out_channels
      w_dict['dim1'] = self.in_channels
      w_dict['dim2'] = self.fil_d
      w_dict['dim3'] = self.fil_h
      w_dict['dim4'] = self.fil_w
      w_dict['layout'] = self.fil_layout
    elif self.fil_layout in ('NHWC', 'NDHWC'):
      w_dict['dim0'] = self.out_channels
      w_dict['dim1'] = self.in_channels
      w_dict['dim2'] = self.fil_d
      w_dict['dim3'] = self.fil_h
      w_dict['dim4'] = self.fil_w
      w_dict['layout'] = self.fil_layout

    return w_dict

  def decompose_weight_t(self, db_obj: ConvolutionConfig) -> bool:
    """Use weight_tensor to assign local variables to build driver cmd """
    self.num_dims = db_obj.weight_t.num_dims
    self.fil_layout = db_obj.weight_t.layout

    if self.fil_layout in ('NCHW', 'NCDHW'):
      self.out_channels = db_obj.weight_t.dim0
      self.in_channels = db_obj.weight_t.dim1
      self.fil_d = db_obj.weight_t.dim2
      self.fil_h = db_obj.weight_t.dim3
      self.fil_w = db_obj.weight_t.dim4
    elif self.fil_layout in ('NHWC', 'NDHWC'):
      self.out_channels = db_obj.weight_t.dim0
      self.in_channels = db_obj.weight_t.dim1
      self.fil_d = db_obj.weight_t.dim2
      self.fil_h = db_obj.weight_t.dim3
      self.fil_w = db_obj.weight_t.dim4

    return True

  def set_cmd(self, data_type: str) -> None:
    """Set cmd based on tensor data type"""
    self.cmd = PREC_TO_CMD[ConfigType.convolution][data_type]
