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
from tuna.miopen.subcmd.update_golden import gold_base_update, gold_session_update, create_perf_table, verify_no_duplicates, latest_golden_v
from tuna.miopen.db.tables import MIOpenDBTables
from tuna.dbBase.sql_alchemy import DbSession
from tuna.miopen.utils.config_type import ConfigType
from tuna.miopen.db.miopen_tables import ConvolutionGolden
from tuna.miopen.db.find_db import ConvolutionFindDB
from utils import add_test_session, DummyArgs

sys.path.append("../tuna")
sys.path.append("tuna")


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


def test_update_golden():
  session_id = add_test_session(arch='gfx90a', num_cu=110, label='pytest_update_golden')
  fdb_entry = build_fdb_entry(session_id)
  with DbSession() as session:
    session.add(fdb_entry)
    session.commit()

  res = None
  args = DummyArgs()
  args.session_id = session_id
  args.config_type = ConfigType.convolution
  dbt = MIOpenDBTables(session_id=args.session_id, config_type=args.config_type)

  gld_v1 = latest_golden_v(dbt) + 1
  args.golden_v = gld_v1

  with DbSession() as session:
    assert gold_session_update(session, gld_v1, session_id, True)
    query = session.query(ConvolutionGolden)\
                    .filter(ConvolutionGolden.golden_miopen_v == gld_v1)\
                    .filter(ConvolutionGolden.session == session_id)
    res = query.all()
    assert len(res) == 1
    assert res[0].params == 'param'

    gld_v2 = gld_v1 + 1
    assert gold_base_update(session, gld_v2, gld_v1, True)
    query = session.query(ConvolutionGolden)\
                    .filter(ConvolutionGolden.golden_miopen_v == gld_v2)\
                    .filter(ConvolutionGolden.session == session_id)
    res = query.all()
    assert len(res) == 1
    assert res[0].params == 'param'


  entries = session.query(ConvolutionFindDB)\
                  .filter(ConvolutionFindDB.session == session_id).all()
  assert verify_no_duplicates(entries)

  fdb_entry2 = build_fdb_entry(session_id)
  fdb_entry2.config = 2
  entries.append(fdb_entry2)
  assert verify_no_duplicates(entries)

  fdb_entry3 = build_fdb_entry(session_id)
  fdb_entry3.solver = 2
  entries.append(fdb_entry3)
  assert verify_no_duplicates(entries)

  session_id2 = add_test_session(arch='gfx90a', num_cu=110, label='pytest_update_golden2')
  fdb_entry4 = build_fdb_entry(session_id2)
  entries.append(fdb_entry4)
  assert verify_no_duplicates(entries)

  fdb_entry5 = build_fdb_entry(session_id)
  fdb_entry5.params = 'something'
  entries.append(fdb_entry5)
  assert verify_no_duplicates(entries) == False

  args.create_perf_table = True
  assert create_perf_table(args)


def copy(dest, src):
  dest.__dict__ = src.__dict__.copy()
