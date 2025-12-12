###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
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
"""Additional branch coverage for export_db."""
import argparse
import base64
import json
import os
import sqlite3
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import tuna.miopen.subcmd.export_db as export_db
from tuna.utils.db_utility import DB_Type
from tuna.miopen.utils.config_type import ConfigType


class _FakeColumn:
  """Lightweight column stub that records equality checks."""

  def __init__(self, name):
    self.name = name

  def __eq__(self, other):
    return SimpleNamespace(value=other)

  def in_(self, _):
    return self


class _FakeQuery:
  """Query stub that carries simple state."""

  def __init__(self, entries=None, value=None):
    self._entries = entries or []
    self.value = value

  def all(self):
    return self._entries

  def filter(self, cond):
    val = getattr(cond, 'value', None)
    return _FakeQuery(self._entries, val)

  def distinct(self):
    return self

  def subquery(self):
    return self

  def order_by(self, *_, **__):
    return self


def _fake_session_factory(num_cu_values):
  """Build a DbSession replacement that returns provided num_cu values."""

  class _FakeSession:

    def __enter__(self):
      return self

    def __exit__(self, exc_type, exc_val, exc_tb):
      return False

    def query(self, *_):
      return _FakeQuery(entries=[(val,) for val in num_cu_values])

    def commit(self):
      return None

  return _FakeSession


def test_arg_export_db_requires_arch(monkeypatch):
  args = argparse.Namespace(golden_v='1.0', arch=None)
  logger = MagicMock()
  export_db.arg_export_db(args, logger)
  logger.error.assert_called_once()


def test_get_filename_variants(monkeypatch, tmp_path):
  monkeypatch.chdir(tmp_path)
  # filename provided
  fname = export_db.get_filename('gfx900', None, 'custom', True,
                                 DB_Type.FIND_DB)
  assert fname.endswith('custom.OpenCL.fdb.txt')
  # num_cu missing falls back to arch
  fname = export_db.get_filename('gfx900', None, None, False, DB_Type.PERF_DB)
  assert fname.endswith('gfx900.db.txt')
  # num_cu over 64 encoded as hex
  fname = export_db.get_filename('gfx900', 128, None, False, DB_Type.FIND_DB)
  assert fname.endswith('gfx90080.HIP.fdb.txt')
  # kernel db extension
  fname = export_db.get_filename('gfx900', 32, None, False, DB_Type.KERN_DB)
  assert fname.endswith('.kdb')


def test_fin_net_cfg_job_non_convolution(monkeypatch):
  logger = MagicMock()
  jobs = export_db.fin_net_cfg_job([], logger, ConfigType.batch_norm)
  logger.error.assert_called_once()
  assert jobs == []


def test_add_entry_to_solvers_duplicate():
  solvers = {'k1': {'solver_a': 123}}
  entry = SimpleNamespace(fdb_key='k1', solver='solver_a', update_ts=456)
  added = export_db.add_entry_to_solvers(entry, solvers, MagicMock())
  assert added is False
  assert solvers['k1']['solver_a'] == 123


def test_build_miopen_fdb_trims(monkeypatch):
  monkeypatch.setattr(export_db, 'require_id_solvers', lambda: None)
  monkeypatch.setattr(export_db, 'ID_SOLVER_MAP', {
      's0': 0,
      's1': 1,
      's2': 2,
      's3': 3,
      's4': 4
  })

  class _Entry(SimpleNamespace):
    pass

  entries = []
  for idx in range(5):
    entries.append((_Entry(fdb_key='key',
                           solver=f's{idx}',
                           kernel_time=idx,
                           workspace_sz=0,
                           update_ts=idx), None))

  query = _FakeQuery(entries=entries)
  result = export_db.build_miopen_fdb(query, MagicMock())
  assert 'key' in result
  assert len(result['key']) == 4
  assert all(isinstance(x, _Entry) for x in result['key'])


def test_write_kdb_handles_extensions_and_dedup(monkeypatch, tmp_path):
  monkeypatch.chdir(tmp_path)
  logger = MagicMock()
  blob = base64.b64encode(b'abc')
  kern1 = SimpleNamespace(kernel_name='k',
                          kernel_args='arg',
                          kernel_blob=blob,
                          kernel_hash='h1',
                          uncompressed_size=1,
                          kernel_group=1)
  kern2 = SimpleNamespace(kernel_name='k',
                          kernel_args='arg',
                          kernel_blob=blob,
                          kernel_hash='h1',
                          uncompressed_size=1,
                          kernel_group=1)
  kern3 = SimpleNamespace(kernel_name='k.mlir',
                          kernel_args='arg3',
                          kernel_blob=blob,
                          kernel_hash='h3',
                          uncompressed_size=1,
                          kernel_group=2)
  fname = export_db.write_kdb('gfx900',
                              64, [kern1, kern2, kern3],
                              logger,
                              filename='out')
  conn = sqlite3.connect(fname)
  cur = conn.cursor()
  cur.execute("SELECT kernel_name, kernel_args FROM kern_db ORDER BY id")
  rows = cur.fetchall()
  cur.close()
  conn.close()
  # duplicate filtered, mlir keeps args as-is without -mcpu
  assert len(rows) == 2
  assert rows[0][0] == 'k.o'
  assert '-mcpu=gfx900' in rows[0][1]
  assert rows[1][0] == 'k.mlir.o'
  assert '-mcpu=' not in rows[1][1]


def test_build_miopen_fdb_skews(monkeypatch):
  # ensure deterministic solver map for sorting
  monkeypatch.setattr(export_db, 'require_id_solvers', lambda: None)
  monkeypatch.setattr(export_db, 'ID_SOLVER_MAP', {'s': 0})

  args = SimpleNamespace()
  args.src_table = SimpleNamespace(num_cu=_FakeColumn('num_cu'),
                                   id=_FakeColumn('id'))
  query = _FakeQuery(entries=[(SimpleNamespace(id=1), None)])

  def fake_build(miopen_query, logger):
    return {f"k_{miopen_query.value}": ['entry']}

  fake_session = _fake_session_factory([64, 32])
  monkeypatch.setattr(export_db, 'DbSession', fake_session)
  monkeypatch.setattr(export_db, 'build_miopen_fdb', fake_build)

  res = export_db.build_miopen_fdb_skews(args, query, MagicMock())
  assert set(res.keys()) == {'k_64_cu64', 'k_32_cu32'}


def test_export_kdb_uses_skews(monkeypatch):
  args = SimpleNamespace(arch='gfx', num_cu=None, filename=None, opencl=False)
  dbt = SimpleNamespace()
  logger = MagicMock()
  monkeypatch.setattr(export_db, 'get_fdb_query', lambda *_: _FakeQuery())
  monkeypatch.setattr(export_db, 'build_miopen_fdb_skews',
                      lambda *_, **__: {'k': ['v']})
  monkeypatch.setattr(export_db, 'build_miopen_kdb', lambda *_: [1, 2, 3])
  monkeypatch.setattr(export_db, 'write_kdb', lambda *_, **__: 'kdb.out')
  result = export_db.export_kdb(dbt, args, logger, skew_fdbs=True)
  assert result == 'kdb.out'


def test_build_miopen_pdb(monkeypatch):
  monkeypatch.setattr(export_db, 'require_id_solvers', lambda: None)
  monkeypatch.setattr(export_db, 'ID_SOLVER_MAP', {'s1': 1})
  args = SimpleNamespace()
  query_entries = [
      (SimpleNamespace(fdb_key='key1',
                       solver='s1',
                       kernel_time=1,
                       workspace_sz=0,
                       update_ts=1,
                       params='p1'), SimpleNamespace(id=1)),
      (SimpleNamespace(fdb_key='dup',
                       solver='s1',
                       kernel_time=2,
                       workspace_sz=0,
                       update_ts=2,
                       params='p1'), SimpleNamespace(id=1)),
      (SimpleNamespace(fdb_key='key2',
                       solver='s1',
                       kernel_time=3,
                       workspace_sz=0,
                       update_ts=3,
                       params='p2'), SimpleNamespace(id=2)),
  ]
  query = _FakeQuery(entries=query_entries)
  monkeypatch.setattr(export_db, 'fin_db_key', lambda *_: {1: 'db1', 2: 'db2'})
  res = export_db.build_miopen_pdb(query, MagicMock())
  assert set(res.keys()) == {'db1', 'db2'}
  # duplicate solver entry skipped, leaving one record for db1
  assert len(res['db1']) == 1


def test_write_pdb_orders_by_solver(monkeypatch, tmp_path):
  monkeypatch.chdir(tmp_path)
  monkeypatch.setattr(export_db, 'require_id_solvers', lambda: None)
  monkeypatch.setattr(export_db, 'ID_SOLVER_MAP', {'s1': 1, 's2': 2})
  perf_db = {
      'db': [
          SimpleNamespace(solver='s2', params='two'),
          SimpleNamespace(solver='s1', params='one')
      ]
  }
  path = export_db.write_pdb('gfx', 1, False, perf_db, filename='perf.txt')
  with open(path, 'r', encoding='utf-8') as fp:
    line = fp.read().strip()
  assert line == 'db=1:one;2:two'


def test_export_pdb_txt(monkeypatch):
  args = SimpleNamespace(arch='gfx', num_cu=1, opencl=False, filename=None)
  dbt = SimpleNamespace()
  logger = MagicMock()
  monkeypatch.setattr(export_db, 'get_pdb_query', lambda *_: _FakeQuery())
  monkeypatch.setattr(export_db, 'build_miopen_pdb',
                      lambda *_: {'db': ['entry']})
  monkeypatch.setattr(export_db, 'write_pdb', lambda *_, **__: 'perf.out')
  res = export_db.export_pdb_txt(dbt, args, logger)
  assert res == 'perf.out'


def test_run_export_db_routes(monkeypatch, capsys):

  class _DummyTables:

    def __init__(self, session_id=None, **_):
      self.session = SimpleNamespace(arch='gfxA', num_cu=64)
      self.find_db_table = 'find'
      self.golden_table = 'golden'
      self.session_id = session_id

  args = argparse.Namespace(session_id=1,
                            golden_v='1.0',
                            find_db=True,
                            kern_db=False,
                            perf_db=False,
                            arch=None,
                            num_cu=None,
                            opencl=False,
                            filename=None)
  logger = MagicMock()
  monkeypatch.setattr(export_db, 'MIOpenDBTables', _DummyTables)
  monkeypatch.setattr(export_db, 'export_fdb', lambda *_: 'out.find')
  export_db.run_export_db(args, logger)
  captured = capsys.readouterr()
  assert 'out.find' in captured.out
