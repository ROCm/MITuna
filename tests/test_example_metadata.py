###############################################################################
#
# MIT License
#
# Copyright (c) 2024 Advanced Micro Devices, Inc.
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
"""Tests for tuna.example.metadata"""
import os
import sys

sys.path.append("../tuna")
sys.path.append("tuna")

from tuna.example import metadata


def test_example_tuning_steps():
  """Test EXAMPLE_TUNING_STEPS constant"""
  assert hasattr(metadata, 'EXAMPLE_TUNING_STEPS')
  assert isinstance(metadata.EXAMPLE_TUNING_STEPS, list)
  assert 'init_session' in metadata.EXAMPLE_TUNING_STEPS
  assert 'execute' in metadata.EXAMPLE_TUNING_STEPS
  assert len(metadata.EXAMPLE_TUNING_STEPS) == 2


def test_example_single_op():
  """Test EXAMPLE_SINGLE_OP constant"""
  assert hasattr(metadata, 'EXAMPLE_SINGLE_OP')
  assert isinstance(metadata.EXAMPLE_SINGLE_OP, list)
  assert 'init_session' in metadata.EXAMPLE_SINGLE_OP
  assert 'execute' in metadata.EXAMPLE_SINGLE_OP
  assert len(metadata.EXAMPLE_SINGLE_OP) == 2


def test_metadata_values():
  """Verify metadata constants have correct values"""
  assert metadata.EXAMPLE_TUNING_STEPS == metadata.EXAMPLE_SINGLE_OP
  assert metadata.EXAMPLE_TUNING_STEPS == ['init_session', 'execute']
