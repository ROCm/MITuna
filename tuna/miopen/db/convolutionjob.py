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
"""ConvolutionJob table """
import enum
from sqlalchemy import Column, Integer, String, UniqueConstraint, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy import Index
from sqlalchemy.sql import func as sqla_func
from sqlalchemy.databases import mysql
from tuna.dbBase.base_class import BASE
from tuna.db.tuna_tables import JobMixin

COMMON_UNIQ_FDS = ["config", "solver", "session"]

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
