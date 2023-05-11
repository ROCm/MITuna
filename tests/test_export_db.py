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

from tuna.dbBase.sql_alchemy import DbSession
from tuna.miopen.utils.config_type import ConfigType
from tuna.miopen.db.tables import MIOpenDBTables
from tuna.miopen.subcmd.export_db import get_fdb_query, build_miopen_fdb
from utils import add_test_session, DummyArgs

sys.path.append("../tuna")
sys.path.append("tuna")

this_path = os.path.dirname(__file__)


def test_export_db():
  session_id = add_test_session()

  args = DummyArgs()
  args.session_id = session_id
  args.config_type = ConfigType.convolution
  args.golden_v = None
  args.opencl = False
  args.config_tag = None

  dbt = MIOpenDBTables(session_id=args.session_id)

  if args.session_id:
    args.arch = dbt.session.arch
    args.num_cu = dbt.session.num_cu

  with DbSession() as session:
    fdb_entry = dbt.find_db_table()
    fdb_entry.solver = 1
    fdb_entry.config = 1
    fdb_entry.opencl = False
    fdb_entry.session = session_id
    fdb_entry.fdb_key = '1x1'
    fdb_entry.params = ''
    fdb_entry.kernel_time = 10
    fdb_entry.workspace_sz = 0
    session.add(fdb_entry)

    fdb_entry2 = dbt.find_db_table()
    fdb_entry2.solver = 1
    fdb_entry2.config = 2
    fdb_entry2.opencl = False
    fdb_entry2.session = session_id
    fdb_entry2.fdb_key = '1x2'
    fdb_entry2.params = ''
    fdb_entry2.kernel_time = 10
    fdb_entry2.workspace_sz = 0
    session.add(fdb_entry2)

    session.commit()

  query = get_fdb_query(dbt, args)
  miopen_fdb = build_miopen_fdb(query)

  for key, solvers in sorted(miopen_fdb.items(), key=lambda kv: kv[0]):
    if key == '1x1':
      assert solvers[0].config == 1
    if key == '1x2':
      assert solvers[0].config == 2
