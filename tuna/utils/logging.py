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
""" utilities for logging """

import os
import sys
import time

import tuna.utils.tools.io as io_tools
from tuna.utils.helpers import as_heading
import tuna.utils.tools.file as file_tools
from tuna.utils.ANSI_formatting import ANSIColors, ANSITools


# pylint: disable-next=invalid-name; logging is supposed to act like a module
class logging:
  """ definitions of logging utilities """

  RUNNING_LOG = ''

  @staticmethod
  def warning(string, end_char='\n', silent=False):
    """ log string as a warning """
    logging.RUNNING_LOG += f'warning: {string}\n'
    if sys.platform == 'win32':
      os.system('color')
    if not silent:
      sys.stdout.write(f"{ANSIColors.yellow(string)}{end_char}")

  @staticmethod
  def info(string, end_char='\n', silent=False):
    """ log string as general info. """
    logging.RUNNING_LOG += f'info: {string}\n'
    if sys.platform == 'win32':
      os.system('color')
    if not silent:
      sys.stdout.write(f"{ANSIColors.blue(string)}{end_char}")

  @staticmethod
  def error(string, end_char='\n', silent=False):
    """ log string as an error """
    logging.RUNNING_LOG += f'error: {string}\n'
    if sys.platform == 'win32':
      os.system('color')
    if not silent:
      sys.stdout.write(f"{ANSIColors.red(string)}{end_char}")

  @staticmethod
  def success(string, end_char='\n', silent=False):
    """ log string as a success """
    logging.RUNNING_LOG += f'success: {string}\n'
    if sys.platform == 'win32':
      os.system('color')
    if not silent:
      sys.stdout.write(f"{ANSIColors.green(string)}{end_char}")

  @staticmethod
  def log(string, formatting=None, end_char='\n', silent=False):
    """ log string with no special connotation """
    logging.RUNNING_LOG += f'{string}\n'
    if not silent:
      if formatting is not None:
        sys.stdout.write(f"{formatting(string)}{end_char}")
      else:
        sys.stdout.write(f"{string}{end_char}")

  @staticmethod
  def reset_line():
    """ clear out the current line in stdout and reset the caret to the start """
    sys.stdout.write(ANSITools.reset_line())

  @staticmethod
  def clean_slate():
    """ clear out the running log """
    logging.RUNNING_LOG = ''

  @staticmethod
  def dump_logs(path=None, clean_slate_after_dump=True, append=False):
    """ dump the running log to file (or stdout if no filepath is provided) """
    str_to_dump = as_heading(
        time.strftime('%l:%M%p %Z on %b %d, %Y')) + '\n' + logging.RUNNING_LOG

    if path is None:
      print(str_to_dump)
    else:
      if append:
        io_tools.safe_save(str_to_dump, path, file_tools.append)
      else:
        io_tools.safe_save(str_to_dump, path, file_tools.write)

    if clean_slate_after_dump:
      logging.clean_slate()


def report_warning(msg, strict=False):
  """log msg as a warning or raise an assertion error"""
  if strict:
    raise AssertionError(msg)
  logging.warning(msg)


def report_error(msg, strict=False):
  """log msg as an error or raise an assertion error"""
  if strict:
    raise AssertionError(msg)
  logging.error(msg)


# exposing the static methods in logging to provide a clean interface
# to the logging utils (and to allow for backwards compatibility)
warning = logging.warning
error = logging.error
success = logging.success
info = logging.info
log = logging.log
dump_logs = logging.dump_logs
reset_line = logging.reset_line
clean_slate = logging.clean_slate
