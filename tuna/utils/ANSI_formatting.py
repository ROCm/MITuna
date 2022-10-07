# pylint: disable=invalid-name
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
""" utils to format strings with ANSI Colors and Formatting """


class ANSIColors:
  """ utils to color strings """
  # inpired from https://stackoverflow.com/a/287944/5046433
  BLUE = '\033[94m'
  CYAN = '\033[96m'
  GREEN = '\033[92m'
  YELLOW = '\033[93m'
  RED = '\033[91m'
  MAGENTA = '\u001b[35m'
  GREY = '\u001b[38;5;8m'
  END_COLOR = '\033[0m'

  @staticmethod
  def blue(string):
    """ color string blue with ANSI codes """
    return f"{ANSIColors.BLUE}{string}{ANSIColors.END_COLOR}"

  @staticmethod
  def cyan(string):
    """ color string cyan with ANSI codes """
    return f"{ANSIColors.CYAN}{string}{ANSIColors.END_COLOR}"

  @staticmethod
  def green(string):
    """ color string green with ANSI codes """
    return f"{ANSIColors.GREEN}{string}{ANSIColors.END_COLOR}"

  @staticmethod
  def yellow(string):
    """ color string yellow with ANSI codes """
    return f"{ANSIColors.YELLOW}{string}{ANSIColors.END_COLOR}"

  @staticmethod
  def red(string):
    """ color string red with ANSI codes """
    return f"{ANSIColors.RED}{string}{ANSIColors.END_COLOR}"

  @staticmethod
  def magenta(string):
    """ color string magenta with ANSI codes """
    return f"{ANSIColors.MAGENTA}{string}{ANSIColors.END_COLOR}"

  @staticmethod
  def grey(string):
    """ color string grey with ANSI codes """
    return f"{ANSIColors.GREY}{string}{ANSIColors.END_COLOR}"


class ANSIFormats:
  """ utils to apply formatting s.a. bold, underline, etc. to strings """
  #  inpired from https://stackoverflow.com/a/287944/5046433
  HEADER = '\033[95m'
  BOLD = '\033[1m'
  UNDERLINE = '\033[4m'
  REVERSED = '\u001b[7m'
  END_FORMAT = '\033[0m'

  @staticmethod
  def header(string):
    """ make string a header using ANSI codes """
    return f"{ANSIFormats.HEADER}{string}{ANSIFormats.END_FORMAT}"

  @staticmethod
  def bold(string):
    """ make string bold using ANSI codes """
    return f"{ANSIFormats.BOLD}{string}{ANSIFormats.END_FORMAT}"

  @staticmethod
  def underline(string):
    """ underline string using ANSI codes """
    return f"{ANSIFormats.UNDERLINE}{string}{ANSIFormats.END_FORMAT}"

  @staticmethod
  def reversed(string):
    """ make string reversed using ANSI codes """
    return f"{ANSIFormats.REVERSED}{string}{ANSIFormats.END_FORMAT}"


# pylint: disable-next=too-few-public-methods
class ANSITools:
  """ tools to help with ANSI formatting """
  CLEAR_LINE = "\033[K"
  CARRAGE_RETURN = "\r"

  @staticmethod
  def reset_line():
    """ clear the line and return carrage to the line start """
    return f"{ANSITools.CLEAR_LINE}{ANSITools.CARRAGE_RETURN}"
