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

from tuna.utils.merge_db import parse_jobline
from tuna.utils.merge_db import parse_text_fdb_name
from tuna.utils.merge_db import parse_text_pdb_name
from tuna.utils.merge_db import load_master_list
from tuna.utils.merge_db import best_solver
from tuna.utils.merge_db import target_merge
from tuna.utils.merge_db import no_job_merge
from tuna.utils.merge_db import single_job_merge
from tuna.utils.merge_db import multi_job_merge
from tuna.utils.merge_db import update_master_list
from tuna.utils.merge_db import write_merge_results
from tuna.utils.merge_db import merge_text_file
from tuna.utils.merge_db import merge_sqlite_pdb
from tuna.utils.merge_db import merge_sqlite_bin_cache
from tuna.utils.merge_db import merge_sqlite
from tuna.utils.merge_db import get_file_list
from tuna.utils.merge_db import get_sqlite_table
from tuna.utils.merge_db import get_sqlite_row
from tuna.helper import prune_cfg_dims
from tuna.utils.merge_db import get_sqlite_data

this_path = os.path.dirname(__file__)


def test_merge_db_functions():
  test_parse_jobline
  test_parse_text_fdb_name
  test_parse_text_pdb_name
  test_load_master_list
  test_best_solver
  test_target_merge
  test_update_master_list
  test_write_merge_results
  test_merge_text_file
  test_get_sqlite_table
  test_get_sqlite_row
  test_get_sqlite_data
  test_get_file_list


def test_parse_jobline():
  data = """1-160-698-5x5-64-79-348-1-1x1-2x2-1x1-0-NCHW-FP32-F=miopenConvolutionFwdAlgoImplicitGEMM:
        ConvHipImplicitGemmForwardV4R4Xdlops_Padded_Gemm,
        0.02352,0,miopenConvolutionFwdAlgoImplicitGEMM,not used;
        miopenConvolutionFwdAlgoWinograd:ConvBinWinogradRxSf2x3g1,0.03856,0,miopenConvolutionFwdAlgoWinograd,
        not used;miopenConvolutionFwdAlgoDirect:ConvOclDirectFwdGen,0.0536,0,miopenConvolutionFwdAlgoDirect,not used;
        miopenConvolutionFwdAlgoGEMM:GemmFwdRest,0.05712,2749200,miopenConvolutionFwdAlgoGEMM,not used"""

  key, vals = parse_jobline(data)
  assert key, vals


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
  if master_list == {}:
    assert False
  else:
    assert True


def test_best_solver():
  #valid sample input test
  test_value = ({
      'miopenConvolutionFwdAlgoImplicitGEMM':
          'ConvMlirIgemmFwdXdlops,0.03776,0,miopenConvolutionFwdAlgoImplicitGEMM,not used'
  })

  new_solver, new_time = best_solver(test_value)
  print(type(new_solver), new_solver)
  print(type(new_time), new_time)
  if (len(new_solver) == 0):
    assert (False)
  else:
    assert (True)

  if (float(new_time)):
    assert (True)
  else:
    assert (False)

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
          'None ,0.00000,0,miopenConvolutionFwdAlgoImplicitGEMM,not used'
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

  final_file = '/data/tests/old_gfx90a68.HIP.fdb.txt'
  copy_files = []

  write_merge_results(master_list, final_file, copy_files)


def test_merge_text_file():
  master_file = '/data/MITunaX/tests/../utils/test_files/old_gfx90a68.HIP.fdb.txt'
  copy_only = False
  keep_keys = False
  target_file = '/data/tests/../utils/test_files/usr_gfx90a68.HIP.fdb.txt'

  result_file = merge_text_file(master_file, copy_only, keep_keys, target_file)

  if (os.stat(result_file)):
    assert (True)
  else:
    assert (False)

  #targetr_file set to None
  result_file = merge_text_file(master_file=None,
                                copy_only=False,
                                keep_keys=False,
                                target_file=None)


def test_get_sqlite_table():

  local_path = '/data/utils/test_files/test_gfx90678.db'
  cnx_from = sqlite3.connect(local_path)
  perf_rows, perf_cols = get_sqlite_table(cnx_from, 'perf_db')

  if not perf_rows:
    assert (False)
  else:
    assert (True)

  if not perf_cols:
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
    print(type(cfg_row), type(cfg_cols))
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

  print(type(res), res)
  print(type(col), col)

  if not res:
    assert (False)
  else:
    assert (True)


def test_get_file_list():
  print('test - get file list')
