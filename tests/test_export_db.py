###############################################################################
#
# MIT License
#
# Copyright (c) 2023 Advanced Micro Devices, Inc.
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
import argparse
import logging
import pytest

from sqlalchemy.orm import Query
from sqlalchemy.ext.declarative import declarative_base

sys.path.append("../tuna")
sys.path.append("tuna")

this_path = os.path.dirname(__file__)

from tuna.miopen.subcmd.export_db import (arg_export_db, get_filename,
                                          get_base_query, get_fdb_query,
                                          get_pdb_query, get_fdb_alg_lists,
                                          build_miopen_fdb, write_fdb,
                                          export_fdb, build_miopen_kdb,
                                          write_kdb, export_kdb)
from tuna.utils.db_utility import DB_Type
from tuna.miopen.db.tables import MIOpenDBTables, ConfigType
from tuna.dbBase.sql_alchemy import DbSession
from tuna.miopen.db.find_db import ConvolutionFindDB
from utils import add_test_session, DummyArgs


@pytest.fixture
def mock_args():
  args = argparse.Namespace()
  args.golden_v = None
  args.arch = "arch"
  args.num_cu = 64
  args.opencl = "1"
  args.config_tag = None
  args.filename = None
  return args


#testing fdb and pdb functions
def build_fdb_entry(session_id):
  fdb_entry = ConvolutionFindDB()
  fdb_entry.config = 1
  fdb_entry.solver = 1
  fdb_entry.session = session_id
  fdb_entry.opencl = False

  fdb_entry.fdb_key = 'key'
  fdb_entry.alg_lib = 'Test'
  fdb_entry.params = 'param'
  fdb_entry.workspace_sz = 0
  fdb_entry.valid = True
  fdb_entry.kernel_time = 11111
  fdb_entry.kernel_group = 1

  return fdb_entry


session_id = add_test_session()
fdb_entry = build_fdb_entry(session_id)
args = DummyArgs()
args.session_id = session_id
args.config_type = ConfigType.convolution
dbt = MIOpenDBTables(session_id=args.session_id, config_type=args.config_type)

logger = logging.getLogger("test_logger")


def test_get_file():
  arch = "gfx900"
  num_cu = 64
  filename = None
  ocl = True
  db_type = DB_Type.FIND_DB

  expeted_filename = "tuna_1.0.0/gfx900_64.OpenCL.fdb.txt"
  actual_filename = get_filename(arch, num_cu, filename, ocl, db_type)

  assert actual_filename == expeted_filename, f"expected {expeted_filename}, but got {actual_filename}"


with DbSession() as session:
  session.add(fdb_entry)
  session.commit()

with DbSession() as session:

  def test_get_base_query(mock_args):
    query = get_base_query(dbt, mock_args, logger)
    assert query is not None, "Query object is None"
    assert isinstance(
        query,
        Query), f"epected query to be an instance of Query, Got {type(query)}"

  def test_get_fdb_query(mock_args):
    fdb_query = get_fdb_query(dbt, mock_args, logger)
    assert fdb_query is not None, "Query object is None"
    assert isinstance(
        fdb_query, Query
    ), f"epected query to be an instance of Query, Got {type(fdb_query)}"

  def test_get_fdb_alg_lists(mock_args):
    fdb_query = get_fdb_query(dbt, mock_args, logger)
    alg_lists = get_fdb_alg_lists(fdb_query, logger)
    assert alg_lists is not None, f"expected a retrived an fdb alg list, Got {type(test_get_fdb_alg_lists)}"

  def test_get_pdb_query(mock_args):
    pdb_query = get_pdb_query(dbt, mock_args, logger)
    assert pdb_query is not None, "Query object is None"
    assert isinstance(
        pdb_query, Query
    ), f"epected query to be an instance of Query, Got {type(pdb_query)}"

  def test_build_export_miopen_fdp(mock_args):
    fdb_query = get_fdb_query(dbt, mock_args, logger)
    alg_lists = get_fdb_alg_lists(fdb_query, logger)
    miopen_fdb = build_miopen_fdb(alg_lists, logger)
    fdb_file = write_fdb(mock_args.arch, mock_args.num_cu, mock_args.opencl,
                         miopen_fdb, mock_args.filename)
    fdb_exported = export_fdb(dbt, mock_args, logger)
    assert miopen_fdb is not None, f"failed to build miopen_fdb, Got {type(miopen_fdb)}"
    assert fdb_file is not None
    assert fdb_exported is not None

  def test_buid_miopen_kdp(mock_args):
    fdb_query = get_fdb_query(dbt, mock_args, logger)
    alg_lists = get_fdb_alg_lists(fdb_query, logger)
    build_mioopen_kdp = build_miopen_kdb(dbt, alg_lists, logger)
    assert build_mioopen_kdp is not None

  session.delete(fdb_entry)
  session.commit()
