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
"""utility for removing duplicate jobs from sql"""
import argparse

from tuna.sql import DbCursor


def parse_args():
  """command line argument parsing"""
  parser = argparse.ArgumentParser(
      description='Scan the job table for duplicate jobs')
  parser.add_argument('-d',
                      '--dry_run',
                      dest='dry_run',
                      action='store_true',
                      default=False,
                      help='Do a dry run')
  parser.add_argument('arch',
                      type=str,
                      help='Architecture of machines to create jobs for',
                      choices=['gfx900', 'gfx906'])
  args = parser.parse_args()
  return args


def main():
  """main"""
  cnt_dup_jobs = 0
  args = parse_args()
  count = 0

  rows = None
  with DbCursor() as cur:
    cur.execute(
        "SELECT id, config FROM job WHERE valid = TRUE AND arch = %s AND state = 'new'",
        (args.arch,))
    assert cur.column_names.index('id') == 0
    rows = cur.fetchall()

  for row in rows:
    count += 1
    for row2 in rows[count:]:
      if row[1:] == row2[1:]:
        # duplicate row
        # mark as invalid
        print("UPDATE job SET valid = False WHERE id = {}".format(row2[0]))
        if not args.dry_run:
          with DbCursor() as cur:
            cur.execute("UPDATE job SET valid = False WHERE id = %s",
                        (row2[0],))
        cnt_dup_jobs += 1

  print('Total duplicate jobs: {}'.format(cnt_dup_jobs))


if __name__ == '__main__':
  main()
