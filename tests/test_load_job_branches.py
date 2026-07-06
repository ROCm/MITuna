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
"""Branch coverage for load_job."""
import argparse
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import tuna.miopen.subcmd.load_job as load_job
from tuna.miopen.utils.config_type import ConfigType
from tuna.miopen.utils.metadata import ALG_SLV_MAP, TENSOR_PRECISION


class _FakeQuery:
  """Minimal query stub."""

  def __init__(self, result=None):
    self._result = result or []
    self.filters = []

  def filter(self, cond):
    self.filters.append(cond)
    return self

  def all(self):
    return self._result

  def subquery(self):
    return self


class _FakeSession:
  """DbSession replacement to avoid hitting the database."""

  def __init__(self, result=None):
    self.result = result or []
    self.executed = []

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    return False

  def query(self, *_, **__):
    return _FakeQuery(self.result)

  def execute(self, stmt):
    self.executed.append(stmt)
    return []

  def add(self, *_):
    return None

  def commit(self):
    return None

  def rollback(self):
    return None


class _FakeColumn:
  """Column stub supporting in_ operator used in filters."""

  def __init__(self, value=None):
    self.value = value

  def in_(self, _):
    return self


def test_arg_solvers_uses_algo(monkeypatch):
  algo = next(iter(ALG_SLV_MAP.keys()))
  args = argparse.Namespace(solvers=None, algo=algo)
  logger = MagicMock()
  result = load_job.arg_solvers(args, logger)
  assert result.solvers[0][0] in ALG_SLV_MAP[algo]


def test_test_tag_name_missing(monkeypatch):
  monkeypatch.setattr(load_job, 'DbSession', lambda: _FakeSession(result=[]))
  with pytest.raises(ValueError):
    load_job.test_tag_name('missing', MagicMock())


def test_config_query_filters(monkeypatch):
  cmd_key = next(iter(TENSOR_PRECISION.keys()))
  session = _FakeSession(result=[(1,)])
  args = argparse.Namespace(tag='foo', cmd=cmd_key)
  dbt = SimpleNamespace(
      config_table=SimpleNamespace(
          id=_FakeColumn(),
          valid=1,
          input_t=SimpleNamespace(data_type=_FakeColumn())),
      config_tags_table=SimpleNamespace(config=_FakeColumn(), tag='foo'),
  )
  query = load_job.config_query(args, session, dbt)
  assert isinstance(query, _FakeQuery)


def test_compose_query_with_filters(monkeypatch):
  args = argparse.Namespace(session_id=1,
                            solvers=[('s', 1)],
                            tunable=True,
                            config_type=ConfigType.batch_norm,
                            only_dynamic=True)
  dbt = SimpleNamespace(solver_app=SimpleNamespace(config=_FakeColumn(),
                                                   session=_FakeColumn(),
                                                   solver=_FakeColumn(),
                                                   applicable=_FakeColumn()),
                        config_table=SimpleNamespace(id=_FakeColumn()),
                        job_table=SimpleNamespace(__tablename__='job'))
  session = _FakeSession(result=[(1, 'solver')])
  query = load_job.compose_query(args, session, dbt, _FakeQuery(result=[1]))
  assert isinstance(query, _FakeQuery)


def test_add_jobs_empty_results(monkeypatch, caplog):
  logger = MagicMock()
  dbt = SimpleNamespace(job_table=SimpleNamespace(__tablename__='job'))
  args = argparse.Namespace(label='lbl',
                            fin_steps=None,
                            session_id=1,
                            solvers=[('', None)],
                            tag=None,
                            cmd=None,
                            tunable=False,
                            config_type=ConfigType.convolution,
                            only_dynamic=False)
  monkeypatch.setattr(load_job, 'DbSession', lambda: _FakeSession(result=[]))
  monkeypatch.setattr(load_job, 'config_query', lambda *_: _FakeQuery())
  monkeypatch.setattr(load_job, 'compose_query', lambda *_: _FakeQuery())
  count = load_job.add_jobs(args, dbt, logger)
  assert count == 0
  logger.error.assert_called_once()


def test_run_load_job_tag_error(monkeypatch, capsys):
  args = argparse.Namespace(tag='missing',
                            solvers=None,
                            algo=None,
                            fin_steps=None,
                            config_type=ConfigType.convolution,
                            session_id=1,
                            label='lbl',
                            only_dynamic=False,
                            tunable=False)
  logger = MagicMock()
  monkeypatch.setattr(load_job, 'test_tag_name', lambda *_:
                      (_ for _ in ()).throw(ValueError('missing')))
  monkeypatch.setattr(load_job, 'add_jobs', lambda *_: 0)
  load_job.run_load_job(args, logger)
  captured = capsys.readouterr()
  assert 'New jobs added' in captured.out
