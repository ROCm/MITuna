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
from tuna.update_golden import merge_golden_entries, get_fdb_query
from tuna.tables import DBTables
from tuna.dbBase.sql_alchemy import DbSession
from tuna.config_type import ConfigType
from tuna.miopen_tables import ConvolutionGolden
from tuna.find_db import ConvolutionFindDB
from utils import add_test_session, DummyArgs

sys.path.append("../tuna")
sys.path.append("tuna")


def add_fdb_entry(session_id):
  with DbSession() as session:
    fdb_entry = ConvolutionFindDB()
    fdb_entry.config = 1
    fdb_entry.solver = 1
    fdb_entry.session = session_id
    fdb_entry.opencl = False

    fdb_entry.fdb_key = 1
    fdb_entry.alg_lib = 'Test'
    fdb_entry.params = 1
    fdb_entry.workspace_sz = 0
    fdb_entry.valid = True
    fdb_entry.kernel_time = 11111
    fdb_entry.kernel_group = 1

    session.add(fdb_entry)
    session.commit()


def test_update_golden():
  session_id = add_test_session()
  add_fdb_entry(session_id)

  res = None
  args = DummyArgs()
  args.session_id = session_id
  args.config_type = ConfigType.convolution
  args.golden_v = 1
  dbt = DBTables(session_id=args.session_id, config_type=args.config_type)
  entries = get_fdb_query(dbt).all()
  assert entries

  with DbSession() as session:
    assert merge_golden_entries(session, dbt, args.golden_v, entries)
    query = session.query(ConvolutionGolden)
    res = query.all()
  assert len(res) is not None
