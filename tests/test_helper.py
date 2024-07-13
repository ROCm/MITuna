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

import os

from tuna.lib_utils import get_library
from tuna.miopen.miopen_lib import MIOpen
from tuna.example.example_lib import Example
from tuna.rocmlir.rocmlir_lib import RocMLIR
from tuna.libraries import Library


def test_helper():
  lib_dict = {"lib": Library.MIOPEN}
  lib = get_library(lib_dict)
  assert type(lib) == MIOpen

  lib_dict['lib'] = Library.EXAMPLE
  lib = get_library(lib_dict)
  assert type(lib) == Example

  lib_dict['lib'] = Library.ROCMLIR
  lib = get_library(lib_dict)
  assert type(lib) == RocMLIR
