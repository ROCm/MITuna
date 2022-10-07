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
""" utils to work with numpy arrays """

from tuna.utils import logging


# pylint: disable=redefined-builtin
def warn_if(condition, warning='', any=True):
  """ log a warning if condition is satisfied (for any/all elements) """
  if (any and not condition.any()) or (not any and not condition.all()):
    logging.warning(warning)
    return False

  return True


# pylint: disable=redefined-builtin
def err_if(condition, error='', any=True, strict=False):
  """ log/raise an error if condition is satisfied (for any/all elements) """
  if (any and not condition.any()) or (not any and not condition.all()):
    if strict:
      raise AssertionError(error)

    logging.error(error)
    return False

  return True
