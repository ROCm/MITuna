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
"""Additional FinClass behavioral tests (branches and error paths)"""

import json
import os
import queue
from io import StringIO
from unittest.mock import Mock, patch

import paramiko
import pytest

from tuna.miopen.worker.fin_class import FinClass
from tuna.miopen.utils.config_type import ConfigType
from tuna.miopen.db.tables import MIOpenDBTables
from tuna.machine import Machine


@pytest.fixture
def mock_machine():
  machine = Mock(spec=Machine)
  machine.hostname = 'test-machine'
  machine.local_machine = True
  machine.port = 22
  machine.user = 'test_user'
  machine.password = 'test_pass'
  machine.id = 42
  machine.arch = 'gfx908'
  return machine


@pytest.fixture
def mock_dbt():
  dbt = Mock(spec=MIOpenDBTables)
  session = Mock()
  session.id = 1
  session.arch = 'gfx908'
  session.num_cu = 120
  session.rocm_v = 'expected_hash'
  session.miopen_v = 'expected_hash'
  dbt.session = session

  # Minimal table mocks with column name access
  def mk_cols(names):
    cols = []
    for n in names:
      c = Mock()
      c.name = n
      cols.append(c)
    return cols

  config_table = Mock()
  config_table.c = mk_cols(['id'])
  config_table.relationships = {}
  dbt.config_table = config_table

  find_db_table = Mock()
  find_db_table.c = mk_cols(['id', 'insert_ts', 'update_ts'])
  dbt.find_db_table = find_db_table

  tuning_data_table = Mock()
  tuning_data_table.c = mk_cols(['id', 'insert_ts', 'update_ts'])
  dbt.tuning_data_table = tuning_data_table

  job_table = Mock()
  job_table.__tablename__ = 'conv_job'
  job_table.c = mk_cols(['id', 'config', 'solver', 'insert_ts', 'update_ts'])
  dbt.job_table = job_table

  # Needed for __parse_applicability label filter
  config_tags_table = Mock()
  config_tags_table.config = 'config'
  dbt.config_tags_table = config_tags_table

  # Minimal solver table factory used in __add_new_solvers
  class _DummySolverTable:

    def __init__(self, **kwargs):
      for k, v in kwargs.items():
        setattr(self, k, v)

  dbt.solver_table = _DummySolverTable

  solver_app = Mock()
  solver_app.__tablename__ = 'conv_solver_applicability'
  solver_app.id = 1
  solver_app.applicable = 1
  dbt.solver_app = solver_app

  return dbt


@pytest.fixture(autouse=True)
def common_patches(mock_dbt, mock_machine):
  with patch('tuna.miopen.db.tables.MIOpenDBTables', return_value=mock_dbt):
    with patch('tuna.worker_interface.inspect') as mock_wi_inspect, \
         patch('tuna.miopen.worker.fin_class.inspect') as mock_fc_inspect, \
         patch('tuna.miopen.worker.fin_class.get_solver_ids', return_value={}), \
         patch('tuna.miopen.worker.fin_class.get_id_solvers', return_value=(True, {})), \
         patch('tuna.worker_interface.connect_db'), \
         patch('tuna.worker_interface.set_usr_logger') as mock_logger:
      mock_wi_inspect.side_effect = lambda x: x
      mock_fc_inspect.side_effect = lambda x: x
      mock_logger.return_value = Mock()
      mock_machine.connect.return_value = Mock()
      yield


def base_kwargs(mock_machine):
  from multiprocessing import Value, Lock, Queue
  return {
      'machine': mock_machine,
      'gpu_id': 0,
      'num_procs': Value('i', 2),
      'bar_lock': Lock(),
      'envmt': ["MIOPEN_LOG_LEVEL=7"],
      'reset_interval': False,
      'app_test': False,
      'label': 'cov_tests',
      'use_tuner': False,
      'job_queue': Queue(),
      'job_queue_lock': Lock(),
      'end_jobs': Value('i', 0),
      'fin_steps': ['not_fin'],
      'config_type': ConfigType.convolution,
      'session_id': 1,
      'find_mode': 1,
  }


def test_check_env_super_false_returns_false(mock_machine):
  with patch('tuna.miopen.worker.fin_class.WorkerInterface.check_env',
             return_value=False):
    worker = FinClass(**base_kwargs(mock_machine))
    assert worker.check_env() is False


def test_check_env_mismatch_raises(mock_machine):
  with patch('tuna.miopen.worker.fin_class.WorkerInterface.check_env',
             return_value=True):
    worker = FinClass(**base_kwargs(mock_machine))
    with patch.object(worker, 'get_miopen_v', return_value='different_hash'):
      with pytest.raises(ValueError):
        worker.check_env()


def test_chk_abort_file_paths(mock_machine, tmp_path):
  worker = FinClass(**base_kwargs(mock_machine))
  # Ensure no files => False
  assert worker.chk_abort_file() is False

  # Create one abort file => True
  p1 = f"/tmp/miopen_abort_{mock_machine.arch}"
  open(p1, 'a').close()
  try:
    assert worker.chk_abort_file() is True
  finally:
    os.remove(p1)

  # Create mid file => True
  p2 = f"/tmp/miopen_abort_mid_{mock_machine.id}"
  open(p2, 'a').close()
  try:
    assert worker.chk_abort_file() is True
  finally:
    os.remove(p2)


def test_compose_fincmd_local_and_remote_exceptions(mock_machine):
  # Local path
  worker = FinClass(**base_kwargs(mock_machine))
  mock_machine.local_machine = True
  cmd = worker._FinClass__compose_fincmd()
  assert '/opt/rocm/bin/fin' in cmd
  assert f"-i {worker.local_file}" in cmd
  assert f"-o {worker.local_output}" in cmd

  # Remote path with SSHException then IOError
  mock_machine.local_machine = False
  worker.machine = mock_machine
  sftp = Mock()
  sftp.put.side_effect = paramiko.ssh_exception.SSHException("ssh fail")
  ssh = Mock()
  ssh.open_sftp.return_value = sftp
  worker.cnx = Mock()
  worker.cnx.ssh = ssh
  cmd = worker._FinClass__compose_fincmd()
  assert '/opt/rocm/bin/fin' in cmd

  # Now IOError
  sftp.put.side_effect = IOError("io fail")
  cmd = worker._FinClass__compose_fincmd()
  assert '/opt/rocm/bin/fin' in cmd


def test_get_fin_results_raises_after_retries(mock_machine):
  worker = FinClass(**base_kwargs(mock_machine))
  with patch.object(worker, '_FinClass__prep_fin_input', return_value=True):
    err = StringIO('ERR')
    err.read = lambda: 'ERR'
    with patch.object(worker, 'exec_docker_cmd', return_value=(1, '', err)):
      with pytest.raises(ValueError):
        worker._FinClass__get_fin_results()


def test_compose_work_objs_appends_not_fin_when_no_steps(mock_machine):
  worker = FinClass(**base_kwargs(mock_machine))
  worker.fin_steps = []
  conds = []
  with patch('tuna.worker_interface.WorkerInterface.compose_work_objs',
             return_value=[]):
    worker.compose_work_objs(Mock(), conds)
  assert "fin_step='not_fin'" in conds


def test_compose_fincmd_remote_success_copy(mock_machine):
  worker = FinClass(**base_kwargs(mock_machine))
  mock_machine.local_machine = False
  worker.machine = mock_machine
  sftp = Mock()
  sftp.put.side_effect = None
  ssh = Mock()
  ssh.open_sftp.return_value = sftp
  worker.cnx = Mock()
  worker.cnx.ssh = ssh
  cmd = worker._FinClass__compose_fincmd()
  assert '/opt/rocm/bin/fin' in cmd


def test_get_solvers_none_returns_false(mock_machine):
  worker = FinClass(**base_kwargs(mock_machine))
  with patch.object(worker, '_FinClass__get_fin_results', return_value=None):
    assert worker.get_solvers() is False


def test_get_solvers_parses_when_present(mock_machine):
  worker = FinClass(**base_kwargs(mock_machine))
  fake = [
      None, {
          'all_solvers': [{
              'id': '1',
              'name': 'S',
              'tunable': '0',
              'type': 0,
              'dynamic': 0
          }]
      }
  ]
  with patch.object(worker, '_FinClass__get_fin_results', return_value=fake), \
       patch.object(worker, '_FinClass__parse_solvers', return_value=True) as p:
    assert worker.get_solvers() is True
    p.assert_called_once()


def test_parse_out_local_bad_json_returns_none(mock_machine, tmp_path):
  worker = FinClass(**base_kwargs(mock_machine))
  with open(worker.local_output, 'w') as f:
    f.write('{not json')
  assert worker._FinClass__parse_out() is None


def test_set_all_configs_success_batch_norm_and_blocks(mock_machine):
  worker = FinClass(**base_kwargs(mock_machine))
  worker.config_type = ConfigType.batch_norm

  class Row:

    def __init__(self, i):
      self.id = i

    def get_direction(self):
      return 2

  rows = [Row(1), Row(2), Row(3)]
  q = Mock()
  q.all.return_value = rows
  with patch.object(worker, 'query_cfgs', return_value=q), \
       patch('tuna.miopen.worker.fin_class.compose_config_obj', return_value={'id': 1, 'direction': 1}):
    assert worker._FinClass__set_all_configs(idx=0, num_blk=2) is True
    assert isinstance(worker.all_configs, list)


def test_set_all_configs_queue_empty_exception(mock_machine):
  worker = FinClass(**base_kwargs(mock_machine))
  with patch.object(worker, 'query_cfgs') as q:
    q.all.return_value = []
    # simulate Empty immediately
    worker.job_queue.get = Mock(side_effect=queue.Empty)
    assert worker._FinClass__set_all_configs(idx=1, num_blk=1) is False


def test_prep_fin_input_default_outfile(mock_machine):
  worker = FinClass(**base_kwargs(mock_machine))
  with patch.object(worker, '_FinClass__create_dumplist', return_value=True), \
       patch.object(worker, '_FinClass__dump_json', return_value=True):
    assert worker._FinClass__prep_fin_input(outfile=None, to_file=True)


def test_insert_applicability_builds_queries(mock_machine):
  worker = FinClass(**base_kwargs(mock_machine))
  worker.solver_id_map = {'A': 26}
  json_in = [{"input": {"config_tuna_id": 7}, "applicable_solvers": ['A']}]
  session = Mock()
  session.execute = Mock()
  session.commit = Mock()
  assert worker._FinClass__insert_applicability(session, json_in) is True
  assert session.execute.call_count >= 2


def test_parse_applicability_flow(mock_machine):
  worker = FinClass(**base_kwargs(mock_machine))
  worker.label = 'taggy'
  packs = [[{"input": {"config_tuna_id": 7}, "applicable_solvers": []}], []]
  with patch('tuna.miopen.worker.fin_class.split_packets', return_value=packs), \
       patch('tuna.miopen.worker.fin_class.session_retry', side_effect=lambda s, fn, cb, lg: fn) as _sr:
    # Dummy session and query chain
    class Q:

      def filter(self, *a, **k):
        return self

      def group_by(self, *a, **k):
        return self

      def all(self):
        return []

    class DS:

      def __enter__(self):
        self.q = Q()
        self._s = Mock()
        self._s.query = Mock(return_value=self.q)
        self._s.execute = Mock()
        self._s.commit = Mock()
        return self._s

      def __exit__(self, *a):
        return False

    with patch('tuna.miopen.worker.fin_class.DbSession', DS):
      assert worker._FinClass__parse_applicability(packs[0]) is True


def test_add_new_solvers_invalid_request_error(mock_machine):
  from sqlalchemy.exc import InvalidRequestError
  worker = FinClass(**base_kwargs(mock_machine))
  solvers = [{'id': '1', 'name': 'X', 'tunable': '0', 'type': 0, 'dynamic': 0}]

  class DS2:

    def __enter__(self):
      s = Mock()
      s.add.side_effect = InvalidRequestError('bad')
      s.commit = Mock()
      return s

    def __exit__(self, *a):
      return False

  with patch('tuna.miopen.worker.fin_class.DbSession', DS2):
    max_id, sids = worker._FinClass__add_new_solvers(solvers)
    assert max_id >= 1 and 1 in sids


def test_populate_kernels_sets_fields():
  kern = {
      'kernel_file': 'f',
      'comp_options': 'opts',
      'blob': 'abc',
      'md5_sum': 'h',
      'uncompressed_size': 9
  }

  class K:
    pass

  k = K()
  res = FinClass.populate_kernels(kern, k)
  assert res.kernel_name == 'f'
  assert res.kernel_args == 'opts'
  assert res.kernel_blob == b'abc'
  assert res.kernel_hash == 'h'
  assert res.uncompressed_size == 9


def test_parse_out_remote_bad_json_returns_none(mock_machine):
  worker = FinClass(**base_kwargs(mock_machine))
  worker.machine.local_machine = False
  worker.exec_command = Mock(return_value=(0, ['{not valid json'], None))
  assert worker._FinClass__parse_out() is None


def test_parse_out_local_success(mock_machine, tmp_path):
  worker = FinClass(**base_kwargs(mock_machine))
  data = [{"ok": True}]
  with open(worker.local_output, 'w') as f:
    json.dump(data, f)
  assert worker._FinClass__parse_out() == data


def test_applicability_returns_false_on_none(mock_machine):
  worker = FinClass(**base_kwargs(mock_machine))
  with patch.object(worker, '_FinClass__get_fin_results', return_value=None):
    assert worker.applicability() is False


def test_applicability_true_when_results_present(mock_machine):
  worker = FinClass(**base_kwargs(mock_machine))
  with patch.object(worker,
                    '_FinClass__get_fin_results',
                    return_value=[{
                        "ok": True
                    }]):
    with patch.object(worker,
                      '_FinClass__parse_applicability',
                      return_value=True) as p:
      assert worker.applicability() is True
      p.assert_called_once()


def test_create_dumplist_variants(mock_machine):
  worker = FinClass(**base_kwargs(mock_machine))

  # get_solvers path
  worker.fin_steps = ['get_solvers']
  assert worker._FinClass__create_dumplist() is True
  assert worker.fin_list == [{"steps": ['get_solvers']}]

  # applicability path with failure in __set_all_configs
  worker.fin_steps = ['applicability']
  with patch.object(worker, '_FinClass__set_all_configs', return_value=False):
    assert worker._FinClass__create_dumplist() is False

  # unrecognized path
  worker.fin_steps = ['bogus']
  assert worker._FinClass__create_dumplist() is False


def test_dump_json_returns_string_when_not_file(mock_machine):
  worker = FinClass(**base_kwargs(mock_machine))
  worker.fin_list = [{"a": 1}]
  out = worker._FinClass__dump_json('ignored', to_file=False)
  assert out == json.dumps(worker.fin_list)


def test_prep_fin_input_true_and_false(mock_machine):
  worker = FinClass(**base_kwargs(mock_machine))
  with patch.object(worker, '_FinClass__create_dumplist', return_value=True), \
       patch.object(worker, '_FinClass__dump_json', return_value=True):
    assert worker._FinClass__prep_fin_input(outfile="/tmp/fin_input.json",
                                            to_file=True)

  with patch.object(worker, '_FinClass__create_dumplist', return_value=False):
    assert worker._FinClass__prep_fin_input(outfile="/tmp/fin_input.json",
                                            to_file=True) is False


def test_run_fin_cmd_failure_result_format(mock_machine):
  worker = FinClass(**base_kwargs(mock_machine))
  mock_machine.make_temp_file.return_value = '/tmp/fin_out.json'
  # FinClass relies on get_fin_input from builder/eval; stub it here
  worker.get_fin_input = lambda: '/tmp/fin_in.json'
  with patch('tuna.worker_interface.WorkerInterface.run_command',
             return_value=(1, 'error%bad:msg')):
    res = worker.run_fin_cmd()
    assert res['success'] is False
    assert 'result' in res


def test_init_check_env_success_and_failure(mock_machine):
  worker = FinClass(**base_kwargs(mock_machine))

  # Failure on first pass
  with patch.object(worker, 'check_env',
                    side_effect=ValueError('mismatch')) as chk:
    assert worker.init_check_env() is False
    assert chk.call_count == 1

  # Second call should not call check_env
  with patch.object(worker, 'check_env', return_value=True) as chk2:
    assert worker.init_check_env() is True
    assert chk2.call_count == 0


def test_step_calls_applicability_when_requested(mock_machine):
  worker = FinClass(**base_kwargs(mock_machine))
  worker.fin_steps = ['applicability']
  with patch.object(worker, 'applicability', return_value=None) as app:
    ret = worker.step()
    assert ret is False
    app.assert_called_once()
    assert worker.multiproc is False
