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

from tuna.miopen.db.find_db import BNFindDB, ConvolutionFindDB
from tuna.miopen.db.bn_golden_tables import BNGolden
from tuna.miopen.db.fusion_config_tables import FusionConfig
from tuna.miopen.db.fusion_config_tables import FusionConfigTags, FusionJob
from tuna.miopen.db.fusion_config_tables import SolverFusionApplicability
from tuna.miopen.db.batch_norm_tables import BNBenchmark, BNConfig
from tuna.miopen.db.batch_norm_tables import BNConfigTags, BNFinJobCache
from tuna.miopen.db.batch_norm_tables import BNJob, BNJobCache, BNKernelCache
from tuna.miopen.db.batch_norm_tables import BNSolverApplicability
from tuna.miopen.db.convolutionjob_tables import ConvFinJobCache
from tuna.miopen.db.convolutionjob_tables import ConvJobCache
from tuna.miopen.db.convolutionjob_tables import ConvSolverAnalyticsAggregated
from tuna.miopen.db.convolutionjob_tables import ConvSolverAnalyticsDetailed
from tuna.miopen.db.convolutionjob_tables import ConvSolverApplicability
from tuna.miopen.db.convolutionjob_tables import ConvolutionBenchmark
from tuna.miopen.db.convolutionjob_tables import ConvolutionConfig
from tuna.miopen.db.convolutionjob_tables import ConvolutionConfigTags
from tuna.miopen.db.convolutionjob_tables import ConvolutionGolden, ConvolutionJob
from tuna.miopen.db.convolutionjob_tables import ConvolutionKernelCache
from tuna.miopen.utils.metadata import DIR_MAP
COMMON_UNIQ_FDS = ["config", "solver", "session"]


#pylint: disable=too-few-public-methods
def get_direction(self):
  """synthesize direction"""
  return DIR_MAP[(self.forw + 4 * self.back)]


def add_conv_tables(miopen_tables):
  """ Append Convolution specific MIOpen DB tables """
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
  """ Append Fusion specific MIOpen DB tables"""
  miopen_tables.append(FusionConfig())
  miopen_tables.append(SolverFusionApplicability())
  miopen_tables.append(FusionJob())
  miopen_tables.append(FusionConfigTags())
  return miopen_tables


def add_bn_tables(miopen_tables):
  """ Append BatchNorm specific MIOpen DB tables"""
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
