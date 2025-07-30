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
"""Represents Fusion config table class definitions """

from sqlalchemy import Column, Integer, UniqueConstraint, ForeignKey
from sqlalchemy.orm import relationship
from tuna.dbBase.base_class import BASE
from tuna.miopen.db.mixin_tables import ConfigTagMixin, MIOpenJobMixin, SolverApplicabilityMixin

COMMON_UNIQ_FDS = ["config", "solver", "session"]


#pylint: disable=too-few-public-methods
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
