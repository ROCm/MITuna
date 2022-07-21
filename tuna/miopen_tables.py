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
from sqlalchemy import Text, Enum
from sqlalchemy.databases import mysql
from sqlalchemy.dialects.mysql import TINYINT, DOUBLE, MEDIUMBLOB, LONGBLOB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func as sqla_func
from sqlalchemy.ext.declarative import declared_attr

from tuna.dbBase.base_class import BASE
from tuna.machine import Machine
from tuna.find_db import ConvolutionFindDB, BNFindDB
from tuna.config_type import ConfigType
from tuna.session import Session
from tuna.metadata import DIR_MAP

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

  conv_find_db_key = Column(Integer,
                            ForeignKey("conv_find_db.id"),
                            nullable=False)
  conv_find_db_entries = relationship("ConvolutionFindDB",
                                      back_populates="blobs")


class BNKernelCache(BASE, KernelCacheMixin):
  """Represents kernel_cache table for batch_norm"""
  __tablename__ = "bn_kernel_cache"

  bn_find_db_key = Column(Integer, ForeignKey("bn_find_db.id"), nullable=False)
  bn_find_db_entries = relationship("BNFindDB", back_populates="blobs")


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
  conv_mode = Column(String(length=40), nullable=False, server_default="conv")
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
  out_layout = Column(String(60), nullable=False, server_default="NCHW")

  def get_direction(self):
    """synthesize direction"""
    return DIR_MAP[str(self.forw + 4 * self.back)]


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


class FinStep(enum.Enum):
  """ Allowed Fin Steps """
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

  state = Column(Enum(JobEnum), nullable=False, server_default="new")
  compile_start = Column(DateTime,
                         nullable=False,
                         server_default=sqla_func.now())
  compile_end = Column(DateTime, nullable=False, server_default=sqla_func.now())
  eval_start = Column(DateTime, nullable=False, server_default=sqla_func.now())
  eval_end = Column(DateTime, nullable=False, server_default=sqla_func.now())
  result = Column(String(length=60), nullable=False, server_default="")
  reason = Column(String(length=60), nullable=False, server_default="")
  machine_id = Column(Integer, nullable=False, server_default="-1")
  eval_mid = Column(Integer, server_default="-1")
  cache_loc = Column(Text)
  gpu_id = Column(Integer, nullable=False, server_default="-1")
  retries = Column(Integer, nullable=False, server_default="0")
  solver = Column(String(length=128), nullable=True, server_default="")
  kernel_time = Column(DOUBLE, nullable=False, server_default="-1")
  fin_step = Column(mysql.MSSet(*(list(k for k in FinStep.__members__))),
                    nullable=False,
                    server_default="not_fin")


class ConvolutionJob(BASE, JobMixin):
  """Represents convolutions job table"""
  __tablename__ = "conv_job"
  __table_args__ = (UniqueConstraint(*COMMON_UNIQ_FDS,
                                     "reason",
                                     "valid",
                                     name="uq_idx"),)

  config = Column(Integer, ForeignKey("conv_config.id"), nullable=False)


class BNJob(BASE, JobMixin):
  """Represents batch norm job table"""
  __tablename__ = "bn_job"
  __table_args__ = (UniqueConstraint(*COMMON_UNIQ_FDS, "reason",
                                     name="uq_idx"),)

  config = Column(Integer, ForeignKey("bn_config.id"), nullable=False)


class FusionJob(BASE, JobMixin):
  """Represents fusions job table"""
  __tablename__ = "fusion_job"
  __table_args__ = (UniqueConstraint(*COMMON_UNIQ_FDS, "reason",
                                     name="uq_idx"),)

  config = Column(Integer, ForeignKey("fusion_config.id"), nullable=False)


class SolverApplicabilityMixin():
  """Represents Mixin class for solver_applicability tables"""

  @declared_attr
  def solver(self):
    """solver column"""
    return Column(Integer, ForeignKey("solver.id"), nullable=False)

  @declared_attr
  def session(self):
    """session key"""
    return Column(Integer, ForeignKey("session.id"), nullable=False)

  applicable = Column(TINYINT, nullable=False, server_default="1")


class ConvSolverApplicability(BASE, SolverApplicabilityMixin):
  """Represents conv_solver_applicability table"""
  __tablename__ = "conv_solver_applicability"
  __table_args__ = (UniqueConstraint(*COMMON_UNIQ_FDS, name="uq_idx"),)

  config = Column(Integer, ForeignKey("conv_config.id"), nullable=False)


class BNSolverApplicability(BASE, SolverApplicabilityMixin):
  """Represents bn_solver_applicability  table"""
  __tablename__ = "bn_solver_applicability"
  __table_args__ = (UniqueConstraint(*COMMON_UNIQ_FDS, name="uq_idx"),)

  config = Column(Integer, ForeignKey("bn_config.id"), nullable=False)


class SolverFusionApplicability(BASE, SolverApplicabilityMixin):
  """Represents fusion_solver_applicability table"""
  __tablename__ = "fusion_solver_applicability"
  __table_args__ = (UniqueConstraint(*COMMON_UNIQ_FDS, name="uq_idx"),)

  config = Column(Integer, ForeignKey("fusion_config.id"), nullable=False)


class PerfConfigMixin():
  """Represents perf_db config table mixin"""
  config = Column(Integer, ForeignKey("config.id"), nullable=False)
  layout = Column(String(60), nullable=False, server_default="NCHW")
  data_type = Column(String(60), nullable=False, server_default="FP32")
  bias = Column(Integer, nullable=False, server_default="0")
  valid = Column(TINYINT(1), nullable=False, server_default="1")


class ConvPerfConfig(BASE, PerfConfigMixin):
  """Represents perf_db config table for convolutions"""
  __tablename__ = "conv_perf_config"
  __table_args__ = (UniqueConstraint("config",
                                     "layout",
                                     "data_type",
                                     "bias",
                                     name="uq_idx"),)

  config = Column(Integer, ForeignKey("conv_config.id"), nullable=False)


class BNPerfConfig(BASE, PerfConfigMixin):
  """Represents perf_db config table for batch norm"""
  __tablename__ = "bn_perf_config"
  __table_args__ = (UniqueConstraint("config",
                                     "layout",
                                     "data_type",
                                     "bias",
                                     name="uq_idx"),)

  config = Column(Integer, ForeignKey("bn_config.id"), nullable=False)


class PerfDBMixin():
  """perf databades"""

  @declared_attr
  def solver(self):
    """solver column"""
    return Column(Integer, ForeignKey("solver.id"), nullable=False)

  @declared_attr
  def session(self):
    """session column"""
    return Column(Integer, ForeignKey("session.id"), nullable=False)

  params = Column(Text, nullable=False)


class ConvPerfDB(BASE, PerfDBMixin):
  """perf db for convolutions"""
  __tablename__ = "conv_perf_db"
  __table_args__ = (UniqueConstraint("solver",
                                     "miopen_config",
                                     "session",
                                     name="uq_idx"),)

  miopen_config = Column(Integer,
                         ForeignKey("conv_perf_config.id"),
                         nullable=False)


class BNPerfDB(BASE, PerfDBMixin):
  """perf db for batch norm"""
  __tablename__ = "bn_perf_db"
  __table_args__ = (UniqueConstraint("solver",
                                     "miopen_config",
                                     "session",
                                     name="uq_idx"),)

  miopen_config = Column(Integer,
                         ForeignKey("bn_perf_config.id"),
                         nullable=False)


class GoldenMixin():
  """Mixin for golden table"""

  @declared_attr
  def session(self):
    """session foreign key"""
    return Column(Integer, ForeignKey("session.id"), nullable=False)

  @declared_attr
  def solver_id(self):
    """solver_id foreign key"""
    return Column(Integer,
                  ForeignKey("solver.id",
                             onupdate="CASCADE",
                             ondelete="CASCADE"),
                  nullable=False)

  golden_miopen_v = Column(String(length=64), nullable=False)
  is_winning = Column(TINYINT(1), nullable=False, server_default="0")
  is_app = Column(TINYINT(1), nullable=False, server_default="0")
  arch = Column(String(length=20), nullable=False, server_default="")
  num_cu = Column(Integer, nullable=False, server_default="0")


class ConvolutionGolden(BASE, GoldenMixin):
  """Golden table for convolution"""
  __tablename__ = "conv_golden"
  __table_args__ = (UniqueConstraint("golden_miopen_v",
                                     "perf_db",
                                     "find_db",
                                     "config",
                                     "session",
                                     "arch",
                                     "num_cu",
                                     name="uq_idx"),)

  perf_db = Column(Integer, ForeignKey("conv_perf_db.id"), nullable=False)
  find_db = Column(Integer, ForeignKey("conv_find_db.id"), nullable=False)
  config = Column(Integer, ForeignKey("conv_config.id"), nullable=False)


class BNGolden(BASE, GoldenMixin):
  """Golden table for batch norm"""
  __tablename__ = "bn_golden"
  __table_args__ = (UniqueConstraint("golden_miopen_v",
                                     "perf_db",
                                     "find_db",
                                     "config",
                                     "session",
                                     "arch",
                                     "num_cu",
                                     name="uq_idx"),)

  perf_db = Column(Integer, ForeignKey("bn_perf_db.id"), nullable=False)
  find_db = Column(Integer, ForeignKey("bn_find_db.id"), nullable=False)
  config = Column(Integer, ForeignKey("bn_config.id"), nullable=False)


def add_conv_tables(miopen_tables):
  """Append Convolution specific MIOpen DB tables"""
  miopen_tables.append(ConvolutionConfig())
  miopen_tables.append(ConvolutionJob)
  miopen_tables.append(ConvolutionConfigTags())
  miopen_tables.append(ConvSolverApplicability())
  miopen_tables.append(ConvolutionFindDB)
  miopen_tables.append(ConvolutionKernelCache())
  miopen_tables.append(ConvPerfConfig())
  miopen_tables.append(ConvPerfDB())
  miopen_tables.append(ConvJobCache())
  miopen_tables.append(ConvFinJobCache())
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
  miopen_tables.append(BNFindDB())
  miopen_tables.append(BNKernelCache())
  miopen_tables.append(BNPerfConfig())
  miopen_tables.append(BNPerfDB())
  miopen_tables.append(BNJobCache())
  miopen_tables.append(BNFinJobCache())
  miopen_tables.append(BNGolden())
  return miopen_tables


def get_miopen_tables():
  """Returns a list of all MIOpen Tuna DB tables"""
  miopen_tables = []
  miopen_tables.append(Solver())
  miopen_tables.append(Session())
  miopen_tables.append(Machine(local_machine=True))
  miopen_tables.append(TensorTable())

  miopen_tables = add_conv_tables(miopen_tables)
  miopen_tables = add_fusion_tables(miopen_tables)
  miopen_tables = add_bn_tables(miopen_tables)

  return miopen_tables
