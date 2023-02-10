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

from tuna.sql import DbCursor
from tuna.utils.logger import setup_logger
from tuna.find_db import ConvolutionFindDB


def parsing(find_db):
  dummy_str = [
      'NA',
      '2020-08-10 15:43:43,724 - /tmp/gfx908/120cu_10.216.64.100_30100p/3 - INFO - MIOpen(HIP): Info [SetValues] , content inserted: ConvHipImplicitGemmBwdDataV1R1Xdlops:64,64,2,64,32,2,1,0',
      '2020-08-10 16:09:07,750 - /tmp/gfx908/120cu_10.216.64.100_30100p/3 - INFO - MIOpen(HIP): Info [SetValues] , content inserted: ConvHipImplicitGemmBwdDataV1R1Xdlops:128,32,2,64,32,2,1,1'
  ]
  good_str = [
      '2020-08-10 15:43:44,096 - /tmp/gfx908/120cu_10.216.64.100_30100p/3 - INFO - MIOpen(HIP): Info [SetValues] 12-82-48-1x1-256-82-48-2-0x0-1x1-1x1-0-NCHW-FP32-B, content inserted: miopenConvolutionBwdDataAlgoImplicitGEMM:ConvHipImplicitGemmBwdDataV1R1Xdlops,0.02688,0,miopenConvolutionBwdDataAlgoImplicitGEMM,<unused>',
      '2020-08-10 16:09:08,075 - /tmp/gfx908/120cu_10.216.64.100_30100p/3 - INFO - MIOpen(HIP): Info [SetValues] 12-84-116-1x1-256-84-116-2-0x0-1x1-1x1-0-NCHW-FP32-B, content inserted: miopenConvolutionBwdDataAlgoImplicitGEMM:ConvHipImplicitGemmBwdDataV1R1Xdlops,0.05392,0,miopenConvolutionBwdDataAlgoImplicitGEMM,<unused>',
      '2020-08-13 11:11:15,877 - /tmp/gfx908/120cu_10.216.64.100_30100p/3 - INFO - MIOpen(HIP): Info [SetValues] 256-46-56-1x1-12-46-56-2-0x0-1x1-1x1-0-NCHW-FP32-F, content inserted: miopenConvolutionFwdAlgoDirect:ConvAsm1x1U,0.115839,0,miopenConvolutionFwdAlgoDirect,<unused>',
      '2020-08-13 11:11:42,935 - /tmp/gfx908/120cu_10.216.64.100_30100p/3 - INFO - MIOpen(HIP): Info [SetValues] 256-46-72-3x3-256-46-72-2-1x1-1x1-1x1-0-NCHW-FP32-F, content inserted: miopenConvolutionFwdAlgoWinograd:ConvBinWinogradRxSf3x2,0.571349,0,miopenConvolutionFwdAlgoWinograd,<unused>'
  ]

  for line in dummy_str:
    ret = find_db.parse(line)
    assert (ret == False)

  for line in good_str:
    ret = find_db.parse(line)
    assert (ret == True)


def test_find():
  logger = setup_logger('Machine')
  keys = {'logger': logger}

  find_db = ConvolutionFindDB(**keys)

  parsing(find_db)
