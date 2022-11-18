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

from tuna.utils.merge_db import parse_jobline, parse_text_fdb_name, parse_text_pdb_name, load_master_list
from tuna.utils.merge_db import best_solver, target_merge, no_job_merge, single_job_merge
from tuna.utils.merge_db import multi_job_merge, update_master_list, write_merge_results
from tuna.utils.merge_db import merge_text_file, merge_sqlite_pdb, merge_sqlite_bin_cache
from tuna.utils.merge_db import merge_sqlite, get_file_list, get_sqlite_table
from tuna.utils.merge_db import get_sqlite_row, get_sqlite_data
from tuna.helper import prune_cfg_dims


def test_parse_jobline():

  data = """1-160-698-5x5-64-79-348-1-1x1-2x2-1x1-0-NCHW-FP32-F=miopenConvolutionFwdAlgoImplicitGEMM:ConvHipImplicitGemmForwardV4R4Xdlops_Padded_Gemm,0.02352,0,miopenConvolutionFwdAlgoImplicitGEMM,not used;miopenConvolutionFwdAlgoWinograd:ConvBinWinogradRxSf2x3g1,0.03856,0,miopenConvolutionFwdAlgoWinograd,not used;miopenConvolutionFwdAlgoDirect:ConvOclDirectFwdGen,0.0536,0,miopenConvolutionFwdAlgoDirect,not used;miopenConvolutionFwdAlgoGEMM:GemmFwdRest,0.05712,2749200,miopenConvolutionFwdAlgoGEMM,not used\n"""

  key, vals = parse_jobline(data)

  assert (key == '1-160-698-5x5-64-79-348-1-1x1-2x2-1x1-0-NCHW-FP32-F')
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
  master_file = '/data/tests/gfx90a_68.HIP.fdb.txt'

  arch, num_cu, final_file, copy_files = parse_text_fdb_name(master_file)
  assert (arch == "gfx90a")
  assert (num_cu == '68')
  assert (final_file == "/data/tests/gfx90a_68.HIP.fdb.txt")
  assert (copy_files == [])


def test_parse_text_pdb_name():
  master_file = '/data/test/gfx1030_36.cd.pdb.txt'

  arch, num_cu, final_file, copy_files = parse_text_pdb_name(master_file)
  assert (arch == "gfx1030")
  assert (num_cu == 36)
  assert (final_file == "/data/tests/gfx1030_36.cd.pdb.txt")
  assert (copy_files == [])


def test_load_master_list():
  master_file = '/data/tests/gfx803_36.HIP.fdb.txt'
  master_list = load_master_list(master_file)

  list1 = list(master_list.keys())
  values = list(master_list.values())

  if master_list == {}:
    assert False
  else:
    assert True
  if master_list:
    assert (list(master_list.keys())[0] ==
            '1-1-1-4x4-512-4-4-128-0x0-1x1-1x1-0-NCHW-FP32-B')
    assert (list(master_list.values())[0] == {
        'miopenConvolutionBwdDataAlgoWinograd':
            'ConvBinWinogradRxSf2x3,0.06365,0,miopenConvolutionBwdDataAlgoWinograd,<unused>',
        'miopenConvolutionBwdDataAlgoGEMM':
            'GemmBwdRest,4.0393,32768,rocBlas,<unused>'
    })


def test_best_solver():

  FdbKey_Set = ({
      'miopenConvolutionFwdAlgoImplicitGEMM':
          'ConvHipImplicitGemmForwardV4R4Xdlops_Padded_Gemm, 0.02352,0,miopenConvolutionFwdAlgoImplicitGEMM,not used',
      'miopenConvolutionFwdAlgoWinograd':
          'ConvBinWinogradRxSf2x3g1,0.03856,0,miopenConvolutionFwdAlgoWinograd,not used',
      'miopenConvolutionFwdAlgoGEMM':
          'GemmFwdRest,0.05712,2749200,miopenConvolutionFwdAlgoGEMM,not used'
  })

  solver, time = best_solver(FdbKey_Set)
  if (len(solver) == 0):
    assert (False)
  else:
    assert (True)

  if (float(time)):
    assert (True)
  else:
    assert (False)

  assert (solver == 'ConvHipImplicitGemmForwardV4R4Xdlops_Padded_Gemm')
  assert (time == 0.02352)

  #Sample as space, time 0.0
  test_value = ({
      'miopenConvolutionFwdAlgoImplicitGEMM':
          ' ,0.00000,0,miopenConvolutionFwdAlgoImplicitGEMM,not used'
  })

  new_solver, new_time = best_solver(test_value)
  if (not (new_solver and new_solver.isspace())):
    assert (True)
  else:
    assert (False)

  #Sample as None and time 0.0

  test_value = ({
      'miopenConvolutionFwdAlgoImplicitGEMM':
          ' ,0.00000,0,miopenConvolutionFwdAlgoImplicitGEMM,not used'
  })

  new_solver, new_time = best_solver(test_value)
  if (not (new_solver and new_solver == "None")):
    assert (False)
  else:
    assert (True)


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
  if (key == '1-160-698-5x5-64-79-348-1-1x1-2x2-1x1-0-NCHW-FP32-F'):
    assert (True)
  if (master_list[key] == {
      'miopenConvolutionFwdAlgoImplicitGEMM':
          'ConvMlirIgemmFwdXdlops,0.03776,0,miopenConvolutionFwdAlgo    ImplicitGEMM,not used'
  }):
    assert (True)

  keep_keys = True
  key = '1-19-19-1x1-64-19-19-1024-0x0-1x1-1x1-0-NCHW-FP32-B'

  target_merge(master_list, key, vals, keep_keys)

  if ((master_list[key]) == {
      'miopenConvolutionBwdDataAlgoWinograd':
          'ConvBinWinogradRxSf2x3g1,0.186719,0,miopenConvolutionBwd    DataAlgoWinograd,not used',
      'miopenConvolutionBwdDataAlgoDirect':
          'ConvOclDirectFwd1x1,0.234239,0,miopenConvolutionBwdData    AlgoDirect,not used',
      'miopenConvolutionBwdDataAlgoGEMM':
          'GemmBwd1x1_stride1,0.239519,0,miopenConvolutionBwdDataAlgoGEMM,    not used',
      'miopenConvolutionBwdDataAlgoImplicitGEMM':
          'ConvAsmImplicitGemmGTCDynamicBwdXdlopsNHWC,0.327199,94633984,miope    nConvolutionBwdDataAlgoImplicitGEMM,not used',
      'miopenConvolutionFwdAlgoImplicitGEMM':
          'ConvMlirIgemmFwdXdlops,0.03776,0,m    iopenConvolutionFwdAlgoImplicitGEMM,not used'
  }):

    assert (True)

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
  target_merge(master_list, key, vals, keep_keys)
  assert (vals == {})

  try:
    target_merge(master_list={}, key={}, vals={}, keep_keys=False)
  except AttributeError:
    assert (True)

  try:

    keep_keys = False
    key = '1-160-698-5x5-64-79-348-1-1x1-2x2-1x1-0-NCHW-FP32-F'

    vals = {
        'miopenConvolutionFwdAlgoImplicitGEMM':
            'ConvMlirIgemmFwdXdlops,0.03776,0,miopenConvolutionFwdAlgoImplicitGEMM,not used'
    }
    master_list = {}
    target_merge(master_list, key, vals, keep_keys)

  except AttributeError:
    assert (True)

    keep_keys = False
    key = '1-160-698-5x5-64-79-348-1-1x1-2x2-1x1-0-NCHW-FP32-F'

    vals = {
        'miopenConvolutionFwdAlgoImplicitGEMM':
            'ConvMlirIgemmFwdXdlops,0.03776,0,miopenConvolutionFwdAlgoImplicitGEMM,not used'
    }


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

  key = '1-160-698-5x5-64-79-348-1-1x1-2x2-1x1-0-NCHW-FP32-F'
  local_paths = ['/data/tests/../utils/test_files/usr_gfx90a68.HIP.fdb.txt']
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

  final_file = '/data/tests/final.txt'
  copy_files = []

  key = '1-48-480-3x3-16-48-480-1-1x1-1x1-1x1-0-NCHW-FP16-F'
  write_merge_results(master_list, final_file, copy_files)

  if key == open('/data/tests/final.txt').read():
    assert (True)
    f.close()

  #input set to invalid types
  master_list = {}

  final_file = '/data/tests/final.txt'
  key = {0}
  write_merge_results(master_list, final_file, copy_files)

  if key == open('/data/tests/final.txt').read():
    assert (True)
    f.close()


def test_merge_text_file():
  master_file = '/data/utils/test_files/old_gfx90a68.HIP.fdb.txt'
  copy_only = False
  keep_keys = False
  target_file = '/data/utils/test_files/usr_gfx90a68.HIP.fdb.txt'

  result_file = merge_text_file(master_file, copy_only, keep_keys, target_file)

  if (os.stat(result_file)):
    assert (True)
  else:
    assert (False)

  try:
    assert [row for row in open(master_file)
           ] == [row for row in open(target_file)]
  except AssertionError as msg:
    assert (True)

  #targetr_file set to None

  master_file = '/data/utils/test_files/old_gfx90a68.HIP.fdb.txt'
  result_file = merge_text_file(master_file,
                                copy_only=False,
                                keep_keys=False,
                                target_file=None)

  if (os.stat(result_file)):
    assert (True)
  else:
    assert (False)


def test_get_sqlite_table():

  local_path = '/data/utils/test_files/test_gfx90678.db'
  cnx_from = sqlite3.connect(local_path)
  perf_rows, perf_cols = get_sqlite_table(cnx_from, 'perf_db')

  if not perf_rows and not perf_cols:
    assert (False)
  else:
    assert (True)


def test_get_sqlite_row():

  local_path = '/data/utils/test_files/test_gfx90678.db'
  cnx_from = sqlite3.connect(local_path)

  perf_rows, perf_cols = get_sqlite_table(cnx_from, 'perf_db')
  for row in perf_rows:
    perf = dict(zip(perf_cols, row))

    cfg_row, cfg_cols = get_sqlite_row(cnx_from, 'config', perf['config'])
    cfg = dict(zip(cfg_cols, cfg_row))
    cfg.pop('id', None)

  if not cfg_row and cfg_row:
    assert (False)
  else:
    assert (True)


def test_get_sqlite_data():

  local_path = '/data/utils/test_files/test_gfx90678.db'
  final_file = '/data/utils/test_files/test_gfx90678.db'
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

  cnx_from = sqlite3.connect(local_path)
  cnx_to = sqlite3.connect(final_file)

  res, col = get_sqlite_data(cnx_to, 'config', prune_cfg_dims(cfg))

  if not res:
    assert (False)
  else:
    assert (True)
