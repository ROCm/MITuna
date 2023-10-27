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

from typing import List, Union, Dict
from abc import ABC, abstractmethod
from tuna.utils.logger import setup_logger
from tuna.miopen.db.miopen_tables import ConvolutionConfig

LOGGER = setup_logger('driver_base')


class DriverBase(ABC):
  """Represents db tables based on ConfigType"""

  @abstractmethod
  def parse_row(self, db_obj: ConvolutionConfig):
    """Overloaded method.Defined in conv&bn driver child class"""
    raise NotImplementedError("Not implemented")

  @staticmethod
  @abstractmethod
  def test_skip_arg(tok1: str):
    """Overloaded method.Defined in conv&br driver child class"""
    raise NotImplementedError("Not implemented")

  @staticmethod
  @abstractmethod
  def get_params(tok1: str):
    """Overloaded method.Defined in conv&br driver child class"""
    raise NotImplementedError("Not implemented")

  @staticmethod
  @abstractmethod
  def get_check_valid(tok1: str, tok2: Union[str, int]):
    """Overloaded method.Defined in conv&br driver child class"""
    raise NotImplementedError("Not implemented")

  def to_dict(self) -> Dict[str, Union[str, int]]:
    """Return class to dictionary"""
    copy_dict: Dict[str, Union[str, int]] = {}
    key: str
    value: Union[int, str]
    for key, value in vars(self).items():
      if key == "_cmd":
        copy_dict["cmd"] = value
      else:
        copy_dict[key] = value
    return copy_dict

  def __eq__(self, other: object) -> bool:
    """Defining equality functionality"""
    if not isinstance(other, DriverBase):
      return NotImplemented
    if self.__class__ != other.__class__:
      return False
    return vars(self) == vars(other)
