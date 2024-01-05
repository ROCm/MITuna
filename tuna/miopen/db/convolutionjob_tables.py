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
"""Represents ConvolutionJob table definitions """
from sqlalchemy import Column, Integer, String, UniqueConstraint, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy import Index
from sqlalchemy import Float, BigInteger, Boolean
from tuna.dbBase.base_class import BASE
from tuna.miopen.db.mixin_tables import BenchmarkMixin, CacheMixin
from tuna.miopen.db.mixin_tables import ConfigTagMixin, GoldenMixin
from tuna.miopen.db.mixin_tables import KernelCacheMixin, MIOpenJobMixin
from tuna.miopen.db.mixin_tables import SolverAnalyticsMixin, SolverApplicabilityMixin

COMMON_UNIQ_FDS = ["config", "solver", "session"]


#pylint: disable=too-few-public-methods
#pylint: disable=duplicate-code
class ConvolutionJob(BASE, MIOpenJobMixin):
  """Represents convolutions job table"""
  __tablename__ = "conv_job"
  __table_args__ = (UniqueConstraint(*COMMON_UNIQ_FDS, name="uq_idx"),)

  config = Column(Integer,
                  ForeignKey("conv_config.id"),
                  nullable=False,
                  index=True)
  get_job_ids1 = Index('get_job_idx1', 'session', 'valid', 'reason', 'fin_step',
                       'retries')
  get_job_ids2 = Index('get_job_idx2', 'session', 'valid')
  get_job_ids3 = Index('get_job_idx3', 'session', 'valid', 'retries')
  get_job_compile = Index('get_job_compile', 'valid', 'state', 'reason',
                          'session')


class ConvolutionConfig(BASE):
  """Represents convolution config table"""
  __tablename__ = "conv_config"

  batchsize = Column(Integer, nullable=False, server_default="0")
  spatial_dim = Column(Integer, nullable=False, server_default="2")
  pad_h = Column(Integer, nullable=False, server_default="0")
  pad_w = Column(Integer, nullable=False, server_default="0")
  pad_d = Column(Integer, nullable=False, server_default="0")
  conv_stride_h = Column(Integer, nullable=False, server_default="1")
  conv_stride_w = Column(Integer, nullable=False, server_default="1")
  conv_stride_d = Column(Integer, nullable=False, server_default="1")
  dilation_h = Column(Integer, nullable=False, server_default="1")
  dilation_w = Column(Integer, nullable=False, server_default="1")
  dilation_d = Column(Integer, nullable=False, server_default="1")
  group_count = Column(Integer, nullable=False, server_default="1")
  mode = Column(String(length=40), nullable=False, server_default="conv")
  pad_mode = Column(String(length=40), nullable=False, server_default="default")
  trans_output_pad_h = Column(Integer, nullable=False, server_default="0")
  trans_output_pad_w = Column(Integer, nullable=False, server_default="0")
  trans_output_pad_d = Column(Integer, nullable=False, server_default="0")
  direction = Column(String(length=8), nullable=False)
  input_tensor = Column(Integer, ForeignKey("tensor.id"), nullable=False)
  weight_tensor = Column(Integer, ForeignKey("tensor.id"), nullable=False)
  input_t = relationship("TensorTable",
                         backref="conv_input_tensor",
                         foreign_keys=[input_tensor],
                         lazy="joined")
  weight_t = relationship("TensorTable",
                          backref="weight_tensor",
                          foreign_keys=[weight_tensor],
                          lazy="joined")
  out_layout = Column(String(60), nullable=False, server_default="NCHW")
  md5 = Column(String(length=40), nullable=False, unique=True)
  driver = Column(String(length=512), nullable=False, server_default="")


class ConvolutionConfigTags(BASE, ConfigTagMixin):
  """Represents config_tags tables"""
  __tablename__ = "conv_config_tags"
  __table_args__ = (UniqueConstraint("config", "tag", name="uq_idx"),)

  config = Column(Integer, ForeignKey("conv_config.id"), nullable=False)


class ConvSolverApplicability(BASE, SolverApplicabilityMixin):
  """Represents conv_solver_applicability table"""
  __tablename__ = "conv_solver_applicability"
  __table_args__ = (UniqueConstraint(*COMMON_UNIQ_FDS, name="uq_idx"),)

  config = Column(Integer,
                  ForeignKey("conv_config.id"),
                  nullable=False,
                  index=True)
  app_idx = Index('app_idx', 'config', 'solver', 'session')
  sess_cfg = Index('sess_cfg', 'session', 'config')


class ConvJobCache(BASE, CacheMixin):
  """Represents job_cache table for convolutions"""
  __tablename__ = "conv_job_cache"
  __table_args__ = (UniqueConstraint("job_id", name="uq_cache_idx"),)

  job_id = Column(Integer, ForeignKey("conv_job.id"), nullable=False)


class ConvFinJobCache(BASE, KernelCacheMixin):
  """Represents job_cache table"""
  __tablename__ = "conv_job_cache_fin"

  job_id = Column(Integer,
                  ForeignKey("conv_job.id",
                             onupdate="CASCADE",
                             ondelete="CASCADE"),
                  nullable=False)
  solver_id = Column(Integer,
                     ForeignKey("solver.id",
                                onupdate="CASCADE",
                                ondelete="CASCADE"),
                     nullable=False)


class ConvolutionKernelCache(BASE, KernelCacheMixin):
  """Represents kernel_cache table for convolutions"""
  __tablename__ = "conv_kernel_cache"

  kernel_group = Column(Integer, nullable=True)


class ConvolutionGolden(BASE, GoldenMixin):
  """Golden table for convolution"""
  __tablename__ = "conv_golden"
  __table_args__ = (UniqueConstraint("golden_miopen_v",
                                     "config",
                                     "solver",
                                     "arch",
                                     "num_cu",
                                     name="uq_idx"),)

  config = Column(Integer, ForeignKey("conv_config.id"), nullable=False)

  fdb_key = Column(String(length=128), nullable=True)
  params = Column(String(length=128), nullable=True)
  kernel_time = Column(Float, nullable=False)
  workspace_sz = Column(BigInteger, nullable=False)
  alg_lib = Column(String(length=64), nullable=True)
  opencl = Column(Boolean, nullable=False)

  kernel_group = Column(Integer, nullable=True)


class ConvolutionBenchmark(BASE, BenchmarkMixin):
  """benchmark table for framework and model parameters"""
  __tablename__ = "conv_benchmark"
  __table_args__ = (UniqueConstraint("framework",
                                     "model",
                                     "batchsize",
                                     "gpu_number",
                                     "config",
                                     name="uq_idx"),)

  config = Column(Integer, ForeignKey("conv_config.id"), nullable=False)


class ConvSolverAnalyticsAggregated(BASE, SolverAnalyticsMixin):
  """Table to store aggregated results from SolverAnalytics"""
  __tablename__ = "conv_solver_analytics_aggregated"

  __table_args__ = (UniqueConstraint("golden_miopen_v",
                                     "arch",
                                     "num_cu",
                                     "opencl",
                                     "filter",
                                     "padding",
                                     "stride",
                                     "dilation",
                                     "layout",
                                     "precision",
                                     "direction",
                                     "sf",
                                     name="uq_idx"),)

  # additional stats (null if no alternate solver is available)
  ta = Column(Float, nullable=True)  # alternate solver runtime
  difference = Column(Float, nullable=True)  # runtime difference
  ratio = Column(Float, nullable=True)  # runtime ratio (null if infinity)


class ConvSolverAnalyticsDetailed(BASE, SolverAnalyticsMixin):
  """Table to store detailed results from SolverAnalytics"""
  __tablename__ = "conv_solver_analytics_detailed"

  __table_args__ = (UniqueConstraint("golden_miopen_v",
                                     "arch",
                                     "num_cu",
                                     "opencl",
                                     "filter",
                                     "padding",
                                     "stride",
                                     "dilation",
                                     "layout",
                                     "precision",
                                     "direction",
                                     "sf",
                                     "sa",
                                     name="uq_idx"),)

  # additional stats
  sa = Column(String(128), nullable=False)  # alternate solver
  ta = Column(Float, nullable=True)  # alternate solver runtime
  difference = Column(Float, nullable=True)  # runtime difference
  ratio = Column(Float, nullable=True)  # runtime ratio (null if infinity)
