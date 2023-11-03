#!/usr/bin/env python3
###############################################################################
#
# MIT License
#
# Copyright (c) 2023 Advanced Micro Devices, Inc.
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
"""Module that encapsulates the DB representation of a Driver cmd"""

from typing import Union, Dict, Any
from abc import ABC, abstractmethod
from tuna.utils.logger import setup_logger

LOGGER = setup_logger('driver_base')


class DriverBase(ABC):
  """Represents db tables based on ConfigType"""

  @abstractmethod
  def construct_driver_from_db(self, db_obj: Any) -> bool:
    """Takes a <>_config row and returns a driver cmd"""
    raise NotImplementedError("Not implemented")

  @abstractmethod
  def insert_tensor(self, tensor_dict: dict) -> int:
    """Insert new row into tensor table and return primary key"""
    raise NotImplementedError("Not implemented")

  @abstractmethod
  def get_input_t_id(self) -> int:
    """Build 1 row in tensor table based on layout from fds param
       Details are mapped in metadata LAYOUT"""
    raise NotImplementedError("Not implemented")

  @abstractmethod
  def compose_input_t(self) -> Dict[str, int]:
    """Build input_tensor"""
    raise NotImplementedError("Not implemented")

  @abstractmethod
  def decompose_input_t(self, db_obj: Any) -> bool:
    """Use input_tensor to assign local variables to build driver cmd """
    raise NotImplementedError("Not implemented")

  @abstractmethod
  def compose_fds(self, tok: list, line: str) -> bool:
    """Compose fds from driver line"""
    raise NotImplementedError("Not implemented")

  @abstractmethod
  def get_weight_t_id(self) -> int:
    """Build 1 row in tensor table based on layout from fds param
     Details are mapped in metadata LAYOUT"""
    raise NotImplementedError("Not implemented")

  @abstractmethod
  def parse_driver_line(self, line: str):
    """Parse line and set attributes"""
    raise NotImplementedError("Not implemented")

  @abstractmethod
  def to_dict(self) -> Dict[str, Union[str, int]]:
    """Return class to dictionary"""
    raise NotImplementedError("Not implemented")

  @abstractmethod
  def __eq__(self, other: object) -> bool:
    """Defining equality functionality"""
    raise NotImplementedError("Not implemented")
