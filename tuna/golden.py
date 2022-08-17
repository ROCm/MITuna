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
"""! @brief Golden table declarations"""
from sqlalchemy import Column, Integer, String, UniqueConstraint, ForeignKey
from sqlalchemy import Float, BigInteger, Boolean, Text
from sqlalchemy.ext.declarative import declared_attr

from tuna.dbBase.base_class import BASE


# pylint: disable=too-few-public-methods
class GoldenMixin():
  """! Represents golden table mixin for golden concrete classes with
     methods and data for reading / writing golden"""

  __table_args__ = {'mysql_engine': 'InnoDB'}
  __mapper_args__ = {'always_refresh': True}

  @declared_attr
  def session(self):
    """session column"""
    return Column(Integer, ForeignKey("session.id"), nullable=False)

  @declared_attr
  def solver(self):
    """! solver column"""
    return Column(Integer, ForeignKey("solver.id"), nullable=False)


class ConvolutionGolden(BASE, GoldenMixin):
  """! Golden table representing MIOpens versioned DBs for convolution operations
     @param BASE Base MITuna DB class
     @param GoldenMixin Mixin for golden tables
  """

  __tablename__ = "conv_golden"
  __table_args__ = (UniqueConstraint("config",
                                     "solver",
                                     "fdb_key",
                                     "alg_lib",
                                     "opencl",
                                     "session",
                                     name="uq_idx"),)

  config = Column(Integer, ForeignKey("conv_config.id"), nullable=False)
  fdb_key = Column(String(length=128), nullable=True)
  params = Column(Text, nullable=False)
  kernel_time = Column(Float, nullable=False)
  workspace_sz = Column(BigInteger, nullable=False)
  alg_lib = Column(String(length=64), nullable=True)
  opencl = Column(Boolean, nullable=False)
