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
import itertools

from sqlalchemy.orm import Query
from sqlalchemy.ext.declarative import declarative_base

sys.path.append("../tuna")
sys.path.append("tuna")

this_path = os.path.dirname(__file__)

from tuna.miopen.subcmd.export_db import (
    arg_export_db, get_filename, get_base_query, get_fdb_query, get_pdb_query,
    get_fdb_alg_lists, build_miopen_fdb, write_fdb, export_fdb,
    build_miopen_kdb, insert_perf_db_sqlite, create_sqlite_tables, get_cfg_dict,
    populate_sqlite)
from tuna.utils.db_utility import DB_Type
from tuna.miopen.db.tables import MIOpenDBTables, ConfigType
from tuna.dbBase.sql_alchemy import DbSession
from tuna.miopen.db.find_db import ConvolutionFindDB
from tuna.utils.db_utility import get_id_solvers
from utils import add_test_session, DummyArgs

_, ID_SOLVER_MAP = get_id_solvers()


class CfgEntry:
  valid = 1

  @staticmethod
  def to_dict():
    return {
        'direction': 'B',
        'out_channels': 10,
        'in_channels': 5,
        'in_w': 8,
        'conv_stride_w': 1,
        'fil_w': 3,
        'pad_w': 0,
        'in_h': 8,
        'conv_stride_h': 1,
        'fil_h': 3,
        'pad_h': 0,
        'spatial_dim': 3,
        'in_d': 8,
        'conv_stride_d': 1,
        'fil_d': 3,
        'pad_d': 0
    }


class TensorEntry:
  id = 1

  @staticmethod
  def to_dict(ommit_valid=False):
    return {'id': 1, 'tensor_id_1': 'cfg_value_1', 'tensor_id_2': 'cfg_value_2'}


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

  def test_buid_miopen_kdb(mock_args):
    fdb_query = get_fdb_query(dbt, mock_args, logger)
    alg_lists = get_fdb_alg_lists(fdb_query, logger)
    build_mioopen_kdp = build_miopen_kdb(dbt, alg_lists, logger)
    assert build_mioopen_kdp is not None

  def test_create_sqlite_tables(mock_args):
    cnx, local_path = create_sqlite_tables(mock_args.arch, mock_args.num_cu,
                                           mock_args.filename)
    cur = cnx.cursor()
    cur.execute(
        "SELECT name from sqlite_master WHERE type='table' AND (name='config' or name='perf_db')"
    )
    table_names = cur.fetchall()
    cur.close()
    assert len(table_names) == 2
    assert ('config') in table_names[0]
    assert ('perf_db') in table_names[1]

    cur = cnx.cursor()
    cur.execute(
        "SELECT name from sqlite_master WHERE type='index' AND (name='idx_config' OR name='idx_perf_db')"
    )
    index_names = cur.fetchall()
    cur.close()
    assert len(index_names) == 2
    assert ('idx_config') in index_names[0]
    assert ('idx_perf_db') in index_names[1]
    cnx.close()
    os.remove(local_path)

  def test_insert_perf_db_sqlite(mock_args):
    ins_cfg_id = 1
    perf_db_entry = build_fdb_entry(session_id)
    cnx, local_path = create_sqlite_tables(mock_args.arch, mock_args.num_cu,
                                           mock_args.filename)
    perf_db_dict = insert_perf_db_sqlite(cnx, perf_db_entry, ins_cfg_id)
    expected_data = {
        "config": ins_cfg_id,
        "solver": ID_SOLVER_MAP[perf_db_entry.solver],
        "params": perf_db_entry.params
    }

    for key, value in expected_data.items():
      assert perf_db_dict[key] == value

    cur = cnx.cursor()
    cur.execute("SELECT config, solver FROM perf_db WHERE config=?",
                (ins_cfg_id,))
    inserted_data = cur.fetchone()
    cur.close()
    cnx.close()
    os.remove(local_path)
    print(inserted_data)
    print(perf_db_dict)
    assert inserted_data is not None, "No data was inserted into perf_db table"
    assert inserted_data == tuple(
        itertools.islice(expected_data.values(), 2)
    ), f"expected inserted data {tuple(itertools.islice(expected_data.values(),2))}, but got {inserted_data}"

  def test_get_cfg_dict():

    cfg_entry = CfgEntry()
    tensor_entry = TensorEntry()

    cfg_dict = get_cfg_dict(cfg_entry, tensor_entry)

    assert isinstance(cfg_dict, dict)
    assert 'tensor_id_1' in cfg_dict
    assert 'tensor_id_2' in cfg_dict
    assert cfg_dict['tensor_id_1'] == 'cfg_value_1'
    assert cfg_dict['tensor_id_2'] == 'cfg_value_2'

  session.delete(fdb_entry)
  session.commit()
