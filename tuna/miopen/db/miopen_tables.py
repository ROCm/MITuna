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
""" Module for creating DB tables"""

from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, UniqueConstraint, ForeignKey
from tuna.dbBase.base_class import BASE
from tuna.machine import Machine
from tuna.miopen.db.batch_norm_tables import BNBenchmark, BNConfig
from tuna.miopen.db.batch_norm_tables import BNConfigTags, BNFinJobCache
from tuna.miopen.db.batch_norm_tables import BNJob, BNJobCache, BNKernelCache
from tuna.miopen.db.batch_norm_tables import BNSolverApplicability
from tuna.miopen.db.convolutionjob_tables import CacheMixin, ConfigTagMixin, ConvolutionJob
from tuna.miopen.db.convolutionjob_tables import ConvFinJobCache, ConvJobCache
from tuna.miopen.db.convolutionjob_tables import ConvSolverAnalyticsAggregated
from tuna.miopen.db.convolutionjob_tables import ConvSolverAnalyticsDetailed
from tuna.miopen.db.convolutionjob_tables import ConvSolverApplicability, ConvolutionBenchmark
from tuna.miopen.db.convolutionjob_tables import ConvolutionConfig, ConvolutionConfigTags
from tuna.miopen.db.convolutionjob_tables import ConvolutionGolden, ConvolutionKernelCache
from tuna.miopen.db.convolutionjob_tables import GoldenMixin, KernelCacheMixin
from tuna.miopen.db.convolutionjob_tables import MIOpenJobMixin, SolverApplicabilityMixin
from tuna.miopen.db.find_db import ConvolutionFindDB, BNFindDB
from tuna.miopen.db.session import Session
from tuna.miopen.db.tensortable import TensorTable
from tuna.miopen.utils.metadata import DIR_MAP
from tuna.miopen.db.benchmark import Model, Framework
from tuna.miopen.db.solver import Solver

COMMON_UNIQ_FDS = ["config", "solver", "session"]


#pylint: disable=too-few-public-methods
class JobCache(BASE, CacheMixin):
  """Represents job_cache table"""

  __tablename__ = "job_cache"
  __table_args__ = (UniqueConstraint("job_id", name="uq_cache_idx"),)

  job_id = Column(Integer, ForeignKey("job.id"), nullable=False)


class FinJobCache(BASE, KernelCacheMixin):
  """Represents job_cache table"""
  __tablename__ = "job_cache_fin"

  job_id = Column(Integer,
                  ForeignKey("job.id", onupdate="CASCADE", ondelete="CASCADE"),
                  nullable=False)
  solver_id = Column(Integer,
                     ForeignKey("solver.id",
                                onupdate="CASCADE",
                                ondelete="CASCADE"),
                     nullable=False)


class FusionConfig(BASE):
  """Represents fusion table"""
  __tablename__ = "fusion_config"
  __table_args__ = (UniqueConstraint("input_tensor",
                                     "weight_tensor",
                                     "activ_mode",
                                     "fusion_mode",
                                     name="uq_idx"),)

  input_tensor = Column(Integer, ForeignKey("tensor.id"), nullable=False)
  input_t = relationship("TensorTable",
                         backref="input_tensor_fusion",
                         foreign_keys=[input_tensor],
                         lazy="joined")
  weight_tensor = Column(Integer, ForeignKey("tensor.id"), nullable=False)
  activ_mode = Column(Integer, nullable=False, server_default="1")
  fusion_mode = Column(Integer, nullable=False, server_default="1")


def get_direction(self):
  """synthesize direction"""
  return DIR_MAP[(self.forw + 4 * self.back)]


class FusionConfigTags(BASE, ConfigTagMixin):
  """Represents config_tags tables"""
  __tablename__ = "fusion_config_tags"
  __table_args__ = (UniqueConstraint("config", "tag", name="uq_idx"),)

  config = Column(Integer, ForeignKey("fusion_config.id"), nullable=False)


class FusionJob(BASE, MIOpenJobMixin):
  """Represents fusions job table"""
  __tablename__ = "fusion_job"
  __table_args__ = (UniqueConstraint(*COMMON_UNIQ_FDS, name="uq_idx"),)

  config = Column(Integer, ForeignKey("fusion_config.id"), nullable=False)


class SolverFusionApplicability(BASE, SolverApplicabilityMixin):
  """Represents fusion_solver_applicability table"""
  __tablename__ = "fusion_solver_applicability"
  __table_args__ = (UniqueConstraint(*COMMON_UNIQ_FDS, name="uq_idx"),)

  config = Column(Integer, ForeignKey("fusion_config.id"), nullable=False)


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


def add_conv_tables(miopen_tables):
  """Append Convolution specific MIOpen DB tables"""
  miopen_tables.append(ConvolutionConfig())
  miopen_tables.append(ConvolutionJob())
  miopen_tables.append(ConvolutionConfigTags())
  miopen_tables.append(ConvSolverApplicability())
  miopen_tables.append(ConvolutionKernelCache())
  miopen_tables.append(ConvJobCache())
  miopen_tables.append(ConvFinJobCache())
  miopen_tables.append(ConvolutionFindDB())
  miopen_tables.append(ConvolutionGolden())
  miopen_tables.append(ConvSolverAnalyticsAggregated())
  miopen_tables.append(ConvSolverAnalyticsDetailed())
  miopen_tables.append(ConvolutionBenchmark())
  return miopen_tables


def add_fusion_tables(miopen_tables):
  """Append Fusion specific MIOpen DB tables"""
  miopen_tables.append(FusionConfig())
  miopen_tables.append(SolverFusionApplicability())
  miopen_tables.append(FusionJob())
  miopen_tables.append(FusionConfigTags())
  return miopen_tables


def add_bn_tables(miopen_tables):
  """Append BatchNorm specific MIOpen DB tables"""
  miopen_tables.append(BNConfig())
  miopen_tables.append(BNJob())
  miopen_tables.append(BNConfigTags())
  miopen_tables.append(BNSolverApplicability())
  miopen_tables.append(BNKernelCache())
  miopen_tables.append(BNJobCache())
  miopen_tables.append(BNFinJobCache())
  miopen_tables.append(BNFindDB())
  miopen_tables.append(BNGolden())
  miopen_tables.append(BNBenchmark())
  return miopen_tables


def get_miopen_tables():
  """Returns a list of all MIOpen Tuna DB tables"""
  miopen_tables = []
  miopen_tables.append(Solver())
  miopen_tables.append(Session())
  miopen_tables.append(Framework())
  miopen_tables.append(Model())
  miopen_tables.append(Machine(local_machine=True))
  miopen_tables.append(TensorTable())

  miopen_tables = add_conv_tables(miopen_tables)
  miopen_tables = add_fusion_tables(miopen_tables)
  miopen_tables = add_bn_tables(miopen_tables)

  miopen_tables.append(ConvolutionBenchmark())
  miopen_tables.append(BNBenchmark())

  return miopen_tables
