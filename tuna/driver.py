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

from typing import List, Union, Dict, Any
from abc import ABC, abstractmethod
from tuna.utils.logger import setup_logger
from tuna.miopen.db.miopen_tables import ConvolutionConfig

LOGGER = setup_logger('driver_base')


class DriverBase(ABC):
  """Represents db tables based on ConfigType"""

  def __init__(self,
               line: str = str(),
               db_obj: ConvolutionConfig = None) -> None:
    self.tensor_attr: List[str] = []
    self.tensor_id_map: Dict[str, int] = {}

    if line:
      if not self.construct_driver(line):
        raise ValueError(f"Error creating Driver from line: '{line}'")
    elif db_obj:
      if not self.construct_driver_from_db(db_obj):
        raise ValueError(
            f"Error creating Driver from db obj: '{db_obj.to_dict()}'")
    else:
      raise ValueError(
          "Error creating Driver. MIOpen Driver cmd line or db_obj required")

  @abstractmethod
  def construct_driver(self, line: str) -> bool:
    """Takes a MIOpenDriver cmd or PDB key"""
    raise NotImplementedError("Not implemented")

  @abstractmethod
  def construct_driver_from_db(self, db_obj: Any) -> bool:
    """Takes a <>_config row and returns a driver cmd"""
    raise NotImplementedError("Not implemented")

  @abstractmethod
  def compose_fds(self, tok: list, line: str) -> bool:
    """Compose fds from driver line"""
    raise NotImplementedError("Not implemented")

  @abstractmethod
  def to_dict(self) -> Dict[str, Union[str, int]]:
    """Return class to dictionary"""
    raise NotImplementedError("Not implemented")

  @abstractmethod
  def __eq__(self, other: object) -> bool:
    """Defining equality functionality"""
    raise NotImplementedError("Not implemented")

  @abstractmethod
  def get_db_obj(self, keep_id: bool = False) -> ConvolutionConfig:
    """Return the DB representation of this object"""
    raise NotImplementedError("Not implemented")
