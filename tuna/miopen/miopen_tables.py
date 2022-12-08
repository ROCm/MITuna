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
import enum
from sqlalchemy import Column, Integer, String, UniqueConstraint, ForeignKey, DateTime
from sqlalchemy import Text, Enum, Index
from sqlalchemy import Float, BigInteger, Boolean
from sqlalchemy.databases import mysql
from sqlalchemy.dialects.mysql import TINYINT, DOUBLE, MEDIUMBLOB, LONGBLOB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func as sqla_func
from sqlalchemy.ext.declarative import declared_attr

from tuna.dbBase.base_class import BASE
from tuna.machine import Machine
from tuna.find_db import ConvolutionFindDB, BNFindDB
from tuna.config_type import ConfigType
from tuna.miopen.session import Session
from tuna.metadata import DIR_MAP
from tuna.miopen.benchmark import Model, Framework

COMMON_UNIQ_FDS = ["config", "solver", "session"]


#pylint: disable=too-few-public-methods
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


class BNJobCache(BASE, CacheMixin):
  """Represents job_cache table for batch_norm"""
  __tablename__ = "bn_job_cache"
  __table_args__ = (UniqueConstraint("job_id", name="uq_cache_idx"),)

  job_id = Column(Integer, ForeignKey("bn_job.id"), nullable=False)


class BNFinJobCache(BASE, KernelCacheMixin):
  """Represents job_cache table for batch_norm"""
  __tablename__ = "bn_job_cache_fin"

  job_id = Column(Integer,
                  ForeignKey("bn_job.id",
                             onupdate="CASCADE",
                             ondelete="CASCADE"),
                  nullable=False)
  solver_id = Column(Integer,
                     ForeignKey("solver.id",
                                onupdate="CASCADE",
                                ondelete="CASCADE"),
                     nullable=False)


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


class BNKernelCache(BASE, KernelCacheMixin):
  """Represents kernel_cache table for batch_norm"""
  __tablename__ = "bn_kernel_cache"

  kernel_group = Column(Integer, nullable=True)


class Solver(BASE):
  """Represents solver table"""
  __tablename__ = "solver"
  __table_args__ = (UniqueConstraint("solver", name="uq_idx"),)

  solver = Column(String(length=128), unique=True, nullable=False)
  tunable = Column(TINYINT(1), nullable=False, server_default="1")
  config_type = Column(Enum(ConfigType),
                       nullable=False,
                       server_default="convolution")
  is_dynamic = Column(TINYINT(1), nullable=False, server_default="0")


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


class BNConfig(BASE):
  """Represents batch normalization table"""
  __tablename__ = "bn_config"
  __table_args__ = (UniqueConstraint("alpha",
                                     "beta",
                                     "forw",
                                     "verify",
                                     "back",
                                     "mode",
                                     "batchsize",
                                     "run",
                                     "input_tensor",
                                     name="uq_idx"),)

  alpha = Column(Integer, nullable=False, server_default="1.0")
  beta = Column(Integer, nullable=False, server_default="0.0")
  forw = Column(Integer, nullable=False, server_default="1")
  verify = Column(Integer, nullable=False, server_default="1")
  back = Column(Integer, nullable=False, server_default="0")
  mode = Column(Integer, nullable=False, server_default="0")
  batchsize = Column(Integer, nullable=False, server_default="32")
  run = Column(Integer, nullable=False, server_default="0")
  save = Column(Integer, nullable=False, server_default="0")
  input_tensor = Column(Integer, ForeignKey("tensor.id"), nullable=False)
  input_t = relationship("TensorTable",
                         backref="bn_input_tensor",
                         foreign_keys=[input_tensor],
                         lazy="joined")
  in_layout = Column(String(60), nullable=False, server_default="NCHW")
  driver = Column(String(length=512), nullable=False, server_default="")

  def get_direction(self):
    """synthesize direction"""
    return DIR_MAP[(self.forw + 4 * self.back)]


class ConfigTagMixin():
  """Mixin class for config tags tables"""

  tag = Column(String(length=128), nullable=False, server_default="no_tag")
  recurrent = Column(TINYINT(1), nullable=False, server_default="0")


class ConvolutionConfigTags(BASE, ConfigTagMixin):
  """Represents config_tags tables"""
  __tablename__ = "conv_config_tags"
  __table_args__ = (UniqueConstraint("config", "tag", name="uq_idx"),)

  config = Column(Integer, ForeignKey("conv_config.id"), nullable=False)


class BNConfigTags(BASE, ConfigTagMixin):
  """Represents config_tags tables"""
  __tablename__ = "bn_config_tags"
  __table_args__ = (UniqueConstraint("config", "tag", name="uq_idx"),)

  config = Column(Integer, ForeignKey("bn_config.id"), nullable=False)


class FusionConfigTags(BASE, ConfigTagMixin):
  """Represents config_tags tables"""
  __tablename__ = "fusion_config_tags"
  __table_args__ = (UniqueConstraint("config", "tag", name="uq_idx"),)

  config = Column(Integer, ForeignKey("fusion_config.id"), nullable=False)


class JobEnum(enum.Enum):
  """Represents job_enum column in config table"""
  # pylint: disable=invalid-name ; names represent entries in job_enum column
  new = 1
  started = 2
  running = 3
  completed = 4
  timeout = 5
  error_status = 6
  no_update = 7
  errored = 8
  bad_param = 9
  error = 10
  transfer_error = 11
  eval_start = 12
  evaluating = 13
  evaluated = 14
  evaluate_error = 15
  compile_start = 16
  compiling = 17
  compiled = 18
  compile_error = 19
  not_applicable = 20
  aborted = 21
  not_tunable = 22
  compiled_pend = 23
  evaluated_pend = 24


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


class JobMixin():
  """Represents Mixin class for job tables"""

  @declared_attr
  def session(self):
    """session key"""
    return Column(Integer, ForeignKey("session.id"), nullable=False)

  reason = Column(String(length=60), nullable=False, server_default="")
  state = Column(Enum(JobEnum), nullable=False, server_default="new")
  retries = Column(Integer, nullable=False, server_default="0")
  result = Column(Text, nullable=True)

  compile_start = Column(DateTime,
                         nullable=False,
                         server_default=sqla_func.now())
  compile_end = Column(DateTime, nullable=False, server_default=sqla_func.now())
  eval_start = Column(DateTime, nullable=False, server_default=sqla_func.now())
  eval_end = Column(DateTime, nullable=False, server_default=sqla_func.now())

  gpu_id = Column(Integer, nullable=False, server_default="-1")
  kernel_time = Column(DOUBLE, nullable=False, server_default="-1")
  machine_id = Column(Integer, nullable=False, server_default="-1")
  eval_mid = Column(Integer, server_default="-1")
  cache_loc = Column(Text)

  solver = Column(String(length=128), nullable=True, server_default="")
  fin_step = Column(mysql.MSSet(*(list(k for k in FinStep.__members__))),
                    nullable=False,
                    server_default="not_fin")


class ConvolutionJob(BASE, JobMixin):
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


class BNJob(BASE, JobMixin):
  """Represents batch norm job table"""
  __tablename__ = "bn_job"
  __table_args__ = (UniqueConstraint(*COMMON_UNIQ_FDS, name="uq_idx"),)

  config = Column(Integer,
                  ForeignKey("bn_config.id"),
                  nullable=False,
                  index=True)


class FusionJob(BASE, JobMixin):
  """Represents fusions job table"""
  __tablename__ = "fusion_job"
  __table_args__ = (UniqueConstraint(*COMMON_UNIQ_FDS, name="uq_idx"),)

  config = Column(Integer, ForeignKey("fusion_config.id"), nullable=False)


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


class BNSolverApplicability(BASE, SolverApplicabilityMixin):
  """Represents bn_solver_applicability  table"""
  __tablename__ = "bn_solver_applicability"
  __table_args__ = (UniqueConstraint(*COMMON_UNIQ_FDS, name="uq_idx"),)

  config = Column(Integer,
                  ForeignKey("bn_config.id"),
                  nullable=False,
                  index=True)


class SolverFusionApplicability(BASE, SolverApplicabilityMixin):
  """Represents fusion_solver_applicability table"""
  __tablename__ = "fusion_solver_applicability"
  __table_args__ = (UniqueConstraint(*COMMON_UNIQ_FDS, name="uq_idx"),)

  config = Column(Integer, ForeignKey("fusion_config.id"), nullable=False)


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


class BNBenchmark(BASE, BenchmarkMixin):
  """benchmark table for framework and model parameters"""
  __tablename__ = "bn_benchmark"
  __table_args__ = (UniqueConstraint("framework",
                                     "model",
                                     "batchsize",
                                     "gpu_number",
                                     "config",
                                     name="uq_idx"),)

  config = Column(Integer, ForeignKey("bn_config.id"), nullable=False)


class SolverAnalyticsResults(BASE):
  """Table to store results from running SolverAnalytics"""
  __tablename__ = "solver_analytics_results"

  # each row in table must correspond to a unique convolution problem
  __table_args__ = (UniqueConstraint("golden_miopen_v",
                                     "filter",
                                     "padding",
                                     "stride",
                                     "layout",
                                     "precision",
                                     "direction",
                                     name="uq_idx"),)
  
  # columns definitions
  golden_miopen_v = Column(Integer, nullable=False)
  filter = Column(String(32), nullable=False)
  padding = Column(String(32), nullable=False)
  stride = Column(String(32), nullable=False)
  dilation = Column(String(32), nullable=False)
  layout = Column(String(8), nullable=False)
  precision = Column(String(8), nullable=False)
  direction = Column(String(1), nullable=False)
  sf = Column(String(128), nullable=False) # fastest solver
  tf = Column(Float, nullable=False) # fastest solver runtime
  ta = Column(Float, nullable=True) # alternate solver runtime (null if no alternate solver)
  difference = Column(Float, nullable=True) # runtime difference (null if no alternate)
  ratio = Column(Float, nullable=True) # runtime ratio (null if infinity or no alternate)
  count = Column(Integer, nullable=False)


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
  miopen_tables.append(ConvolutionBenchmark())
  miopen_tables.append(BNBenchmark())

  miopen_tables = add_conv_tables(miopen_tables)
  miopen_tables = add_fusion_tables(miopen_tables)
  miopen_tables = add_bn_tables(miopen_tables)

  miopen_tables.append(SolverAnalyticsResults())

  return miopen_tables
