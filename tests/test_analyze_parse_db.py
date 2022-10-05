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
import sys

sys.path.append("../tuna")
sys.path.append("tuna")

this_path = os.path.dirname(__file__)

from tuna.metadata import SQLITE_CONFIG_COLS
from tuna.helper import prune_cfg_dims
from tuna.analyze_parse_db import parse_pdb_filename


def test_prune_cfg_dims():
  cfg_obj = {}
  for col in SQLITE_CONFIG_COLS:
    cfg_obj[col] = 1

  cfg_obj_2d = cfg_obj.copy()
  cfg_obj_2d['spatial_dim'] = 2
  cfg_obj_3d = cfg_obj.copy()
  cfg_obj_3d['spatial_dim'] = 3

  pruned = prune_cfg_dims(cfg_obj_2d)
  assert ((cfg_obj_2d is pruned) == False)
  for key in pruned.keys():
    assert (key.endswith('_d') == False)

  pruned = prune_cfg_dims(cfg_obj_3d)
  assert ((cfg_obj_3d is pruned) == False)
  for key in SQLITE_CONFIG_COLS:
    assert (key in pruned.keys())


def test_parse_pdb_filename():

  #pass
  nm1 = 'gfx90878.db'
  nm2 = 'gfx90a6e.db'
  nm3 = 'gfx906_60.db'
  #fails
  nm4 = 'gfx90aaa.db'
  nm5 = 'gfx908_70.db'

  arch, num_cu = parse_pdb_filename(nm1)
  assert (arch == 'gfx908')
  assert (num_cu == 120)
  arch, num_cu = parse_pdb_filename(nm2)
  assert (arch == 'gfx90a')
  assert (num_cu == 110)
  arch, num_cu = parse_pdb_filename(nm3)
  assert (arch == 'gfx906')
  assert (num_cu == 60)

  err_throw = False
  try:
    arch, num_cu = parse_pdb_filename(nm4)
  except ValueError:
    err_throw = True
  assert (err_throw)

  err_throw = False
  try:
    arch, num_cu = parse_pdb_filename(nm5)
  except ValueError:
    err_throw = True
  assert (err_throw)
