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
"""Represents Batchnorm Golden table definitions """

from sqlalchemy import Column, Integer, UniqueConstraint, ForeignKey
from tuna.dbBase.base_class import BASE
from tuna.miopen.db.mixin_tables import GoldenMixin


class BNGolden(BASE, GoldenMixin):
  """Golden table for batch norm"""
  __tablename__ = "bn_golden"
  __table_args__ = (UniqueConstraint("golden_miopen_v",
                                     "config",
                                     "solver",
                                     "arch",
                                     "num_cu",
                                     name="uq_idx"),)

  config = Column(Integer, ForeignKey("bn_config.id"), nullable=False)

  kernel_group = Column(Integer, nullable=True)
