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

from tuna.import_configs import import_cfgs
from tuna.sql import DbCursor
from tuna.tables import DBTables, ConfigType
from utils import CfgImportArgs


def test_importconfigs():
  test_import_conv()
  test_import_batch_norm()


def test_import_conv():
  dbt = DBTables(config_type=ConfigType.convolution)
  res = None
  clean_tags = "TRUNCATE table conv_config_tags;"
  find_tags = "SELECT count(*) FROM conv_config_tags WHERE tag='conv_config_test';"
  find_configs = "SELECT count(*) FROM conv_config;"
  with DbCursor() as cur:
    cur.execute(clean_tags)

  before_cfg_num = 0
  with DbCursor() as cur:
    cur.execute(find_configs)
    res = cur.fetchall()
    before_cfg_num = res[0][0]

  cfg_file = "{0}/../utils/configs/conv_configs_NHWC.txt".format(this_path)
  add_cfg_NHWC = "{0}/../tuna/import_configs.py -f {0}/../utils/configs/conv_configs_NHWC.txt -t conv_config_test -V 1.0.0 -C convolution".format(
      this_path)
  args = CfgImportArgs
  args.file_name = cfg_file
  args.tag = "conv_config_test"
  args.version = '1.0.0'
  counts = import_cfgs(args, dbt)
  os.system(add_cfg_NHWC)

  with DbCursor() as cur:
    cur.execute(find_tags)
    res = cur.fetchall()
    assert (res[0][0] == len(counts['cnt_tagged_configs']))

    cur.execute(find_configs)
    res = cur.fetchall()
    after_cfg_num = res[0][0]
    assert (after_cfg_num - before_cfg_num == counts['cnt_configs'])


def test_import_batch_norm():
  dbt = DBTables(config_type=ConfigType.batch_norm)
  res = None
  clean_tags = "TRUNCATE table bn_config_tags;"
  find_tags = "SELECT count(*) FROM bn_config_tags WHERE tag='bn_config_test';"
  find_configs = "SELECT count(*) FROM bn_config;"
  with DbCursor() as cur:
    cur.execute(clean_tags)

  before_cfg_num = 0
  with DbCursor() as cur:
    cur.execute(find_configs)
    res = cur.fetchall()
    before_cfg_num = res[0][0]

  cfg_file = "{0}/../utils/configs/batch_norm.txt".format(this_path)
  add_cfg_NHWC = "{0}/../tuna/import_configs.py -f {0}/../utils/configs/batch_norm.txt -t bn_config_test -V 1.0.0 -C batch_norm".format(
      this_path)
  args = CfgImportArgs
  args.file_name = cfg_file
  args.tag = "bn_config_test"
  args.version = '1.0.0'
  args.config_type = ConfigType.batch_norm
  counts = import_cfgs(args, dbt)
  os.system(add_cfg_NHWC)

  with DbCursor() as cur:
    cur.execute(find_tags)
    res = cur.fetchall()
    assert (res[0][0] == len(counts['cnt_tagged_configs']))

    cur.execute(find_configs)
    res = cur.fetchall()
    after_cfg_num = res[0][0]
    assert (after_cfg_num - before_cfg_num == counts['cnt_configs'])
