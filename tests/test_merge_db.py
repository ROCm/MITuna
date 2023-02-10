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
import sys
import os

from tuna.miopen.subcmd.merge_db import merge_files

sys.path.append("../tuna")
sys.path.append("tuna")
this_path = os.path.dirname(__file__)


def parse_fdb(filename):
  find_db = {}
  fp = open(filename)
  for line in fp:
    key, vals = line.split('=')
    vals = [x.strip() for x in vals.split(';')]
    find_db[key] = vals
  fp.close()

  return find_db


def test_merge_fdb():
  master_file = "{0}/../utils/test_files/old_gfx90a68.HIP.fdb.txt".format(
      this_path)
  target_file = "{0}/../utils/test_files/usr_gfx90a68.HIP.fdb.txt".format(
      this_path)

  master_db = parse_fdb(master_file)
  target_db = parse_fdb(target_file)

  copy_only = False
  keep_keys = False
  output_file = merge_files(master_file, copy_only, keep_keys, target_file)

  output_db1 = {}
  output_fp = open(output_file)
  for line in output_fp:
    key, vals = line.split('=')
    output_db1[key] = vals

  for key in master_db:
    assert key in output_db1

  for key in target_db:
    assert key in output_db1
    for val in target_db[key]:
      assert val in output_db1[key]

    if key in master_db:
      for val in master_db[key]:
        #if old entry isn't in target, assert it isn't in the output (old entries not kept)
        if not val in target_db[key]:
          assert not val in output_db1[key]

  copy_only = False
  keep_keys = True
  output_file = merge_files(master_file, copy_only, keep_keys, target_file)

  output_db2 = {}
  output_fp = open(output_file)
  for line in output_fp:
    key, vals = line.split('=')
    output_db2[key] = vals

  for key in master_db:
    assert key in output_db2

  for key in target_db:
    assert key in output_db2
    for val in target_db[key]:
      assert val in output_db2[key]

    if key in master_db:
      new_algs = [x.split(':')[0].strip() for x in target_db[key]]
      for val in master_db[key]:
        alg = val.split(':')[0].strip()
        #if old alg isn't in target db, assert it is in the output (it was kept)
        if not alg in new_algs:
          assert alg in output_db2[key]
