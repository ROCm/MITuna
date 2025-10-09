#!/usr/bin/env python3
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
"""Tests for MIOpen class in miopen_lib.py"""

import sys
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from tuna.miopen.miopen_lib import MIOpen, MAX_ERRORED_JOB_RETRIES
from tuna.miopen.utils.config_type import ConfigType
from tuna.utils.utility import SimpleDict
from tuna.libraries import Library, Operation
from tuna.custom_errors import CustomError


# ============================================================================
# Fixtures
# ============================================================================
@pytest.fixture
def miopen_instance():
  """Create a MIOpen instance for testing."""
  with patch('tuna.miopen.miopen_lib.DbSession'):
    miopen = MIOpen()
    return miopen


@pytest.fixture
def mock_args():
  """Create mock arguments."""
  args = Mock()
  args.config_type = ConfigType.convolution
  args.session_id = 123
  args.arch = 'gfx90a'
  args.num_cu = 110
  args.version = '1.0.0'
  args.machines = None
  args.remote_machine = None
  args.label = 'test_label'
  args.restart_machine = False
  args.docker_name = 'test_docker'
  args.shutdown_workers = False
  args.enqueue_only = False
  args.find_mode = 1
  args.ticket = None
  args.solver_id = None
  args.dynamic_solvers_only = False
  args.blacklist = None
  args.reset_interval = None
  args.gpu_lim = None
  args.rich_data = False
  args.subcommand = None
  args.add_tables = False
  args.init_session = False
  args.fin_steps = None
  args.list_solvers = False
  args.update_solvers = False
  args.update_applicability = False
  args.check_status = False
  args.execute_cmd = None
  return args


# ============================================================================
# Test MIOpen Initialization
# ============================================================================
class TestMIOpenInitialization:
  """Test MIOpen class initialization."""

  def test_initialization(self):
    """Test MIOpen initializes correctly."""
    with patch('tuna.miopen.miopen_lib.DbSession'):
      miopen = MIOpen()
      assert miopen.args is None
      assert miopen.set_state is None
      # Library is stored in parent class, check via __dict__ or inheritance
      assert hasattr(miopen, '_library')
      assert miopen._library == Library.MIOPEN

  def test_inherits_from_mituna_interface(self):
    """Test that MIOpen inherits from MITunaInterface."""
    with patch('tuna.miopen.miopen_lib.DbSession'):
      miopen = MIOpen()
      assert hasattr(miopen, 'parse_args')
      assert hasattr(miopen, 'run')


# ============================================================================
# Test parse_args Method
# ============================================================================
class TestParseArgs:
  """Test argument parsing in MIOpen."""

  @patch('tuna.miopen.miopen_lib.setup_arg_parser')
  @patch('tuna.miopen.miopen_lib.args_check')
  @patch('tuna.miopen.miopen_lib.MIOpenDBTables')
  @patch('sys.argv', ['prog', '--find_mode', '1', '--session_id', '123'])
  def test_parse_args_basic(self, mock_dbtables, mock_args_check,
                            mock_setup_parser, miopen_instance):
    """Test basic argument parsing."""
    mock_parser = Mock()
    mock_parser.parse_args.return_value = Mock(
        config_type=ConfigType.convolution,
        session_id=123,
        subcommand=None,
        list_solvers=False,
        fin_steps=None,
        find_mode=1,
        blacklist=None,
        check_status=False,
        restart_machine=False,
        execute_cmd=None,
        update_applicability=False)
    mock_setup_parser.return_value = mock_parser

    miopen_instance.parse_args()

    assert miopen_instance.args is not None
    assert miopen_instance.args.config_type == ConfigType.convolution
    mock_dbtables.assert_called_once()

  @patch('tuna.miopen.miopen_lib.setup_arg_parser')
  @patch('tuna.miopen.miopen_lib.print_solvers')
  @patch('sys.argv', ['prog', '--list_solvers'])
  def test_parse_args_list_solvers(self, mock_print_solvers, mock_setup_parser,
                                   miopen_instance):
    """Test --list_solvers exits after printing."""
    mock_parser = Mock()
    mock_parser.parse_args.return_value = Mock(
        config_type=ConfigType.convolution,
        session_id=123,
        subcommand=None,
        list_solvers=True,
        fin_steps=None,
        find_mode=1,
        blacklist=None,
        update_applicability=False)
    mock_setup_parser.return_value = mock_parser

    with pytest.raises(CustomError, match='Printing solvers'):
      miopen_instance.parse_args()

    mock_print_solvers.assert_called_once()

  @patch('tuna.miopen.miopen_lib.setup_arg_parser')
  @patch('tuna.miopen.miopen_lib.MIOpenDBTables')
  @patch('tuna.miopen.miopen_lib.args_check')
  @patch('sys.argv', ['prog', '--find_mode', '1'])
  def test_parse_args_default_config_type(self, mock_args_check, mock_dbtables,
                                          mock_setup_parser, miopen_instance):
    """Test default config_type is set to convolution."""
    mock_parser = Mock()
    mock_parser.parse_args.return_value = Mock(config_type=None,
                                               session_id=None,
                                               subcommand=None,
                                               list_solvers=False,
                                               fin_steps=None,
                                               find_mode=1,
                                               blacklist=None,
                                               check_status=False,
                                               restart_machine=False,
                                               execute_cmd=None,
                                               update_applicability=False,
                                               machines=None)
    mock_setup_parser.return_value = mock_parser

    miopen_instance.parse_args()

    assert miopen_instance.args.config_type == ConfigType.convolution


# ============================================================================
# Test check_blacklist Method
# ============================================================================
class TestCheckBlacklist:
  """Test blacklist validation."""

  def test_check_blacklist_valid(self, miopen_instance, mock_args):
    """Test valid blacklist values."""
    mock_parser = Mock()
    mock_args.blacklist = 'miopenConvolutionAlgoGEMM,miopenConvolutionAlgoDirect'
    miopen_instance.args = mock_args

    # Should not raise
    miopen_instance.check_blacklist(mock_parser)

    assert miopen_instance.args.blacklist == [
        'miopenConvolutionAlgoGEMM', 'miopenConvolutionAlgoDirect'
    ]

  def test_check_blacklist_invalid(self, miopen_instance, mock_args):
    """Test invalid blacklist values."""
    mock_parser = Mock()
    mock_args.blacklist = 'invalid_algo'
    miopen_instance.args = mock_args

    miopen_instance.check_blacklist(mock_parser)

    mock_parser.error.assert_called_once_with("Incorrect blacklist value")


# ============================================================================
# Test check_fin_args Method
# ============================================================================
class TestCheckFinArgs:
  """Test fin_steps validation."""

  def test_check_fin_args_valid_single(self, miopen_instance, mock_args):
    """Test valid single fin_step."""
    mock_parser = Mock()
    mock_args.fin_steps = 'miopen_find_compile'
    miopen_instance.args = mock_args

    miopen_instance.check_fin_args(mock_parser)

    assert miopen_instance.args.fin_steps == ['miopen_find_compile']
    mock_parser.error.assert_not_called()

  def test_check_fin_args_multiple_not_supported(self, miopen_instance,
                                                 mock_args):
    """Test multiple fin_steps not supported."""
    mock_parser = Mock()
    # Make parser.error raise SystemExit like the real parser would
    mock_parser.error.side_effect = SystemExit(2)
    mock_args.fin_steps = 'miopen_find_compile,miopen_find_eval'
    miopen_instance.args = mock_args

    with pytest.raises(SystemExit):
      miopen_instance.check_fin_args(mock_parser)

    mock_parser.error.assert_called_once_with(
        'Multiple fin_steps currently not supported')

  def test_check_fin_args_invalid_step(self, miopen_instance, mock_args):
    """Test invalid fin_step."""
    mock_parser = Mock()
    mock_args.fin_steps = 'invalid_step'
    miopen_instance.args = mock_args

    miopen_instance.check_fin_args(mock_parser)

    assert mock_parser.error.called
    call_args = mock_parser.error.call_args[0][0]
    assert 'Supported fin steps are' in call_args


# ============================================================================
# Test add_tables Method
# ============================================================================
class TestAddTables:
  """Test database table creation."""

  @patch('tuna.miopen.miopen_lib.recreate_triggers')
  @patch('tuna.miopen.miopen_lib.get_miopen_triggers')
  @patch('tuna.miopen.miopen_lib.drop_miopen_triggers')
  @patch('tuna.miopen.miopen_lib.create_tables')
  @patch('tuna.miopen.miopen_lib.get_miopen_tables')
  def test_add_tables_success(self, mock_get_tables, mock_create_tables,
                              mock_drop_triggers, mock_get_triggers,
                              mock_recreate_triggers, miopen_instance):
    """Test successful table creation."""
    mock_get_tables.return_value = ['table1', 'table2']
    mock_create_tables.return_value = True
    mock_drop_triggers.return_value = ['drop1']
    mock_get_triggers.return_value = ['trigger1']

    result = miopen_instance.add_tables()

    assert result is True
    mock_get_tables.assert_called_once()
    mock_create_tables.assert_called_once_with(['table1', 'table2'])
    mock_recreate_triggers.assert_called_once_with(['drop1'], ['trigger1'])


# ============================================================================
# Test run Method
# ============================================================================
class TestRun:
  """Test main run method."""

  @patch('tuna.miopen.miopen_lib.load_machines')
  def test_run_no_args_parses(self, mock_load_machines, miopen_instance,
                              mock_args):
    """Test run() calls parse_args if args is None."""
    miopen_instance.args = None
    mock_args.add_tables = False
    mock_args.subcommand = None
    mock_load_machines.return_value = []

    with patch.object(miopen_instance, 'parse_args') as mock_parse:
      # Make parse_args set self.args when called
      def set_args():
        miopen_instance.args = mock_args

      mock_parse.side_effect = set_args

      with patch.object(miopen_instance, 'compose_worker_list',
                        return_value=[]):
        miopen_instance.run()

        mock_parse.assert_called_once()

  @patch('tuna.miopen.miopen_lib.run_import_configs')
  def test_run_import_configs_subcommand(self, mock_run_import, miopen_instance,
                                         mock_args):
    """Test run() with import_configs subcommand."""
    mock_args.subcommand = 'import_configs'
    mock_args.import_configs = Mock()
    miopen_instance.args = mock_args
    miopen_instance.logger = Mock()

    result = miopen_instance.run()

    assert result is None
    mock_run_import.assert_called_once_with(mock_args.import_configs,
                                            miopen_instance.logger)

  @patch('tuna.miopen.miopen_lib.run_load_job')
  def test_run_load_job_subcommand(self, mock_run_load_job, miopen_instance,
                                   mock_args):
    """Test run() with load_job subcommand."""
    mock_args.subcommand = 'load_job'
    mock_args.load_job = Mock()
    miopen_instance.args = mock_args
    miopen_instance.logger = Mock()

    result = miopen_instance.run()

    assert result is None
    mock_run_load_job.assert_called_once_with(mock_args.load_job,
                                              miopen_instance.logger)

  @patch('tuna.miopen.miopen_lib.run_export_db')
  def test_run_export_db_subcommand(self, mock_run_export, miopen_instance,
                                    mock_args):
    """Test run() with export_db subcommand."""
    mock_args.subcommand = 'export_db'
    mock_args.export_db = Mock()
    miopen_instance.args = mock_args
    miopen_instance.logger = Mock()

    result = miopen_instance.run()

    assert result is None
    mock_run_export.assert_called_once_with(mock_args.export_db,
                                            miopen_instance.logger)

  @patch('tuna.miopen.miopen_lib.run_update_golden')
  def test_run_update_golden_subcommand(self, mock_run_update, miopen_instance,
                                        mock_args):
    """Test run() with update_golden subcommand."""
    mock_args.subcommand = 'update_golden'
    mock_args.update_golden = Mock()
    miopen_instance.args = mock_args
    miopen_instance.logger = Mock()

    result = miopen_instance.run()

    assert result is None
    mock_run_update.assert_called_once_with(mock_args.update_golden,
                                            miopen_instance.logger)

  def test_run_add_tables(self, miopen_instance, mock_args):
    """Test run() with add_tables flag."""
    mock_args.add_tables = True
    miopen_instance.args = mock_args

    with patch.object(miopen_instance, 'add_tables', return_value=True):
      result = miopen_instance.run()

      assert result is None

  @patch('tuna.miopen.miopen_lib.load_machines')
  def test_run_compose_workers(self, mock_load_machines, miopen_instance,
                               mock_args):
    """Test run() composes worker list."""
    mock_args.add_tables = False
    mock_args.subcommand = None
    miopen_instance.args = mock_args

    mock_machines = [Mock(), Mock()]
    mock_load_machines.return_value = mock_machines
    mock_workers = [Mock(), Mock()]

    with patch.object(miopen_instance,
                      'compose_worker_list',
                      return_value=mock_workers):
      result = miopen_instance.run()

      assert result == mock_workers
      mock_load_machines.assert_called_once_with(mock_args)


# ============================================================================
# Test get_envmt Method
# ============================================================================
class TestGetEnvmt:
  """Test environment variable construction."""

  def test_get_envmt_basic(self, miopen_instance, mock_args):
    """Test basic environment variables."""
    mock_args.find_mode = None
    mock_args.blacklist = None
    miopen_instance.args = mock_args

    envmt = miopen_instance.get_envmt()

    assert "MIOPEN_LOG_LEVEL=4" in envmt
    assert "MIOPEN_SQLITE_KERN_CACHE=ON" in envmt
    assert "MIOPEN_DEBUG_IMPLICIT_GEMM_FIND_ALL_SOLUTIONS=1" in envmt

  def test_get_envmt_with_find_mode(self, miopen_instance, mock_args):
    """Test environment with find_mode."""
    mock_args.find_mode = 1
    mock_args.blacklist = None
    miopen_instance.args = mock_args

    envmt = miopen_instance.get_envmt()

    assert "MIOPEN_FIND_MODE=1" in envmt

  def test_get_envmt_with_blacklist(self, miopen_instance, mock_args):
    """Test environment with blacklist."""
    mock_args.find_mode = None
    mock_args.blacklist = ['miopenConvolutionAlgoGEMM']
    miopen_instance.args = mock_args

    envmt = miopen_instance.get_envmt()

    assert "miopenConvolutionAlgoGEMM=0" in envmt

  def test_get_envmt_multiple_blacklist(self, miopen_instance, mock_args):
    """Test environment with multiple blacklist entries."""
    mock_args.find_mode = 1
    mock_args.blacklist = [
        'miopenConvolutionAlgoGEMM', 'miopenConvolutionAlgoDirect'
    ]
    miopen_instance.args = mock_args

    envmt = miopen_instance.get_envmt()

    assert "MIOPEN_FIND_MODE=1" in envmt
    assert "miopenConvolutionAlgoGEMM=0" in envmt
    # Second item has leading space due to join/split behavior
    assert " miopenConvolutionAlgoDirect=0" in envmt


# ============================================================================
# Test get_kwargs Method
# ============================================================================
class TestGetKwargs:
  """Test kwargs construction for workers."""

  def test_get_kwargs_basic(self, miopen_instance, mock_args):
    """Test basic kwargs construction."""
    mock_args.fin_steps = ['miopen_find_compile']
    mock_args.dynamic_solvers_only = False
    mock_args.config_type = ConfigType.convolution
    mock_args.reset_interval = None
    miopen_instance.args = mock_args

    gpu_idx = 0
    f_vals = {'machine': Mock(), 'b_first': True}

    with patch.object(miopen_instance.__class__.__bases__[0],
                      'get_kwargs',
                      return_value={'base': 'kwargs'}):
      kwargs = miopen_instance.get_kwargs(gpu_idx, f_vals, tuning=False)

      assert kwargs['fin_steps'] == ['miopen_find_compile']
      assert kwargs['dynamic_solvers_only'] is False
      assert kwargs['config_type'] == ConfigType.convolution
      assert kwargs['reset_interval'] is None

  def test_get_kwargs_with_tuning(self, miopen_instance, mock_args):
    """Test kwargs with tuning flag."""
    mock_args.fin_steps = ['miopen_perf_eval']
    mock_args.dynamic_solvers_only = True
    mock_args.config_type = ConfigType.batch_norm
    mock_args.reset_interval = 24
    miopen_instance.args = mock_args

    gpu_idx = 1
    f_vals = {'machine': Mock(), 'b_first': False}

    with patch.object(miopen_instance.__class__.__bases__[0],
                      'get_kwargs',
                      return_value={'base': 'kwargs'}):
      kwargs = miopen_instance.get_kwargs(gpu_idx, f_vals, tuning=True)

      assert kwargs['fin_steps'] == ['miopen_perf_eval']
      assert kwargs['dynamic_solvers_only'] is True
      assert kwargs['config_type'] == ConfigType.batch_norm
      assert kwargs['reset_interval'] == 24


# ============================================================================
# Test update_operation Method
# ============================================================================
class TestUpdateOperation:
  """Test operation type updates."""

  def test_update_operation_find_compile(self, miopen_instance, mock_args):
    """Test update_operation with find_compile."""
    mock_args.fin_steps = ['miopen_find_compile']
    mock_args.update_applicability = False
    miopen_instance.args = mock_args
    miopen_instance.fetch_state = set()

    miopen_instance.update_operation()

    assert 'new' in miopen_instance.fetch_state
    assert miopen_instance.set_state == 'compile_start'
    assert miopen_instance.operation == Operation.COMPILE

  def test_update_operation_find_eval(self, miopen_instance, mock_args):
    """Test update_operation with find_eval."""
    mock_args.fin_steps = ['miopen_find_eval']
    mock_args.update_applicability = False
    miopen_instance.args = mock_args
    miopen_instance.fetch_state = set()

    miopen_instance.update_operation()

    assert 'new' in miopen_instance.fetch_state
    assert 'compiled' in miopen_instance.fetch_state
    assert miopen_instance.set_state == 'eval_start'
    assert miopen_instance.operation == Operation.EVAL

  def test_update_operation_perf_compile(self, miopen_instance, mock_args):
    """Test update_operation with perf_compile."""
    mock_args.fin_steps = ['miopen_perf_compile']
    mock_args.update_applicability = False
    miopen_instance.args = mock_args
    miopen_instance.fetch_state = set()

    miopen_instance.update_operation()

    assert 'new' in miopen_instance.fetch_state
    assert miopen_instance.set_state == 'compile_start'
    assert miopen_instance.operation == Operation.COMPILE

  def test_update_operation_applicability(self, miopen_instance, mock_args):
    """Test update_operation with update_applicability."""
    mock_args.fin_steps = None
    mock_args.update_applicability = True
    miopen_instance.args = mock_args
    miopen_instance.fetch_state = set()

    miopen_instance.update_operation()

    assert 'new' in miopen_instance.fetch_state


# ============================================================================
# Test has_tunable_operation Method
# ============================================================================
class TestHasTunableOperation:
  """Test tunable operation checks."""

  def test_has_tunable_operation_with_load_job(self, miopen_instance,
                                               mock_args):
    """Test has_tunable_operation returns False for load_job."""
    mock_args.subcommand = 'load_job'
    mock_args.shutdown_workers = False
    mock_args.fin_steps = None
    miopen_instance.args = mock_args

    result = miopen_instance.has_tunable_operation()

    assert result is False

  def test_has_tunable_operation_with_shutdown(self, miopen_instance,
                                               mock_args):
    """Test has_tunable_operation returns True for shutdown."""
    mock_args.subcommand = None
    mock_args.shutdown_workers = True
    mock_args.fin_steps = None
    miopen_instance.args = mock_args

    result = miopen_instance.has_tunable_operation()

    assert result is True

  def test_has_tunable_operation_with_celery_steps(self, miopen_instance,
                                                   mock_args):
    """Test has_tunable_operation with celery steps."""
    mock_args.subcommand = None
    mock_args.shutdown_workers = False
    mock_args.fin_steps = ['miopen_find_compile']
    miopen_instance.args = mock_args

    result = miopen_instance.has_tunable_operation()

    assert result is True


# ============================================================================
# Test get_fdb_attr and get_tuning_data_attr Methods
# ============================================================================
class TestTableAttributes:
  """Test table attribute getters."""

  def test_get_fdb_attr(self, miopen_instance):
    """Test get_fdb_attr returns correct attributes."""
    mock_dbt = Mock()
    mock_column1 = Mock()
    mock_column1.name = 'id'
    mock_column2 = Mock()
    mock_column2.name = 'config'
    mock_column3 = Mock()
    mock_column3.name = 'insert_ts'
    mock_column4 = Mock()
    mock_column4.name = 'update_ts'

    mock_dbt.find_db_table = Mock()
    with patch('tuna.miopen.miopen_lib.inspect') as mock_inspect:
      mock_inspect.return_value.c = [
          mock_column1, mock_column2, mock_column3, mock_column4
      ]
      miopen_instance.dbt = mock_dbt

      result = miopen_instance.get_fdb_attr()

      assert 'id' in result
      assert 'config' in result
      assert 'insert_ts' not in result
      assert 'update_ts' not in result

  def test_get_tuning_data_attr(self, miopen_instance):
    """Test get_tuning_data_attr returns correct attributes."""
    mock_dbt = Mock()
    mock_column1 = Mock()
    mock_column1.name = 'id'
    mock_column2 = Mock()
    mock_column2.name = 'params'
    mock_column3 = Mock()
    mock_column3.name = 'insert_ts'
    mock_column4 = Mock()
    mock_column4.name = 'update_ts'

    mock_dbt.tuning_data_table = Mock()
    with patch('tuna.miopen.miopen_lib.inspect') as mock_inspect:
      mock_inspect.return_value.c = [
          mock_column1, mock_column2, mock_column3, mock_column4
      ]
      miopen_instance.dbt = mock_dbt

      result = miopen_instance.get_tuning_data_attr()

      assert 'id' in result
      assert 'params' in result
      assert 'insert_ts' not in result
      assert 'update_ts' not in result


# ============================================================================
# Test serialize_jobs and build_context Methods
# ============================================================================
class TestJobSerialization:
  """Test job serialization and context building."""

  @patch('tuna.miopen.miopen_lib.serialize_chunk')
  def test_serialize_jobs(self, mock_serialize, miopen_instance):
    """Test serialize_jobs calls appropriate methods."""
    mock_session = Mock()
    batch_jobs = [Mock(config=1), Mock(config=2)]
    miopen_instance.dbt = Mock()

    with patch.object(miopen_instance,
                      'compose_work_objs_fin',
                      return_value=['entry1', 'entry2']):
      mock_serialize.return_value = 'serialized'

      result = miopen_instance.serialize_jobs(mock_session, batch_jobs)

      assert result == 'serialized'
      mock_serialize.assert_called_once_with(['entry1', 'entry2'])

  def test_build_context(self, miopen_instance, mock_args):
    """Test build_context creates correct context."""
    miopen_instance.args = mock_args
    miopen_instance.operation = Operation.COMPILE
    miopen_instance.dbt = Mock()
    miopen_instance.dbt.session.arch = 'gfx90a'
    miopen_instance.dbt.session.num_cu = 110

    job = SimpleDict(id=1, config=100)
    config = SimpleDict(id=100, in_channels=64)
    serialized_jobs = [(job, config)]

    with patch.object(miopen_instance,
                      'get_context_items',
                      return_value={'key': 'value'}):
      with patch.object(miopen_instance,
                        'get_fdb_attr',
                        return_value=['fdb_col1']):
        with patch.object(miopen_instance,
                          'get_tuning_data_attr',
                          return_value=['tuning_col1']):
          contexts = miopen_instance.build_context(serialized_jobs)

          assert len(contexts) == 1
          ctx = contexts[0]
          assert ctx['job'] == job
          assert ctx['config'] == config
          assert ctx['operation'] == Operation.COMPILE
          assert ctx['arch'] == 'gfx90a'
          assert ctx['num_cu'] == 110
          assert ctx['rich_data'] is False


# ============================================================================
# Test process_compile_results Method
# ============================================================================
class TestProcessCompileResults:
  """Test compile result processing."""

  @patch('tuna.miopen.miopen_lib.set_job_state')
  @patch('tuna.miopen.miopen_lib.get_fin_result')
  @patch('tuna.miopen.miopen_lib.process_fdb_w_kernels')
  @patch('tuna.miopen.miopen_lib.get_solver_ids')
  def test_process_compile_results_success(self, mock_get_solver_ids,
                                           mock_process_fdb, mock_get_result,
                                           mock_set_state, miopen_instance):
    """Test successful compile result processing."""
    mock_session = Mock()
    fin_json = {
        'success': True,
        'miopen_find_compile_result': {
            'solver': 'data'
        }
    }
    context = {'job': {'id': 1}, 'config': {'id': 100}, 'fdb_attr': ['col1']}

    miopen_instance.dbt = Mock()
    mock_get_solver_ids.return_value = {'solver1': 1}
    mock_process_fdb.return_value = [{'success': True}]
    mock_get_result.return_value = (True, 'success_msg')

    result = miopen_instance.process_compile_results(mock_session, fin_json,
                                                     context)

    assert result is True
    mock_set_state.assert_called_once()
    call_kwargs = mock_set_state.call_args[1]
    assert 'compiled' in str(mock_set_state.call_args)

  @patch('tuna.miopen.miopen_lib.set_job_state')
  @patch('tuna.miopen.miopen_lib.get_fin_result')
  @patch('tuna.miopen.miopen_lib.get_solver_ids')
  def test_process_compile_results_failure(self, mock_get_solver_ids,
                                           mock_get_result, mock_set_state,
                                           miopen_instance):
    """Test failed compile result processing."""
    mock_session = Mock()
    fin_json = {'success': False, 'error': 'compile_error'}
    context = {'job': {'id': 1}, 'config': {'id': 100}, 'fdb_attr': ['col1']}

    miopen_instance.dbt = Mock()
    mock_get_result.return_value = (False, 'error_msg')

    result = miopen_instance.process_compile_results(mock_session, fin_json,
                                                     context)

    assert result is True
    mock_set_state.assert_called_once()
    assert 'errored' in str(mock_set_state.call_args)


# ============================================================================
# Test process_eval_results Method
# ============================================================================
class TestProcessEvalResults:
  """Test eval result processing."""

  @patch('tuna.miopen.miopen_lib.clean_cache_table')
  @patch('tuna.miopen.miopen_lib.set_job_state')
  @patch('tuna.miopen.miopen_lib.get_fin_result')
  @patch('tuna.miopen.miopen_lib.process_fdb_w_kernels')
  def test_process_eval_results_success(self, mock_process_fdb, mock_get_result,
                                        mock_set_state, mock_clean_cache,
                                        miopen_instance):
    """Test successful eval result processing."""
    mock_session = Mock()
    fin_json = {'success': True, 'miopen_find_eval_result': {'timing': 'data'}}
    context = {
        'job': {
            'id': 1,
            'retries': 0
        },
        'config': {
            'id': 100
        },
        'fdb_attr': ['col1'],
        'rich_data': False
    }

    miopen_instance.dbt = Mock()
    mock_process_fdb.return_value = [{'success': True}]
    mock_get_result.return_value = (True, 'success_msg')

    result = miopen_instance.process_eval_results(mock_session, fin_json,
                                                  context)

    assert result is True
    mock_set_state.assert_called_once()
    assert 'evaluated' in str(mock_set_state.call_args)
    mock_clean_cache.assert_called_once()

  @patch('tuna.miopen.miopen_lib.set_job_state')
  @patch('tuna.miopen.miopen_lib.get_fin_result')
  def test_process_eval_results_max_retries(self, mock_get_result,
                                            mock_set_state, miopen_instance):
    """Test eval results with max retries reached."""
    mock_session = Mock()
    fin_json = {'success': False, 'error': 'eval_error'}
    context = {
        'job': {
            'id': 1,
            'retries': MAX_ERRORED_JOB_RETRIES - 1
        },
        'config': {
            'id': 100
        },
        'fdb_attr': ['col1']
    }

    miopen_instance.dbt = Mock()
    miopen_instance.logger = Mock()
    mock_get_result.return_value = (False, 'error_msg')

    result = miopen_instance.process_eval_results(mock_session, fin_json,
                                                  context)

    assert result is True
    mock_set_state.assert_called_once()
    assert 'errored' in str(mock_set_state.call_args)


# ============================================================================
# Test Integration Scenarios
# ============================================================================
class TestIntegrationScenarios:
  """Test complex integration scenarios."""

  @patch('tuna.miopen.miopen_lib.setup_arg_parser')
  @patch('tuna.miopen.miopen_lib.args_check')
  @patch('tuna.miopen.miopen_lib.MIOpenDBTables')
  @patch('sys.argv', ['prog', '--find_mode', '1', '--session_id', '123'])
  def test_full_parse_and_validate(self, mock_dbtables, mock_args_check,
                                   mock_setup_parser):
    """Test full argument parsing and validation flow."""
    mock_parser = Mock()
    mock_parser.parse_args.return_value = Mock(
        config_type=ConfigType.convolution,
        session_id=123,
        subcommand=None,
        list_solvers=False,
        fin_steps=None,
        find_mode=1,
        blacklist=None,
        check_status=False,
        restart_machine=False,
        execute_cmd=None,
        update_applicability=False)
    mock_setup_parser.return_value = mock_parser

    with patch('tuna.miopen.miopen_lib.DbSession'):
      miopen = MIOpen()
      miopen.parse_args()

      assert miopen.args.session_id == 123
      assert miopen.args.config_type == ConfigType.convolution
      mock_dbtables.assert_called_once_with(session_id=123,
                                            config_type=ConfigType.convolution)


if __name__ == '__main__':
  pytest.main([__file__, '-v'])
