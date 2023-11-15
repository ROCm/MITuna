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
from tuna.miopen.db.miopen_tables import ConvolutionConfig

class DriverBase(ABC):
  """Represents db tables based on ConfigType"""

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
