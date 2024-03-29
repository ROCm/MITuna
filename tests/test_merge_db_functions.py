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
import sqlite3

sys.path.append("../tuna")
sys.path.append("tuna")

this_path = os.path.dirname(__file__)

from tuna.miopen.subcmd.merge_db import parse_jobline, parse_text_fdb_name, parse_text_pdb_name
from tuna.miopen.subcmd.merge_db import target_merge
from tuna.miopen.subcmd.merge_db import update_master_list, write_merge_results
from tuna.miopen.subcmd.merge_db import merge_text_file
from tuna.miopen.subcmd.merge_db import get_sqlite_table
from tuna.miopen.subcmd.merge_db import get_sqlite_row, get_sqlite_data, load_master_list
from tuna.miopen.utils.helper import prune_cfg_dims


def test_parse_jobline():

  data = """1-160-698-5x5-64-79-348-1-1x1-2x2-1x1-0-NCHW-FP32-F=miopenConvolutionFwdAlgoImplicitGEMM:ConvHipImplicitGemmForwardV4R4Xdlops_Padded_Gemm,0.02352,0,miopenConvolutionFwdAlgoImplicitGEMM,not used;miopenConvolutionFwdAlgoWinograd:ConvBinWinogradRxSf2x3g1,0.03856,0,miopenConvolutionFwdAlgoWinograd,not used;miopenConvolutionFwdAlgoDirect:ConvOclDirectFwdGen,0.0536,0,miopenConvolutionFwdAlgoDirect,not used;miopenConvolutionFwdAlgoGEMM:GemmFwdRest,0.05712,2749200,miopenConvolutionFwdAlgoGEMM,not used\n"""

  key, vals = parse_jobline(data)

  assert key == '1-160-698-5x5-64-79-348-1-1x1-2x2-1x1-0-NCHW-FP32-F'
  assert (vals == {
      'miopenConvolutionFwdAlgoImplicitGEMM':
          'ConvHipImplicitGemmForwardV4R4Xdlops_Padded_Gemm,0.02352,0,miopenConvolutionFwdAlgoImplicitGEMM,not used',
      'miopenConvolutionFwdAlgoWinograd':
          'ConvBinWinogradRxSf2x3g1,0.03856,0,miopenConvolutionFwdAlgoWinograd,not used',
      'miopenConvolutionFwdAlgoDirect':
          'ConvOclDirectFwdGen,0.0536,0,miopenConvolutionFwdAlgoDirect,not used',
      'miopenConvolutionFwdAlgoGEMM':
          'GemmFwdRest,0.05712,2749200,miopenConvolutionFwdAlgoGEMM,not used'
  })

  algo = 'miopenConvolutionFwdAlgoImplicitGEMM'
  assert (
      vals[algo] ==
      'ConvHipImplicitGemmForwardV4R4Xdlops_Padded_Gemm,0.02352,0,miopenConvolutionFwdAlgoImplicitGEMM,not used'
  )


def test_parse_text_fdb_name():

  # Db names are as generated by the MIOPEN Lib
  master_file = "{0}/../utils/test_files/gfx90a_68.HIP.fdb.txt".format(
      this_path)
  arch, num_cu, final_file, copy_files = parse_text_fdb_name(master_file)

  assert (arch == "gfx90a")
  assert (num_cu == '68')
  assert (final_file)
  assert (copy_files == [])

  master_file = "{0}/../utils/test_files/gfx90878.HIP.fdb.txt".format(this_path)
  arch, num_cu, final_file, copy_files = parse_text_fdb_name(master_file)
  assert (arch == "gfx908")
  assert (num_cu == 120)

  master_file = "{0}/../utils/test_files/gfx1030_36.HIP.fdb.txt".format(
      this_path)
  arch, num_cu, final_file, copy_files = parse_text_fdb_name(master_file)
  assert (arch == "gfx1030")
  assert (num_cu == '36')


def test_parse_text_pdb_name():
  master_file = "{0}/../utils/test_files/old_gfx1030_36.db.txt".format(
      this_path)

  arch, num_cu, final_file, copy_files = parse_text_pdb_name(master_file)
  assert (arch == "gfx1030")
  assert (num_cu == 36)
  assert (final_file)
  assert (copy_files == [])

  master_file = "{0}/../utils/test_files/old_gfx90878.db.txt".format(this_path)

  arch, num_cu, final_file, copy_files = parse_text_pdb_name(master_file)
  assert (arch == "gfx908")
  assert (num_cu == 120)
  assert (final_file)
  assert (copy_files == [])


def test_load_master_list():
  master_file = "{0}/../utils/test_files/old_gfx90a68.HIP.fdb.txt".format(
      this_path)

  master_list = load_master_list(master_file)

  if master_list == {}:
    assert False

  if master_list:
    assert (list(master_list.keys())[0] ==
            '1-160-698-5x5-64-79-348-1-1x1-2x2-1x1-0-NCHW-FP32-F')
    assert (list(master_list.values())[0] == {
        'miopenConvolutionFwdAlgoImplicitGEMM':
            'ConvHipImplicitGemmForwardV4R4Xdlops_Padded_Gemm,0.02352,0,miopenConvolutionFwdAlgoImplicitGEMM,not used',
        'miopenConvolutionFwdAlgoWinograd':
            'ConvBinWinogradRxSf2x3g1,0.03856,0,miopenConvolutionFwdAlgoWinograd,not used',
        'miopenConvolutionFwdAlgoDirect':
            'ConvOclDirectFwdGen,0.0536,0,miopenConvolutionFwdAlgoDirect,not used',
        'miopenConvolutionFwdAlgoGEMM':
            'GemmFwdRest,0.05712,2749200,miopenConvolutionFwdAlgoGEMM,not used'
    })


def test_target_merge():
  master_list = {
      '1-160-698-5x5-64-79-348-1-1x1-2x2-1x1-0-NCHW-FP32-F': {
          'miopenConvolutionFwdAlgoImplicitGEMM':
              'ConvHipImplicitGemmForwardV4R4Xdlops_Padded_Gemm,0.02352,0,miopenConvolutionFwdAlgoImplicitGEMM,not used',
          'miopenConvolutionFwdAlgoWinograd':
              'ConvBinWinogradRxSf2x3g1,0.03856,0,miopenConvolutionFwdAlgoWinograd,not used',
          'miopenConvolutionFwdAlgoDirect':
              'ConvOclDirectFwdGen,0.0536,0,miopenConvolutionFwdAlgoDirect,not used',
          'miopenConvolutionFwdAlgoGEMM':
              'GemmFwdRest,0.05712,2749200,miopenConvolutionFwdAlgoGEMM,not used'
      },
      '1-19-19-1x1-64-19-19-1024-0x0-1x1-1x1-0-NCHW-FP32-B': {
          'miopenConvolutionBwdDataAlgoWinograd':
              'ConvBinWinogradRxSf2x3g1,0.186719,0,miopenConvolutionBwdDataAlgoWinograd,not used',
          'miopenConvolutionBwdDataAlgoDirect':
              'ConvOclDirectFwd1x1,0.234239,0,miopenConvolutionBwdDataAlgoDirect,not used',
          'miopenConvolutionBwdDataAlgoGEMM':
              'GemmBwd1x1_stride1,0.239519,0,miopenConvolutionBwdDataAlgoGEMM,not used',
          'miopenConvolutionBwdDataAlgoImplicitGEMM':
              'ConvAsmImplicitGemmGTCDynamicBwdXdlopsNHWC,0.327199,94633984,miopenConvolutionBwdDataAlgoImplicitGEMM,not used'
      }
  }

  key = '1-160-698-5x5-64-79-348-1-1x1-2x2-1x1-0-NCHW-FP32-F'
  vals = {
      'miopenConvolutionFwdAlgoImplicitGEMM':
          'ConvMlirIgemmFwdXdlops,0.03776,0,miopenConvolutionFwdAlgoImplicitGEMM,not used'
  }
  keep_keys = False
  target_merge(master_list, key, vals, keep_keys)

  #new key with the avaliable values.
  assert (master_list[key] == {
      'miopenConvolutionFwdAlgoImplicitGEMM':
          'ConvMlirIgemmFwdXdlops,0.03776,0,miopenConvolutionFwdAlgoImplicitGEMM,not used'
  })

  keep_keys = True
  key = '1-19-19-1x1-64-19-19-1024-0x0-1x1-1x1-0-NCHW-FP32-B'

  target_merge(master_list, key, vals, keep_keys)

  assert ((master_list[key]) == {
      'miopenConvolutionBwdDataAlgoWinograd':
          'ConvBinWinogradRxSf2x3g1,0.186719,0,miopenConvolutionBwdDataAlgoWinograd,not used',
      'miopenConvolutionBwdDataAlgoDirect':
          'ConvOclDirectFwd1x1,0.234239,0,miopenConvolutionBwdDataAlgoDirect,not used',
      'miopenConvolutionBwdDataAlgoGEMM':
          'GemmBwd1x1_stride1,0.239519,0,miopenConvolutionBwdDataAlgoGEMM,not used',
      'miopenConvolutionBwdDataAlgoImplicitGEMM':
          'ConvAsmImplicitGemmGTCDynamicBwdXdlopsNHWC,0.327199,94633984,miopenConvolutionBwdDataAlgoImplicitGEMM,not used',
      'miopenConvolutionFwdAlgoImplicitGEMM':
          'ConvMlirIgemmFwdXdlops,0.03776,0,miopenConvolutionFwdAlgoImplicitGEMM,not used'
  })

  #test when we pass vals == {}
  keep_keys = False

  master_list = {
      '1-160-698-5x5-64-79-348-1-1x1-2x2-1x1-0-NCHW-FP32-F': {
          'miopenConvolutionFwdAlgoImplicitGEMM':
              'ConvHipImplicitGemmForwardV4R4Xdlops_Padded_Gemm,0.02352,0,miopenConvolutionFwdAlgoImplicitGEMM,not used',
          'miopenConvolutionFwdAlgoWinograd':
              'ConvBinWinogradRxSf2x3g1,0.03856,0,miopenConvolutionFwdAlgoWinograd,not used',
          'miopenConvolutionFwdAlgoDirect':
              'ConvOclDirectFwdGen,0.0536,0,miopenConvolutionFwdAlgoDirect,not used',
          'miopenConvolutionFwdAlgoGEMM':
              'GemmFwdRest,0.05712,2749200,miopenConvolutionFwdAlgoGEMM,not used'
      }
  }

  key = '1-160-698-5x5-64-79-348-1-1x1-2x2-1x1-0-NCHW-FP32-F'
  vals = {}

  err_found = False
  try:
    target_merge(master_list, key, vals, keep_keys)
  except ValueError:
    err_found = True
  assert (err_found)

  # inputs wth key= None
  err_found = False
  key = None

  vals = {
      'miopenConvolutionFwdAlgoImplicitGEMM':
          'ConvMlirIgemmFwdXdlops,0.03776,0,miopenConvolutionFwdAlgoImplicitGEMM,not used'
  }

  master_list = {
      '1-160-698-5x5-64-79-348-1-1x1-2x2-1x1-0-NCHW-FP32-F': {
          'miopenConvolutionFwdAlgoImplicitGEMM':
              'ConvHipImplicitGemmForwardV4R4Xdlops_Padded_Gemm,0.02352,0,miopenConvolutionFwdAlgoImplicitGEMM,not used',
          'miopenConvolutionFwdAlgoWinograd':
              'ConvBinWinogradRxSf2x3g1,0.03856,0,miopenConvolutionFwdAlgoWinograd,not used',
          'miopenConvolutionFwdAlgoDirect':
              'ConvOclDirectFwdGen,0.0536,0,miopenConvolutionFwdAlgoDirect,not used',
          'miopenConvolutionFwdAlgoGEMM':
              'GemmFwdRest,0.05712,2749200,miopenConvolutionFwdAlgoGEMM,not used'
      }
  }

  try:
    target_merge(master_list, key, vals, keep_keys=False)
  except ValueError:
    err_found = True
  assert (err_found)

  # key = ""
  err_found = False
  key = ""
  vals = {
      'miopenConvolutionFwdAlgoImplicitGEMM':
          'ConvMlirIgemmFwdXdlops,0.03776,0,miopenConvolutionFwdAlgoImplicitGEMM,not used'
  }

  master_list = {
      '1-160-698-5x5-64-79-348-1-1x1-2x2-1x1-0-NCHW-FP32-F': {
          'miopenConvolutionFwdAlgoImplicitGEMM':
              'ConvHipImplicitGemmForwardV4R4Xdlops_Padded_Gemm,0.02352,0,miopenConvolutionFwdAlgoImplicitGEMM,not used',
          'miopenConvolutionFwdAlgoWinograd':
              'ConvBinWinogradRxSf2x3g1,0.03856,0,miopenConvolutionFwdAlgoWinograd,not used',
          'miopenConvolutionFwdAlgoDirect':
              'ConvOclDirectFwdGen,0.0536,0,miopenConvolutionFwdAlgoDirect,not used',
          'miopenConvolutionFwdAlgoGEMM':
              'GemmFwdRest,0.05712,2749200,miopenConvolutionFwdAlgoGEMM,not used'
      }
  }

  try:
    target_merge(master_list, key, vals, keep_keys=False)
  except ValueError:
    err_found = True
  assert (err_found)

  # key = " "
  err_found = False
  key = "  "
  vals = {
      'miopenConvolutionFwdAlgoImplicitGEMM':
          'ConvMlirIgemmFwdXdlops,0.03776,0,miopenConvolutionFwdAlgoImplicitGEMM,not used'
  }

  master_list = {
      '1-160-698-5x5-64-79-348-1-1x1-2x2-1x1-0-NCHW-FP32-F': {
          'miopenConvolutionFwdAlgoImplicitGEMM':
              'ConvHipImplicitGemmForwardV4R4Xdlops_Padded_Gemm,0.02352,0,miopenConvolutionFwdAlgoImplicitGEMM,not used',
          'miopenConvolutionFwdAlgoWinograd':
              'ConvBinWinogradRxSf2x3g1,0.03856,0,miopenConvolutionFwdAlgoWinograd,not used',
          'miopenConvolutionFwdAlgoDirect':
              'ConvOclDirectFwdGen,0.0536,0,miopenConvolutionFwdAlgoDirect,not used',
          'miopenConvolutionFwdAlgoGEMM':
              'GemmFwdRest,0.05712,2749200,miopenConvolutionFwdAlgoGEMM,not used'
      }
  }

  try:
    target_merge(master_list, key, vals, keep_keys=False)
  except ValueError:
    err_found = True
  assert (err_found)

  # inputs wth key={}
  err_found = False
  key = {}

  vals = {
      'miopenConvolutionFwdAlgoImplicitGEMM':
          'ConvMlirIgemmFwdXdlops,0.03776,0,miopenConvolutionFwdAlgoImplicitGEMM,not used'
  }

  master_list = {
      '1-160-698-5x5-64-79-348-1-1x1-2x2-1x1-0-NCHW-FP32-F': {
          'miopenConvolutionFwdAlgoImplicitGEMM':
              'ConvHipImplicitGemmForwardV4R4Xdlops_Padded_Gemm,0.02352,0,miopenConvolutionFwdAlgoImplicitGEMM,not used',
          'miopenConvolutionFwdAlgoWinograd':
              'ConvBinWinogradRxSf2x3g1,0.03856,0,miopenConvolutionFwdAlgoWinograd,not used',
          'miopenConvolutionFwdAlgoDirect':
              'ConvOclDirectFwdGen,0.0536,0,miopenConvolutionFwdAlgoDirect,not used',
          'miopenConvolutionFwdAlgoGEMM':
              'GemmFwdRest,0.05712,2749200,miopenConvolutionFwdAlgoGEMM,not used'
      }
  }

  try:
    target_merge(master_list, key, vals, keep_keys=False)
  except ValueError:
    err_found = True
  assert (err_found)

  # inputs wth master_list={}, error handling
  err_found = False
  master_list = {}
  keep_keys = False
  key = '1-160-698-5x5-64-79-348-1-1x1-2x2-1x1-0-NCHW-FP32-F'

  vals = {
      'miopenConvolutionFwdAlgoImplicitGEMM':
          'ConvMlirIgemmFwdXdlops,0.03776,0,miopenConvolutionFwdAlgoImplicitGEMM,not used'
  }

  try:
    target_merge(master_list, key, vals, keep_keys)
  except ValueError:
    err_found = True
  assert err_found

  #with solver indexed format
  master_list = {
      '992-7-7-1x1-128-7-7-8-0x0-1x1-1x1-0-NCHW-FP16-F': {
          'ConvMlirIgemmFwdXdlops':
              '0.01904,0,miopenConvolutionFwdAlgoImplicitGEMM',
          'ConvHipImplicitGemmForwardV4R4Xdlops_Padded_Gemm':
              '0.024,0,miopenConvolutionFwdAlgoImplicitGEMM',
          'ConvAsmImplicitGemmGTCDynamicFwdXdlops':
              '0.04512,0,miopenConvolutionFwdAlgoImplicitGEMM',
          'ConvAsm1x1U':
              '0.0528,0,miopenConvolutionFwdAlgoDirect'
      },
      '992-7-7-1x1-128-7-7-8-0x0-1x1-1x1-0-NCHW-FP32-F': {
          'ConvMlirIgemmFwdXdlops':
              '0.02704,0,miopenConvolutionFwdAlgoImplicitGEMM',
          'ConvAsm1x1U':
              '0.031041,0,miopenConvolutionFwdAlgoDirect',
          'ConvOclDirectFwd1x1':
              '0.03552,0,miopenConvolutionFwdAlgoDirect',
          'ConvHipImplicitGemmForwardV4R4Xdlops_Padded_Gemm':
              '0.04192,0,miopenConvolutionFwdAlgoImplicitGEMM'
      }
  }
  key = '992-7-7-1x1-128-7-7-8-0x0-1x1-1x1-0-NCHW-FP16-F'
  vals = {'NewBest': '0.0001,0,Best'}
  keep_keys = False
  target_merge(master_list, key, vals, keep_keys)
  assert (master_list[key] == vals)


def test_update_master_list():

  master_list = {
      '1-48-480-3x3-16-48-480-1-1x1-1x1-1x1-0-NCHW-FP16-F': {
          'miopenConvolutionFwdAlgoImplicitGEMM':
              'ConvHipImplicitGemmForwardV4R4Xdlops_Padded_Gemm,0.02512,0,miopenConvolutionFwdAlgoImplicitGEMM,not used',
          'miopenConvolutionFwdAlgoDirect':
              'ConvOclDirectFwd,0.02544,0,miopenConvolutionFwdAlgoDirect,not used',
          'miopenConvolutionFwdAlgoWinograd':
              'ConvBinWinogradRxSf2x3g1,0.03104,0,miopenConvolutionFwdAlgoWinograd,not used',
          'miopenConvolutionFwdAlgoGEMM':
              'GemmFwdRest,0.06096,414720,miopenConvolutionFwdAlgoGEMM,not used'
      }
  }

  test_target_file = "{0}/../utils/test_files/usr_gfx90a68.HIP.fdb.txt".format(
      this_path)

  local_paths = [test_target_file]
  mids = [-1]
  keep_keys = False
  update_master_list(master_list, local_paths, mids, keep_keys)

  #master_list got updated for new entries
  assert (master_list == {
      '1-48-480-3x3-16-48-480-1-1x1-1x1-1x1-0-NCHW-FP16-F': {
          'miopenConvolutionFwdAlgoImplicitGEMM':
              'ConvHipImplicitGemmForwardV4R4Xdlops_Padded_Gemm,0.02512,0,miopenConvolutionFwdAlgoImplicitGEMM,not used',
          'miopenConvolutionFwdAlgoDirect':
              'ConvOclDirectFwd,0.02544,0,miopenConvolutionFwdAlgoDirect,not used',
          'miopenConvolutionFwdAlgoWinograd':
              'ConvBinWinogradRxSf2x3g1,0.03104,0,miopenConvolutionFwdAlgoWinograd,not used',
          'miopenConvolutionFwdAlgoGEMM':
              'GemmFwdRest,0.06096,414720,miopenConvolutionFwdAlgoGEMM,not used'
      },
      '1-160-698-5x5-64-79-348-1-1x1-2x2-1x1-0-NCHW-FP32-F': {
          'miopenConvolutionFwdAlgoImplicitGEMM':
              'ConvMlirIgemmFwdXdlops,0.03776,0,miopenConvolutionFwdAlgoImplicitGEMM,not used'
      },
      '1-19-19-1x1-64-19-19-1024-0x0-1x1-1x1-0-NCHW-FP32-B': {
          'miopenConvolutionBwdDataAlgoDirect':
              'ConvAsm1x1U,0.09728,0,miopenConvolutionBwdDataAlgoDirect,not used',
          'miopenConvolutionBwdDataAlgoWinograd':
              'ConvBinWinogradRxSf3x2,0.18192,0,miopenConvolutionBwdDataAlgoWinograd,not used',
          'miopenConvolutionBwdDataAlgoImplicitGEMM':
              'ConvMlirIgemmBwdXdlops,0.250079,0,miopenConvolutionBwdDataAlgoImplicitGEMM,not used',
          'miopenConvolutionBwdDataAlgoGEMM':
              'GemmBwd1x1_stride1,2732.22,0,miopenConvolutionBwdDataAlgoGEMM,not used'
      },
      '1-19-19-1x1-64-19-19-1024-0x0-1x1-1x1-0-NCHW-FP32-W': {
          'miopenConvolutionBwdWeightsAlgoDirect':
              'ConvAsmBwdWrW1x1,0.445761,0,miopenConvolutionBwdWeightsAlgoDirect,not used',
          'miopenConvolutionBwdWeightsAlgoWinograd':
              'ConvBinWinogradRxSf2x3,11.9268,0,miopenConvolutionBwdWeightsAlgoWinograd,not used',
          'miopenConvolutionBwdWeightsAlgoImplicitGEMM':
              'ConvMlirIgemmWrWXdlops,69.8604,0,miopenConvolutionBwdWeightsAlgoImplicitGEMM,not used'
      },
      '1024-14-14-1x1-256-14-14-15-0x0-1x1-1x1-0-NCHW-FP16-F': {
          'miopenConvolutionFwdAlgoImplicitGEMM':
              'ConvHipImplicitGemmForwardV4R4Xdlops_Padded_Gemm,0.03808,0,miopenConvolutionFwdAlgoImplicitGEMM,not used',
          'miopenConvolutionFwdAlgoDirect':
              'ConvAsm1x1U,0.11072,0,miopenConvolutionFwdAlgoDirect,not used',
          'miopenConvolutionFwdAlgoWinograd':
              'ConvBinWinogradRxSf3x2,0.208159,0,miopenConvolutionFwdAlgoWinograd,not used',
          'miopenConvolutionFwdAlgoGEMM':
              'GemmFwd1x1_0_1,2730.97,0,miopenConvolutionFwdAlgoGEMM,not used'
      }
  })


def test_write_merge_results():

  master_file = "{0}/../utils/test_files/old_gfx90a68.HIP.fdb.txt".format(
      this_path)

  if master_file.endswith('.fdb.txt'):
    _, _, final_file, copy_files = parse_text_fdb_name(master_file)

  master_list = load_master_list(master_file)

  copy_files = []

  write_merge_results(master_list, final_file, copy_files)

  with open(final_file, "r") as fptr:
    file_content = fptr.read()
    assert (file_content.find('miopenConvolutionFwdAlgoImplicitGEMM'))


def parse_fdb(filename):
  find_db = {}
  fp = open(filename)
  for line in fp:
    key, vals = line.split('=')
    vals = [x.strip() for x in vals.split(';')]
    find_db[key] = vals
  fp.close()

  return find_db


def test_merge_text_file():
  master_file = "{0}/../utils/test_files/old_gfx90a68.HIP.fdb.txt".format(
      this_path)
  copy_only = False
  keep_keys = False
  target_file = "{0}/../utils/test_files/usr_gfx90a68.HIP.fdb.txt".format(
      this_path)

  master_db = parse_fdb(master_file)

  if master_file.endswith('.fdb.txt'):
    _, _, final_file, copy_files = parse_text_fdb_name(master_file)

  result_file = merge_text_file(master_file, copy_only, keep_keys, target_file)

  assert os.stat(result_file)

  chk_db = {}
  output_fp = open(result_file)
  for line in output_fp:
    key, vals = line.split('=')
    chk_db[key] = vals

  for key in master_db:
    assert key in chk_db

  #target_file set to None
  master_file = "{0}/../utils/test_files/old_gfx90a68.HIP.fdb.txt".format(
      this_path)

  err_found = False
  target_file = " "
  try:
    result_file = merge_text_file(master_file,
                                  copy_only=False,
                                  keep_keys=False,
                                  target_file=None)

  except ValueError:
    err_found = True
  assert (err_found)


def test_get_sqlite_table():

  local_path = "{0}/../utils/test_files/test_gfx90678.db".format(this_path)
  cnx_from = sqlite3.connect(local_path)
  perf_rows, perf_cols = get_sqlite_table(cnx_from, 'perf_db')

  assert perf_rows or perf_cols


def test_get_sqlite_row():

  local_path = "{0}/../utils/test_files/test_gfx90678.db".format(this_path)
  cnx_from = sqlite3.connect(local_path)

  perf_rows, perf_cols = get_sqlite_table(cnx_from, 'perf_db')
  for row in perf_rows:
    perf = dict(zip(perf_cols, row))

    cfg_row, cfg_cols = get_sqlite_row(cnx_from, 'config', perf['config'])
    cfg = dict(zip(cfg_cols, cfg_row))
    cfg.pop('id', None)

  assert cfg_row and cfg_row


def test_get_sqlite_data():

  test_file = "{0}/../utils/test_files/test_gfx90678.db".format(this_path)

  cfg = {
      'layout': 'NCHW',
      'data_type': 'FP32',
      'direction': 'F',
      'spatial_dim': 2,
      'in_channels': 192,
      'in_h': 28,
      'in_w': 28,
      'in_d': 1,
      'fil_h': 1,
      'fil_w': 1,
      'fil_d': 1,
      'out_channels': 64,
      'batchsize': 8,
      'pad_h': 0,
      'pad_w': 0,
      'pad_d': 0,
      'conv_stride_h': 1,
      'conv_stride_w': 1,
      'conv_stride_d': 0,
      'dilation_h': 1,
      'dilation_w': 1,
      'dilation_d': 0,
      'bias': 0,
      'group_count': 1
  }

  cnx_to = sqlite3.connect(test_file)

  res, col = get_sqlite_data(cnx_to, 'config', prune_cfg_dims(cfg))

  assert res
