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
"""Represents Mixin type table class definitions """
import enum
from sqlalchemy.sql import func as sqla_func
from sqlalchemy.databases import mysql
from sqlalchemy import Float, Boolean
from sqlalchemy.dialects.mysql import TINYINT, MEDIUMBLOB, LONGBLOB
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime

from tuna.db.tuna_tables import JobMixin

#pylint: disable=too-few-public-methods


class FinStep(enum.Enum):
  """ Allowed Fin Steps """
  # pylint: disable=invalid-name ; tuna/go_fish.py names valid fin steps as FinStep.__members__
  find_compile = 1
  find_eval = 2
  get_solvers = 3
  get_applicability = 4
  not_fin = 5
  miopen_find_compile = 6
  miopen_find_eval = 7
  miopen_perf_compile = 8
  miopen_perf_eval = 9


class MIOpenJobMixin(JobMixin):
  """Represents MIOpen Mixin class for job tables"""

  compile_start = Column(DateTime,
                         nullable=False,
                         server_default=sqla_func.now())
  compile_end = Column(DateTime, nullable=False, server_default=sqla_func.now())
  eval_start = Column(DateTime, nullable=False, server_default=sqla_func.now())
  eval_end = Column(DateTime, nullable=False, server_default=sqla_func.now())

  solver = Column(String(length=128), nullable=True, server_default="")
  eval_mid = Column(Integer, server_default="-1")
  fin_step = Column(mysql.MSSet(*(list(k for k in FinStep.__members__))),
                    nullable=False,
                    server_default="not_fin")


class ConfigTagMixin():
  """Mixin class for config tags tables"""

  tag = Column(String(length=128), nullable=False, server_default="no_tag")
  recurrent = Column(TINYINT(1), nullable=False, server_default="0")


class SolverApplicabilityMixin():
  """Represents Mixin class for solver_applicability tables"""

  @declared_attr
  def solver(self):
    """solver column"""
    return Column(Integer, ForeignKey("solver.id"), nullable=False, index=True)

  @declared_attr
  def session(self):
    """session key"""
    return Column(Integer, ForeignKey("session.id"), nullable=False, index=True)

  applicable = Column(TINYINT, nullable=False, server_default="1")


class CacheMixin():
  """Represents job_cache table"""

  kernel_blob = Column(LONGBLOB, nullable=False)
  cache_name = Column(String(length=45), nullable=False)


class KernelCacheMixin():
  """Represents Mixin for KernelCache table"""

  kernel_name = Column(String(length=4000), nullable=False)
  kernel_args = Column(String(length=9000), nullable=False)
  kernel_blob = Column(MEDIUMBLOB, nullable=False)
  kernel_hash = Column(String(length=128), nullable=False)
  uncompressed_size = Column(Integer, nullable=False)


class GoldenMixin():
  """Mixin for golden table"""

  @declared_attr
  def session(self):
    """session foreign key"""
    return Column(Integer, ForeignKey("session.id"), nullable=False)

  @declared_attr
  def solver(self):
    """solver foreign key"""
    return Column(Integer,
                  ForeignKey("solver.id",
                             onupdate="CASCADE",
                             ondelete="CASCADE"),
                  nullable=False)

  golden_miopen_v = Column(Integer, nullable=False)
  arch = Column(String(length=20), nullable=False, server_default="")
  num_cu = Column(Integer, nullable=False, server_default="0")


class BenchmarkMixin():
  """Mixin class for bechmark tables"""

  @declared_attr
  def framework(self):
    """Framework Fkey"""
    return Column(Integer, ForeignKey("framework.id"), nullable=False)

  @declared_attr
  def model(self):
    """Model Fkey"""
    return Column(Integer, ForeignKey("model.id"), nullable=False)

  batchsize = Column(Integer, nullable=False, server_default="32")
  gpu_number = Column(Integer, nullable=True, server_default="1")
  driver_cmd = Column(String(length=512), nullable=False)


class SolverAnalyticsMixin():
  """common columns in aggregated & detailed solver analytics tables"""
  # software state description
  golden_miopen_v = Column(Integer, nullable=False)
  # hardware description
  arch = Column(String(20), nullable=False)
  num_cu = Column(Integer, nullable=False)
  opencl = Column(Boolean, nullable=False)
  # convolution problem description
  filter = Column(String(32), nullable=False)
  padding = Column(String(32), nullable=False)
  stride = Column(String(32), nullable=False)
  dilation = Column(String(32), nullable=False)
  layout = Column(String(8), nullable=False)
  precision = Column(String(8), nullable=False)
  direction = Column(String(1), nullable=False)
  # fastest solvers stats
  sf = Column(String(128), nullable=False)  # fastest solver name
  tf = Column(Float, nullable=False)  # fastest solver runtime
  count = Column(Integer, nullable=False)  # fastest solver count
