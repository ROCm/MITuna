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
""" Module for defining Tensor Table and model enums  """

from sqlalchemy import Column, Integer, String, UniqueConstraint
from tuna.dbBase.base_class import BASE

#pylint: disable=too-few-public-methods


class TensorTable(BASE):
  """Represents tensor table"""
  __tablename__ = "tensor"
  __table_args__ = (UniqueConstraint("dim0",
                                     "dim1",
                                     "dim2",
                                     "dim3",
                                     "dim4",
                                     "layout",
                                     "num_dims",
                                     "data_type",
                                     name="uq_idx"),)

  dim0 = Column(Integer, nullable=False, server_default="0")
  dim1 = Column(Integer, nullable=False, server_default="0")
  dim2 = Column(Integer, nullable=False, server_default="0")
  dim3 = Column(Integer, nullable=False, server_default="0")
  dim4 = Column(Integer, nullable=False, server_default="0")
  layout = Column(String(60), nullable=False, server_default="NCHW")
  num_dims = Column(Integer, nullable=False, server_default="2")
  data_type = Column(String(60), nullable=False, server_default="FP32")
