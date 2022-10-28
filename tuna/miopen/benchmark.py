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
""" Module for defining benchmark and model enums """

import enum
from sqlalchemy import Column, UniqueConstraint
from sqlalchemy import Enum, Float, String
from tuna.dbBase.base_class import BASE


#pylint: disable=too-few-public-methods
class FrameworkEnum(enum.Enum):
  """Represents framework enums"""
  PYTORCH = 'Pytorch'
  DEEPBENCH = 'Deepbench'

  def __str__(self):
    return self.value


class Framework(BASE):
  """Represents framework table"""
  __tablename__ = "framework"
  __table_args__ = (UniqueConstraint("framework", name="uq_idx"),)
  framework = Column(Enum(FrameworkEnum), nullable=False)


class Model(BASE):
  """Represents model table"""
  __tablename__ = "model"
  __table_args__ = (UniqueConstraint("model", "version", name="uq_idx"),)
  model = Column(String(length=128), nullable=False)
  version = Column(Float, nullable=False)
