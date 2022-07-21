#!/usr/bin/env python3
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
"""Remove duplicate configs from config table and update job table to correct config"""
from tuna.sql import DbCursor


def main():
  """main"""
  count = 0

  with DbCursor() as cur:
    cur.execute(
        "SELECT * from config WHERE valid = TRUE AND (cmd = 'conv' OR cmd = 'convfp16');"
    )
    #sub_cmd_idx = cur.column_names.index('cmd')
    assert cur.column_names.index('id') == 0

    rows = cur.fetchall()

  for row in rows:
    for row2 in rows[count + 1:]:
      if row[1:] == row2[1:]:
        with DbCursor() as cur:
          # duplicate row
          # mark as invalid
          print("UPDATE config SET valid = False WHERE id = {}".format(row2[0]))
          cur.execute("UPDATE config SET valid = False WHERE id = %s",
                      (row2[0],))
          # update job table to point to first config
          print("UPDATE job SET config = {} WHERE config = {}".format(
              row[0], row2[0]))
          cur.execute("UPDATE job SET config = %s WHERE config = %s",
                      (row[0], row2[0]))
    count += 1

  with DbCursor() as cur:
    cur.execute(
        "SELECT * from config WHERE valid = TRUE AND (cmd = 'CBAInfer' OR cmd = 'CBAInferfp16');"
    )
    #sub_cmd_idx = cur.column_names.index('cmd')
    assert cur.column_names.index('id') == 0

    rows = cur.fetchall()
  for row in rows:
    for row2 in rows[count + 1:]:
      if row[1:] == row2[1:]:
        with DbCursor() as cur:
          # duplicate row
          # mark as invalid
          print("UPDATE config SET valid = False WHERE id = {}".format(row2[0]))
          cur.execute("UPDATE config SET valid = False WHERE id = %s",
                      (row2[0],))
          # update job table to point to first config
          print("UPDATE job SET config = {} WHERE config = {}".format(
              row[0], row2[0]))
          cur.execute("UPDATE job SET config = %s WHERE config = %s",
                      (row[0], row2[0]))
    count += 1


if __name__ == '__main__':
  main()
