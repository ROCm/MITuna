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
""" Module for get/set/initialize DB - MIOpen/Conv/Fusion/Batchnorm tables"""

from tuna.machine import Machine
from tuna.miopen.db.benchmark import Framework, Model
from tuna.miopen.db.solver import Solver
from tuna.miopen.db.batch_norm_tables import BNBenchmark
from tuna.miopen.db.convolutionjob_tables import ConvolutionBenchmark
from tuna.miopen.db.tensortable import TensorTable
from tuna.miopen.db.miopen_tables import add_bn_tables
from tuna.miopen.db.miopen_tables import add_conv_tables
from tuna.miopen.db.miopen_tables import add_fusion_tables
from tuna.miopen.db.session import Session


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

  return miopen_tables
