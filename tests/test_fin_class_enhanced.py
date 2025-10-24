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
"""Enhanced comprehensive tests for FinClass worker module"""

import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from multiprocessing import Value, Lock, Queue
from tuna.miopen.worker.fin_class import FinClass
from tuna.miopen.utils.config_type import ConfigType
from tuna.miopen.db.tables import MIOpenDBTables
from tuna.machine import Machine


@pytest.fixture
def mock_machine():
  """Create mock machine"""
  machine = Mock(spec=Machine)
  machine.hostname = 'test-machine'
  machine.local_machine = True
  machine.port = 22
  machine.user = 'test_user'
  machine.password = 'test_pass'
  return machine


@pytest.fixture
def mock_dbt():
  """Create mock database tables"""
  dbt = Mock(spec=MIOpenDBTables)
  session = Mock()
  session.id = 1
  session.arch = 'gfx908'
  session.num_cu = 120
  session.rocm_v = 'expected_hash'  # Must match mocked exec_docker_cmd return
  session.miopen_v = 'expected_hash'  # Must match mocked get_miopen_v return
  dbt.session = session

  # Mock config_table with columns that can be inspected
  config_table = Mock()
  mock_col = Mock()
  mock_col.name = 'id'
  config_table.c = [mock_col]
  config_table.relationships = {}
  dbt.config_table = config_table

  # Mock find_db_table with columns
  find_db_table = Mock()
  find_col1 = Mock()
  find_col1.name = 'id'
  find_col2 = Mock()
  find_col2.name = 'insert_ts'
  find_col3 = Mock()
  find_col3.name = 'update_ts'
  find_db_table.c = [find_col1, find_col2, find_col3]
  dbt.find_db_table = find_db_table

  # Mock tuning_data_table for convolution config type
  tuning_data_table = Mock()
  tuning_col1 = Mock()
  tuning_col1.name = 'id'
  tuning_col2 = Mock()
  tuning_col2.name = 'insert_ts'
  tuning_col3 = Mock()
  tuning_col3.name = 'update_ts'
  tuning_data_table.c = [tuning_col1, tuning_col2, tuning_col3]
  dbt.tuning_data_table = tuning_data_table

  # Mock job_table - required by WorkerInterface.__init__
  job_table = Mock()
  job_col1 = Mock()
  job_col1.name = 'id'
  job_col2 = Mock()
  job_col2.name = 'config'
  job_col3 = Mock()
  job_col3.name = 'solver'
  job_col4 = Mock()
  job_col4.name = 'insert_ts'
  job_col5 = Mock()
  job_col5.name = 'update_ts'
  job_table.c = [job_col1, job_col2, job_col3, job_col4, job_col5]
  job_table.__tablename__ = 'conv_job'
  dbt.job_table = job_table

  return dbt


@pytest.fixture(autouse=True)
def patch_miopen_dbtables(mock_dbt, mock_machine):
  """Patch MIOpenDBTables and other external dependencies"""
  # Patch at the actual import location since it's imported inside set_db_tables()
  with patch('tuna.miopen.db.tables.MIOpenDBTables', return_value=mock_dbt):
    with patch('tuna.miopen.worker.fin_class.inspect') as mock_inspect:
      mock_inspect.side_effect = lambda x: x  # Return the object itself
      # Patch database connection to avoid real DB access
      with patch('tuna.worker_interface.connect_db'):
        # Patch logger setup to avoid file system operations
        with patch('tuna.worker_interface.set_usr_logger') as mock_logger:
          mock_logger.return_value = Mock()
          # Patch machine.connect to avoid SSH connections
          mock_machine.connect.return_value = Mock()
          yield


@pytest.fixture
def fin_worker_kwargs(mock_machine):
  """Create FinClass worker kwargs"""
  return {
      'machine': mock_machine,
      'gpu_id': 0,
      'num_procs': Value('i', 2),
      'bar_lock': Lock(),
      'envmt': ["MIOPEN_LOG_LEVEL=7"],
      'reset_interval': False,
      'app_test': False,
      'label': 'test_fin_worker',
      'use_tuner': False,
      'job_queue': Queue(),
      'job_queue_lock': Lock(),  # WorkerInterface expects job_queue_lock
      'end_jobs': Value('i', 0),
      'fin_steps': ['not_fin'],
      'config_type': ConfigType.convolution,
      'session_id': 1,
      'find_mode': 1,
      'blacklist': None
  }


@pytest.mark.unit
@pytest.mark.worker
class TestFinClassInit:
  """Test FinClass initialization"""

  def test_initialization_basic(self, fin_worker_kwargs):
    """Test basic FinClass initialization"""
    worker = FinClass(**fin_worker_kwargs)

    assert worker.config_type == ConfigType.convolution
    assert worker.session_id == 1
    assert worker.gpu_id == 0
    assert worker.label == 'test_fin_worker'
    assert worker.fin_steps == ['not_fin']
    assert worker.dynamic_solvers_only is False

  def test_initialization_with_dynamic_solvers(self, fin_worker_kwargs):
    """Test initialization with dynamic solvers only"""
    fin_worker_kwargs['dynamic_solvers_only'] = True
    worker = FinClass(**fin_worker_kwargs)

    assert worker.dynamic_solvers_only is True

  def test_initialization_sets_miopen_paths(self, fin_worker_kwargs):
    """Test that MIOPEN environment variables are set"""
    worker = FinClass(**fin_worker_kwargs)

    # Check that MIOPEN env vars are in envmt
    miopen_env_vars = [e for e in worker.envmt if 'MIOPEN' in e]
    assert len(miopen_env_vars) >= 3  # Original + 2 added by FinClass
    assert any('MIOPEN_USER_DB_PATH' in e for e in worker.envmt)
    assert any('MIOPEN_CUSTOM_CACHE_DIR' in e for e in worker.envmt)

  def test_initialization_config_types(self, fin_worker_kwargs):
    """Test initialization with different config types"""
    for config_type in [ConfigType.convolution, ConfigType.batch_norm]:
      fin_worker_kwargs['config_type'] = config_type
      worker = FinClass(**fin_worker_kwargs)
      assert worker.config_type == config_type

  def test_initialization_fin_steps(self, fin_worker_kwargs):
    """Test initialization with various fin steps"""
    fin_steps = ['get_solvers', 'applicability', 'fin_find_compile']
    fin_worker_kwargs['fin_steps'] = fin_steps
    worker = FinClass(**fin_worker_kwargs)
    assert worker.fin_steps == fin_steps


@pytest.mark.unit
@pytest.mark.worker
class TestFinClassAttributes:
  """Test FinClass attribute access"""

  def test_has_required_attributes(self, fin_worker_kwargs):
    """Test that worker has all required attributes"""
    worker = FinClass(**fin_worker_kwargs)

    required_attrs = [
        'config_type', 'session_id', 'gpu_id', 'machine', 'fin_steps',
        'job_queue', 'envmt', 'solver_id_map', 'id_solver_map', 'local_file',
        'fin_infile', 'fin_outfile'
    ]

    for attr in required_attrs:
      assert hasattr(worker, attr), f"Missing attribute: {attr}"

  def test_temp_file_creation(self, fin_worker_kwargs):
    """Test that temporary files are created"""
    worker = FinClass(**fin_worker_kwargs)

    assert worker.local_file is not None
    assert worker.fin_infile is not None
    assert worker.fin_outfile is not None
    assert worker.fin_infile.endswith('.json')
    assert worker.fin_outfile.endswith('.json')

  def test_solver_maps_initialized(self, fin_worker_kwargs):
    """Test that solver ID maps are initialized"""
    worker = FinClass(**fin_worker_kwargs)

    assert hasattr(worker, 'solver_id_map')
    assert hasattr(worker, 'id_solver_map')
    assert worker.solver_id_map is not None


@pytest.mark.unit
@pytest.mark.worker
class TestFinClassCheckEnv:
  """Test FinClass environment checking"""

  @patch.object(FinClass, 'exec_docker_cmd')
  def test_get_miopen_v_success(self, mock_exec, fin_worker_kwargs):
    """Test getting MIOpen version successfully"""
    mock_exec.return_value = (0, '12345abc', '')
    worker = FinClass(**fin_worker_kwargs)

    version = worker.get_miopen_v()
    assert version == '12345abc'
    mock_exec.assert_called_once()

  @patch.object(FinClass, 'exec_docker_cmd')
  def test_get_miopen_v_fallback_path(self, mock_exec, fin_worker_kwargs):
    """Test getting MIOpen version with fallback path"""
    # First call fails, second succeeds
    mock_exec.side_effect = [(0, 'No such file or directory', ''),
                             (0, 'abcdef123', '')]
    worker = FinClass(**fin_worker_kwargs)

    version = worker.get_miopen_v()
    assert version == 'abcdef123'
    assert mock_exec.call_count == 2

  @patch.object(FinClass, 'exec_docker_cmd')
  def test_check_env_success(self, mock_exec, fin_worker_kwargs):
    """Test environment check success"""
    mock_exec.return_value = (0, 'expected_hash', '')
    worker = FinClass(**fin_worker_kwargs)

    # Mock the check
    with patch.object(worker, 'get_miopen_v', return_value='expected_hash'):
      result = worker.check_env()
      assert result is True


@pytest.mark.unit
@pytest.mark.worker
class TestFinClassQueueOperations:
  """Test FinClass queue operations"""

  def test_queue_end_reset(self, fin_worker_kwargs):
    """Test queue end reset operation"""
    worker = FinClass(**fin_worker_kwargs)
    worker.end_jobs.value = 5

    worker.queue_end_reset()
    assert worker.end_jobs.value == 0

  def test_job_queue_empty_initially(self, fin_worker_kwargs):
    """Test that job queue is empty on initialization"""
    worker = FinClass(**fin_worker_kwargs)
    assert worker.job_queue.empty()

  def test_can_add_jobs_to_queue(self, fin_worker_kwargs):
    """Test adding jobs to queue"""
    worker = FinClass(**fin_worker_kwargs)
    test_job = {'id': 1, 'config': 'test'}

    # Verify worker can put and get from queue
    worker.job_queue.put(test_job)
    retrieved_job = worker.job_queue.get(timeout=1)
    assert retrieved_job == test_job


@pytest.mark.unit
@pytest.mark.worker
class TestFinClassSolvers:
  """Test FinClass solver-related operations"""

  @patch('tuna.miopen.worker.fin_class.get_solver_ids')
  @patch('tuna.miopen.worker.fin_class.get_id_solvers')
  def test_solver_maps_loaded(self, mock_id_solvers, mock_solver_ids,
                              fin_worker_kwargs):
    """Test that solver maps are loaded correctly"""
    mock_solver_ids.return_value = {'ConvAsm1x1U': 1, 'ConvOclDirectFwd': 2}
    mock_id_solvers.return_value = (True, {
        1: 'ConvAsm1x1U',
        2: 'ConvOclDirectFwd'
    })

    worker = FinClass(**fin_worker_kwargs)

    assert worker.solver_id_map is not None
    mock_solver_ids.assert_called_once()
    mock_id_solvers.assert_called_once()


@pytest.mark.unit
@pytest.mark.worker
class TestFinClassConfigTypes:
  """Test FinClass with different config types"""

  def test_convolution_config_type(self, fin_worker_kwargs):
    """Test FinClass with convolution config type"""
    fin_worker_kwargs['config_type'] = ConfigType.convolution
    worker = FinClass(**fin_worker_kwargs)

    assert worker.config_type == ConfigType.convolution
    assert hasattr(worker, 'tuning_data_attr')

  def test_batch_norm_config_type(self, fin_worker_kwargs):
    """Test FinClass with batch norm config type"""
    fin_worker_kwargs['config_type'] = ConfigType.batch_norm
    worker = FinClass(**fin_worker_kwargs)

    assert worker.config_type == ConfigType.batch_norm


@pytest.mark.unit
@pytest.mark.worker
class TestFinClassEnvironment:
  """Test FinClass environment setup"""

  def test_gpu_specific_paths(self, fin_worker_kwargs):
    """Test that GPU-specific paths are set correctly"""
    gpu_id = 3
    fin_worker_kwargs['gpu_id'] = gpu_id
    worker = FinClass(**fin_worker_kwargs)

    # Check that paths contain GPU ID
    miopen_paths = [e for e in worker.envmt if 'MIOPEN' in e and 'thread' in e]
    assert len(miopen_paths) >= 2
    assert all(f'thread-{gpu_id}' in path for path in miopen_paths)

  def test_additional_env_vars_preserved(self, fin_worker_kwargs):
    """Test that additional environment variables are preserved"""
    custom_envmt = [
        "MIOPEN_LOG_LEVEL=7", "MIOPEN_FIND_ENFORCE=3", "CUSTOM_VAR=value"
    ]
    fin_worker_kwargs['envmt'] = custom_envmt.copy()
    worker = FinClass(**fin_worker_kwargs)

    # Check that original env vars are still there
    for env_var in custom_envmt:
      assert env_var in worker.envmt


@pytest.mark.unit
@pytest.mark.worker
class TestFinClassEdgeCases:
  """Test FinClass edge cases"""

  def test_initialization_with_none_config_type(self, fin_worker_kwargs):
    """Test initialization with None config type defaults to convolution"""
    fin_worker_kwargs['config_type'] = None
    worker = FinClass(**fin_worker_kwargs)

    assert worker.config_type == ConfigType.convolution

  def test_multiproc_flag_default(self, fin_worker_kwargs):
    """Test multiproc flag is False by default"""
    worker = FinClass(**fin_worker_kwargs)
    assert worker.multiproc is False

  def test_first_pass_flag_default(self, fin_worker_kwargs):
    """Test first_pass flag is True by default"""
    worker = FinClass(**fin_worker_kwargs)
    assert worker.first_pass is True

  def test_empty_fin_steps(self, fin_worker_kwargs):
    """Test initialization with empty fin_steps"""
    fin_worker_kwargs['fin_steps'] = []
    worker = FinClass(**fin_worker_kwargs)
    assert worker.fin_steps == []

  def test_supported_fin_steps_list(self, fin_worker_kwargs):
    """Test supported fin steps list is available"""
    worker = FinClass(**fin_worker_kwargs)
    assert hasattr(worker, 'supported_fin_steps')
    assert 'get_solvers' in worker.supported_fin_steps
    assert 'applicability' in worker.supported_fin_steps


@pytest.mark.unit
@pytest.mark.worker
class TestFinClassDatabaseAttributes:
  """Test FinClass database table attributes"""

  def test_config_attributes_initialized(self, fin_worker_kwargs):
    """Test that config attributes are extracted"""
    worker = FinClass(**fin_worker_kwargs)
    assert hasattr(worker, 'cfg_attr')
    assert isinstance(worker.cfg_attr, list)

  def test_fdb_attributes_initialized(self, fin_worker_kwargs):
    """Test that find database attributes are extracted"""
    worker = FinClass(**fin_worker_kwargs)
    assert hasattr(worker, 'fdb_attr')
    assert isinstance(worker.fdb_attr, list)
    # insert_ts and update_ts should be removed
    assert 'insert_ts' not in worker.fdb_attr
    assert 'update_ts' not in worker.fdb_attr


@pytest.mark.unit
@pytest.mark.worker
class TestFinClassLocks:
  """Test FinClass lock handling"""

  def test_bar_lock_initialized(self, fin_worker_kwargs):
    """Test that bar_lock is initialized"""
    worker = FinClass(**fin_worker_kwargs)
    assert hasattr(worker, 'bar_lock')
    assert worker.bar_lock is not None

  def test_queue_lock_initialized(self, fin_worker_kwargs):
    """Test that job_queue_lock is initialized"""
    worker = FinClass(**fin_worker_kwargs)
    assert hasattr(worker, 'job_queue_lock')
    assert worker.job_queue_lock is not None


@pytest.mark.unit
@pytest.mark.worker
class TestFinClassMachineAccess:
  """Test FinClass machine attribute access"""

  def test_machine_attribute(self, fin_worker_kwargs, mock_machine):
    """Test machine attribute access"""
    worker = FinClass(**fin_worker_kwargs)
    assert worker.machine == mock_machine
    assert worker.machine.hostname == 'test-machine'

  def test_gpu_id_attribute(self, fin_worker_kwargs):
    """Test GPU ID attribute"""
    gpu_id = 5
    fin_worker_kwargs['gpu_id'] = gpu_id
    worker = FinClass(**fin_worker_kwargs)
    assert worker.gpu_id == gpu_id
