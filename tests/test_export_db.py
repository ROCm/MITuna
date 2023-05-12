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
from tuna.miopen.subcmd.export_db import get_fdb_query, build_miopen_fdb, get_pdb_query, build_miopen_kdb
from utils import add_test_session, DummyArgs

sys.path.append("../tuna")
sys.path.append("tuna")

this_path = os.path.dirname(__file__)


def test_export_db():
  session_id = add_test_session(arch='gfx90a',
                                num_cu=110,
                                label='pytest_export_db')

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
    fdb_entry.fdb_key = 'key1'
    fdb_entry.params = 'params'
    fdb_entry.kernel_time = 10
    fdb_entry.workspace_sz = 0
    fdb_entry.kernel_group = 11359
    session.add(fdb_entry)

    fdb_entry2 = dbt.find_db_table()
    fdb_entry2.solver = 1
    fdb_entry2.config = 2
    fdb_entry2.opencl = False
    fdb_entry2.session = session_id
    fdb_entry2.fdb_key = 'key2'
    fdb_entry2.params = 'params'
    fdb_entry2.kernel_time = 10
    fdb_entry2.workspace_sz = 0
    fdb_entry2.kernel_group = 11360
    session.add(fdb_entry2)

    kcache = dbt.kernel_cache()
    kcache.kernel_name = 'kname1'
    kcache.kernel_args = 'arg1'
    kcache.kernel_blob = bytes('blob', 'utf-8')
    kcache.kernel_hash = 0
    kcache.uncompressed_size = 0
    kcache.kernel_group = 11359
    session.add(kcache)

    kcache2 = dbt.kernel_cache()
    kcache2.kernel_name = 'kname2'
    kcache2.kernel_args = 'arg2'
    kcache2.kernel_blob = bytes('blob', 'utf-8')
    kcache2.kernel_hash = 0
    kcache2.uncompressed_size = 0
    kcache2.kernel_group = 11360
    session.add(kcache2)

    session.commit()

  query = get_fdb_query(dbt, args)
  miopen_fdb = build_miopen_fdb(query)
  miopen_kdb = build_miopen_kdb(dbt, miopen_fdb)

  for key, solvers in sorted(miopen_fdb.items(), key=lambda kv: kv[0]):
    if key == 'key1':
      assert solvers[0].config == 1
    elif key == 'key2':
      assert solvers[0].config == 2
    else:
      assert False

  for kern in miopen_kdb:
    if kern.kernel_group not in (11359, 11360):
      if kern.kernel_group == 11359:
        assert kern.kernel_name == 'kname1'
      elif kern.kernel_group == 11360:
        assert kern.kernel_name == 'kname2'

  pdb_entries = get_pdb_query(dbt, args).all()
  for entry, _ in pdb_entries:
    if entry.fdb_key == 'key1':
      assert entry.config == 1
    elif entry.fdb_key == 'key2':
      assert entry.config == 2
    else:
      assert False
