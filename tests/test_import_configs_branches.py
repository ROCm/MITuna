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
"""Branch coverage for import_configs."""
import argparse
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import tuna.miopen.subcmd.import_configs as import_configs
from tuna.miopen.utils.config_type import ConfigType
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound


class _FakeSession:
  """Simple DbSession stand‑in for unit tests."""

  def __init__(self, query_result=None, raise_on_commit=None):
    self._query_result = query_result or []
    self._raise_on_commit = raise_on_commit
    self.added = []

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    return False

  def query(self, *_, **__):

    class _Query:

      def __init__(self, result):
        self._result = result

      def filter(self, *_):
        return self

      def one(self):
        if isinstance(self._result, Exception):
          raise self._result
        return SimpleNamespace(id=self._result)

      def all(self):
        return self._result

    return _Query(self._query_result)

  def merge(self, obj):
    self.added.append(obj)
    if isinstance(self._raise_on_commit, IntegrityError):
      raise self._raise_on_commit
    return obj

  def add(self, obj):
    self.added.append(obj)
    if isinstance(self._raise_on_commit, IntegrityError):
      raise self._raise_on_commit

  def commit(self):
    if isinstance(self._raise_on_commit, IntegrityError):
      raise self._raise_on_commit

  def rollback(self):
    return None


def test_create_query_variants():
  assert import_configs.create_query(None, True, 1) == {
      'config': 1,
      'recurrent': 1
  }
  assert import_configs.create_query('tag', False, 2) == {
      'config': 2,
      'tag': 'tag'
  }
  assert import_configs.create_query('tag', True, 3) == {
      'config': 3,
      'tag': 'tag',
      'recurrent': 1
  }


def test_set_import_cfg_batches(monkeypatch):
  args = argparse.Namespace(batches='1,2,3', batch_list=None)
  import_configs.set_import_cfg_batches(args)
  assert args.batch_list == [1, 2, 3]
  args = argparse.Namespace(batches=None, batch_list=None)
  import_configs.set_import_cfg_batches(args)
  assert args.batch_list == []


def test_process_config_line_tag_only(monkeypatch):
  driver = MagicMock()
  args = argparse.Namespace(tag_only=True)
  counts = {}
  dbt = MagicMock()
  logger = MagicMock()
  monkeypatch.setattr(import_configs, 'tag_config_v2', lambda *_, **__: True)
  result = import_configs.process_config_line_v2(driver, args, counts, dbt,
                                                 logger)
  assert result is False


def test_parse_line_batches(monkeypatch):
  called_batches = []

  class _Driver(MagicMock):
    batchsize = None

  def _process(driver, args, counts, dbt, logger):
    called_batches.append(driver.batchsize)
    return True

  monkeypatch.setattr(import_configs, 'DriverConvolution', _Driver)
  monkeypatch.setattr(import_configs, 'process_config_line_v2', _process)
  args = argparse.Namespace(config_type=ConfigType.convolution,
                            command=None,
                            batch_list=[2, 4],
                            tag_only=False)
  import_configs.parse_line(args, 'cmd', {}, MagicMock(), MagicMock())
  assert called_batches == [2, 4]


def test_add_model_integrity_error(monkeypatch):
  fake_session = _FakeSession(raise_on_commit=IntegrityError('dup'))
  monkeypatch.setattr(import_configs, 'DbSession', lambda: fake_session)
  args = argparse.Namespace(add_model='m', md_version=1)
  logger = MagicMock()
  assert import_configs.add_model(args, logger) is False


def test_get_database_id_not_found(monkeypatch):
  fake_session = _FakeSession(query_result=NoResultFound())
  monkeypatch.setattr(import_configs, 'DbSession', lambda: fake_session)
  dbt = MagicMock()
  logger = MagicMock()
  mid, fid = import_configs.get_database_id('fw', 1, 'model', 1.0, dbt, logger)
  assert mid == -1 and fid == -1


@pytest.mark.parametrize("mid,fid", [(None, 1), (1, None)])
def test_add_benchmark_missing_ids(monkeypatch, mid, fid):
  monkeypatch.setattr(import_configs, 'get_database_id',
                      lambda *_args, **_kwargs: (mid, fid))
  args = argparse.Namespace(framework='fw',
                            fw_version=1,
                            model='m',
                            md_version=1.0,
                            config_type=ConfigType.convolution,
                            driver='cmd',
                            file_name=None,
                            add_model=False,
                            add_framework=False,
                            add_benchmark=True,
                            gpu_count=1)
  dbt = MagicMock()
  logger = MagicMock()
  assert import_configs.add_benchmark(args, dbt, logger) is False


def test_check_import_benchmark_args_raises():
  args = argparse.Namespace(add_model=True,
                            md_version=None,
                            add_benchmark=True,
                            model=None,
                            framework=None,
                            gpu_count=None,
                            md_version2=None,
                            fw_version=None,
                            driver=None,
                            file_name=None)
  with pytest.raises(ValueError):
    import_configs.check_import_benchmark_args(args)


def test_run_import_configs_flag_paths(monkeypatch):
  args = argparse.Namespace(config_type=ConfigType.convolution,
                            print_models=True,
                            add_model=False,
                            add_framework=False,
                            add_benchmark=False,
                            batches=None,
                            batch_list=[],
                            tag=None,
                            tag_only=False,
                            file_name=None,
                            mark_recurrent=False)
  logger = MagicMock()
  monkeypatch.setattr(import_configs, 'MIOpenDBTables', MagicMock())
  monkeypatch.setattr(import_configs, 'check_import_benchmark_args',
                      lambda *_: None)
  called = {}
  monkeypatch.setattr(import_configs, 'print_models',
                      lambda *_: called.setdefault('print', True))
  assert import_configs.run_import_configs(args, logger) is True

  # cover add_model and add_framework branch
  args.print_models = False
  args.add_model = True
  args.add_framework = True
  monkeypatch.setattr(import_configs, 'add_model',
                      lambda *_: called.setdefault('model', True))
  monkeypatch.setattr(import_configs, 'add_frameworks',
                      lambda *_: called.setdefault('framework', True))
  assert import_configs.run_import_configs(args, logger) is True

  # cover add_benchmark branch
  args.add_model = False
  args.add_framework = False
  args.add_benchmark = True
  monkeypatch.setattr(import_configs, 'add_benchmark',
                      lambda *_: called.setdefault('benchmark', True))
  assert import_configs.run_import_configs(args, logger) is True

  # fall through to import_cfgs path
  args.add_benchmark = False
  args.print_models = False
  args.batches = '8,16'
  monkeypatch.setattr(
      import_configs, 'import_cfgs', lambda *_args, **_kwargs: {
          'cnt_configs': 0,
          'cnt_tagged_configs': set()
      })
  assert import_configs.run_import_configs(args, logger) is True
