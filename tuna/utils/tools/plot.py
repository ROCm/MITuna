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
""" utils for plotting data """

#import seaborn as sns

from tuna.utils.tools.io import safe_save


def histogram(data, x, filename=None):  # pylint: disable=invalid-name
  """ plot data as a histogram """
  raise NotImplementedError(
      'implementation commented out to avoid seaborn as yet another dependency')


#  if isinstance(data, pd.DataFrame):
#    sns.set_style('white')
#    sns.displot(data=data, x=x, kind='hist')
#    save_or_show(plt, filename)


def save(plot, filename):
  """ save plot to file """
  plot.tight_layout()
  plot.savefig(filename, bbox_inches='tight')


def save_or_show(plot, filename, log=True):
  """ save plot to file if a filename is given, otherwise, render the plot right away """
  if filename is None:
    plot.show()
  else:
    safe_save(plot, filename, save, log_to_console=log)
    plot.close()
