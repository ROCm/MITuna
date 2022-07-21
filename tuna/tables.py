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
"""Module that encapsulates the DB representation based on configuration type"""
from tuna.find_db import ConvolutionFindDB, BNFindDB
from tuna.miopen_tables import ConvolutionJob, ConvolutionConfig, ConvolutionConfigTags
from tuna.miopen_tables import ConvPerfDB, ConvPerfConfig
from tuna.miopen_tables import ConvJobCache, Solver
from tuna.miopen_tables import BNJob, BNConfig, BNPerfDB, BNJobCache, BNFinJobCache, BNConfigTags
from tuna.miopen_tables import ConvSolverApplicability, BNSolverApplicability
from tuna.miopen_tables import ConvFinJobCache, BNKernelCache, ConvolutionKernelCache
from tuna.config_type import ConfigType
from tuna.dbBase.sql_alchemy import DbSession
from tuna.session import Session


#pylint: disable=too-many-instance-attributes
#pylint: disable=too-few-public-methods
class DBTables():
  """Represents db tables based on ConfigType"""

  def __init__(self, **kwargs):
    """Constructor"""
    super().__init__()
    allowed_keys = set(['config_type', 'session_id'])
    self.__dict__.update((key, None) for key in allowed_keys)

    #for pylint
    self.job_table = None
    self.config_table = None
    self.config_tags_table = None
    self.find_db_table = None
    self.solver_app = None
    self.perf_config_table = None
    self.perf_db_table = None
    self.cache_table = None
    self.fin_cache_table = None
    self.solver_table = None
    self.kernel_cache = None
    self.config_type = None
    self.session = None
    self.session_id = None

    self.__dict__.update(
        (key, value) for key, value in kwargs.items() if key in allowed_keys)
    self.set_tables()

  def set_tables(self):
    """Set appropriate tables based on config type"""

    self.solver_table = Solver

    if self.session_id is not None:
      with DbSession() as session:
        query = session.query(Session).filter(Session.id == self.session_id)
        self.session = query.one()

    if self.config_type == ConfigType.batch_norm:
      self.job_table = BNJob
      self.config_table = BNConfig
      self.config_tags_table = BNConfigTags
      self.find_db_table = BNFindDB
      self.solver_app = BNSolverApplicability
      self.perf_config_table = BNConfig
      self.perf_db_table = BNPerfDB
      self.cache_table = BNJobCache
      self.fin_cache_table = BNFinJobCache
      self.kernel_cache = BNKernelCache
    else:
      self.job_table = ConvolutionJob
      self.config_table = ConvolutionConfig
      self.config_tags_table = ConvolutionConfigTags
      self.find_db_table = ConvolutionFindDB
      self.solver_app = ConvSolverApplicability
      self.perf_config_table = ConvPerfConfig
      self.perf_db_table = ConvPerfDB
      self.cache_table = ConvJobCache
      self.fin_cache_table = ConvFinJobCache
      self.kernel_cache = ConvolutionKernelCache
