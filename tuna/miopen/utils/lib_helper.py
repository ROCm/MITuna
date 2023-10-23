#!/usr/bin/env python3
###############################################################################
#
# MIT License
#
# Copyright (c) 2023 Advanced Micro Devices, Inc.
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
"""Utility module for miopen library"""

from tuna.miopen.worker.fin_builder import FinBuilder
from tuna.miopen.worker.fin_eval import FinEvaluator
from tuna.miopen.worker.fin_class import FinClass
from tuna.worker_interface import WorkerInterface


def get_worker(kwargs, worker_type):
  """Return worker based on worker_type"""
  if worker_type is "fin_class_worker":
    return FinClass(**kwargs)
  elif worker_type is "fin_build_worker":
    return FinBuilder(**kwargs)
  elif worker_type is "fin_eval_worker":
    return FinEvaluator(**kwargs)
  else:
    return WorkerInterface(kwargs)

