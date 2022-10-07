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
""" finddb_like objects are finddb, explodedfinddb, fastdb, explodedfastdb """

from tuna.utils import logging
from tuna.utils.db_utility import get_id_solvers
from tuna.utils.helpers import sort_dict, invert_dict, as_heading

_, _ID_TO_SOLVER = get_id_solvers()
_SOLVER_TO_ID = invert_dict(_ID_TO_SOLVER)


def get_solver_counts(finddb_like, use_id=False):
  """ returns a dictionary that maps a given solver name to the
  number of times it occurs in finddb-like Database """
  solver_counts = finddb_like['solver'].value_counts()
  solver_counts_dict = {}
  for solver_id, count in solver_counts.iteritems():
    if use_id:
      solver_counts_dict[solver_id] = count
    else:
      solver_counts_dict[_ID_TO_SOLVER[solver_id]] = count
  return sort_dict(solver_counts_dict)


def log_duplicates(finddb, cols_with_conv_params):
  """ log convolution configs that report multiple kernel times for the same solver """
  duplicates = finddb[finddb.duplicated(subset=cols_with_conv_params +
                                        ['solver'],
                                        keep=False)]
  duplicates = duplicates.sort_values(cols_with_conv_params +
                                      ['solver', 'kernel_time'])
  duplicates = duplicates.groupby(cols_with_conv_params + ['solver'])

  duplicates_str = as_heading("Duplicates") + '\n'
  for i, (_, df) in enumerate(duplicates):  # pylint: disable=invalid-name
    for _, row in df.iterrows():
      conv_params_str = "+ " if i % 2 == 0 else "- "
      for colname, val in zip(cols_with_conv_params,
                              row[cols_with_conv_params]):
        conv_params_str += f'{colname} {val}, '
      duplicates_str += f"{conv_params_str}\n  solver: {row['solver']},  " +\
                f"kernel_time: {row['kernel_time']}\n\n"

  logging.log(duplicates_str, silent=True)
