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

import os
import sqlite3

# TODO: This is a copy and is unacceptable
sqlite_config_cols = [
    'layout', 'direction', 'data_type', 'spatial_dim', 'in_channels', 'in_h',
    'in_w', 'in_d', 'fil_h', 'fil_w', 'fil_d', 'out_channels', 'batchsize',
    'pad_h', 'pad_w', 'pad_d', 'conv_stride_h', 'conv_stride_w',
    'conv_stride_d', 'dilation_h', 'dilation_w', 'dilation_d', 'bias',
    'group_count'
]

sqlite_perf_db_cols = ["solver", "config", "arch", "num_cu", "params"]

valid_arch_cu = [("gfx803", 36), ("gfx803", 64), ("gfx900", 56), ("gfx900", 64),
                 ("gfx906", 60), ("gfx906", 64), ("gfx908", 120),
                 ("gfx1030", 36)]


def get_sqlite_table(cnx, table_name):
  query = "SELECT * from {}".format(table_name)
  c = cnx.cursor()
  c.execute(query)
  rows = c.fetchall()
  columns = [x[0] for x in c.description]
  return rows, columns
