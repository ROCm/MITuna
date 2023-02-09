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

from tuna.dbBase.sql_alchemy import DbSession
from utils import DummyArgs
from tuna.miopen.modules.import_benchmark import add_model, update_frameworks, print_models
from tuna.miopen.modules.import_benchmark import add_benchmark
from tuna.miopen.db.benchmark import Framework, ModelEnum, FrameworkEnum
from tuna.miopen.db.tables import MIOpenDBTables
from tuna.miopen.db.miopen_tables import ConvolutionBenchmark
from tuna.miopen.utils.config_type import ConfigType


def test_import_benchmark():
  args = DummyArgs
  models = {
      ModelEnum.ALEXNET: 1.0,
      ModelEnum.GOOGLENET: 2.0,
      ModelEnum.VGG19: 3.0
  }
  for key, value in models.items():
    args.add_model = key.value
    args.version = value
    add_model(args)
  print_models()
  update_frameworks()
  with DbSession() as session:
    frmks = session.query(Framework).all()
    assert len(frmks) > 0

  args.config_type = ConfigType.convolution
  dbt = MIOpenDBTables(session_id=None, config_type=args.config_type)
  args.driver = None
  args.add_benchmark = True
  args.framework = FrameworkEnum.PYTORCH
  args.model = ModelEnum.ALEXNET
  args.gpu_count = 8
  args.batchsize = 512
  args.file_name = "{0}/../utils/configs/conv_configs_NHWC.txt".format(
      this_path)
  add_benchmark(args, dbt)
  with DbSession() as session:
    bk_entries = session.query(ConvolutionBenchmark).all()
    assert len(bk_entries) > 0
