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
"""Factory method to get library"""

from typing import Union, Dict, Any
from tuna.libraries import Library
from tuna.miopen.miopen_lib import MIOpen
from tuna.example.example_lib import Example
from tuna.rocmlir.rocmlir_lib import RocMLIR


def get_library(args: Dict[str, Any]) -> Union[Example, MIOpen, RocMLIR]:
  """Factory method to get lib based on args"""
  library: Union[Example, MIOpen, RocMLIR]
  if 'lib' not in args.keys() or args['lib'].value == Library.MIOPEN.value:
    library = MIOpen()
  elif args['lib'].value == Library.EXAMPLE.value:
    library = Example()
  elif args['lib'].value == Library.ROCMLIR.value:
    library = RocMLIR()
  else:
    raise ValueError("Not implemented")

  return library
