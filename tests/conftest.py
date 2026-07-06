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
"""
Pytest configuration and shared fixtures for MITuna test suite.

This module provides reusable fixtures for database sessions, temporary files,
logging, and mock objects to support test isolation and maintainability.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as SQLAlchemySession

# Add tuna to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.logger import setup_logger
from tuna.utils.utility import get_env_vars
from tuna.miopen.db.session import Session as MIOPenSession
from tuna.miopen.utils.config_type import ConfigType

# ============================================================================
# Session-scoped fixtures (initialized once per test session)
# ============================================================================


@pytest.fixture(scope="session")
def test_env_vars():
  """Provide test environment variables."""
  return get_env_vars()


@pytest.fixture(scope="session")
def test_db_engine(test_env_vars):
  """Create a test database engine."""
  engine = create_engine(
      f"mysql+pymysql://{test_env_vars['user_name']}:"
      f"{test_env_vars['user_password']}@{test_env_vars['db_hostname']}:"
      f"3306/{test_env_vars['db_name']}")
  return engine


# ============================================================================
# Function-scoped fixtures (initialized for each test function)
# ============================================================================


@pytest.fixture
def db_session(test_db_engine) -> Generator[SQLAlchemySession, None, None]:
  """
  Provide a database session with automatic rollback for test isolation.
  
  This fixture creates a new database session for each test and rolls back
  all changes at the end, ensuring tests don't affect each other.
  """
  connection = test_db_engine.connect()
  transaction = connection.begin()
  SessionLocal = sessionmaker(bind=connection)
  session = SessionLocal()

  yield session

  session.close()
  transaction.rollback()
  connection.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
  """Provide a temporary directory that is cleaned up after the test."""
  temp_path = Path(tempfile.mkdtemp(prefix="mituna_test_"))
  yield temp_path
  if temp_path.exists():
    shutil.rmtree(temp_path)


@pytest.fixture
def temp_file(temp_dir) -> Generator[Path, None, None]:
  """Provide a temporary file path in a temporary directory."""
  file_path = temp_dir / "test_file.txt"
  yield file_path
  if file_path.exists():
    file_path.unlink()


@pytest.fixture
def test_logger():
  """Provide a test logger instance."""
  return setup_logger('test_logger')


@pytest.fixture
def mock_machine():
  """Provide a mock Machine object for testing."""
  machine = MagicMock()
  machine.hostname = "test-machine"
  machine.ip = "127.0.0.1"
  machine.local_ip = "127.0.0.1"
  machine.port = 22
  machine.user = "test_user"
  machine.password = "test_pass"
  machine.arch = "gfx90a"
  machine.num_cu = 110
  machine.available = True
  machine.id = 1
  return machine


@pytest.fixture
def mock_session():
  """Provide a mock Session object for MIOpen testing."""
  session = MagicMock(spec=MIOPenSession)
  session.id = 1
  session.arch = "gfx90a"
  session.num_cu = 110
  session.rocm_v = "5.7.0"
  session.miopen_v = "2.20.0"
  return session


@pytest.fixture
def convolution_config_type():
  """Provide convolution config type."""
  return ConfigType.convolution


@pytest.fixture
def batch_norm_config_type():
  """Provide batch norm config type."""
  return ConfigType.batch_norm


@pytest.fixture
def sample_conv_driver_cmd():
  """Provide a sample convolution driver command for testing."""
  return ("./bin/MIOpenDriver conv --pad_h 1 --pad_w 1 --out_channels 128 "
          "--fil_w 3 --fil_h 3 --dilation_w 1 --dilation_h 1 "
          "--conv_stride_w 1 --conv_stride_h 1 --in_channels 128 "
          "--in_w 28 --in_h 28 --batchsize 256 --group_count 1 "
          "--in_d 1 --fil_d 1 --forw 1 --in_layout NCHW "
          "--fil_layout NCHW --out_layout NCHW -V 0")


@pytest.fixture
def sample_bn_driver_cmd():
  """Provide a sample batch norm driver command for testing."""
  return ("./bin/MIOpenDriver bnorm -n 256 -c 64 -H 56 -W 56 "
          "-m 1 --forw 1 -b 0 -s 1 -r 1")


@pytest.fixture
def sample_fdb_entry():
  """Provide a sample find database entry."""
  return {
      "config": 1,
      "solver": 1,
      "fdb_key": "64-75-75-3x3-64-75-75-512-1x1-1x1-1x1-0-NHWC-FP16-F",
      "params": "1x256x1x1x128,1x3x3x128x128,56,2",
      "kernel_time": 0.123456,
      "workspace_sz": 0,
      "opencl": False,
      "session": 1
  }


# ============================================================================
# Fixtures for mocking external dependencies
# ============================================================================


@pytest.fixture
def mock_subprocess():
  """Mock subprocess calls to prevent actual system commands."""
  with patch('subprocess.run') as mock_run, \
       patch('subprocess.Popen') as mock_popen, \
       patch('subprocess.check_output') as mock_output:
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    mock_popen.return_value = MagicMock(pid=12345)
    mock_output.return_value = b""
    yield {'run': mock_run, 'popen': mock_popen, 'check_output': mock_output}


@pytest.fixture
def mock_ssh():
  """Mock SSH/paramiko connections."""
  with patch('paramiko.SSHClient') as mock_client:
    mock_ssh_instance = MagicMock()
    mock_client.return_value = mock_ssh_instance
    yield mock_ssh_instance


@pytest.fixture
def mock_redis():
  """Mock Redis connections."""
  with patch('redis.Redis') as mock_redis_class:
    mock_redis_instance = MagicMock()
    mock_redis_class.return_value = mock_redis_instance
    yield mock_redis_instance


@pytest.fixture
def mock_celery():
  """Mock Celery task queue."""
  with patch('celery.Celery') as mock_celery_class:
    mock_celery_instance = MagicMock()
    mock_celery_class.return_value = mock_celery_instance
    yield mock_celery_instance


@pytest.fixture
def isolated_filesystem(temp_dir, monkeypatch):
  """
  Change to a temporary directory for filesystem isolation.
  
  This fixture changes the current working directory to a temporary location
  and restores it after the test completes.
  """
  original_dir = Path.cwd()
  monkeypatch.chdir(temp_dir)
  yield temp_dir
  os.chdir(original_dir)


# ============================================================================
# Fixtures for test data factories
# ============================================================================


@pytest.fixture
def config_factory():
  """
  Factory fixture for creating test configuration objects.
  
  Usage:
      def test_example(config_factory):
          config = config_factory(batchsize=128, in_channels=64)
  """

  def _create_config(**kwargs):
    """Create a configuration dictionary with defaults."""
    defaults = {
        'batchsize': 256,
        'spatial_dim': 2,
        'in_channels': 128,
        'in_h': 28,
        'in_w': 28,
        'in_d': 1,
        'fil_h': 3,
        'fil_w': 3,
        'fil_d': 1,
        'out_channels': 128,
        'pad_h': 1,
        'pad_w': 1,
        'pad_d': 0,
        'conv_stride_h': 1,
        'conv_stride_w': 1,
        'conv_stride_d': 0,
        'dilation_h': 1,
        'dilation_w': 1,
        'dilation_d': 0,
        'group_count': 1,
        'in_layout': 'NCHW',
        'fil_layout': 'NCHW',
        'out_layout': 'NCHW',
        'data_type': 'FP32',
        'direction': 'F',
    }
    defaults.update(kwargs)
    return defaults

  return _create_config


@pytest.fixture
def job_factory():
  """Factory fixture for creating test job objects."""

  def _create_job(**kwargs):
    """Create a job dictionary with defaults."""
    defaults = {
        'id': 1,
        'config': 1,
        'solver': 1,
        'session': 1,
        'state': 'new',
        'valid': 1,
        'reason': None,
        'retries': 0,
    }
    defaults.update(kwargs)
    return defaults

  return _create_job


# ============================================================================
# Hooks for test execution
# ============================================================================


def pytest_configure(config):
  """Configure pytest with custom settings."""
  # Add custom markers
  config.addinivalue_line("markers", "unit: Unit tests")
  config.addinivalue_line("markers", "integration: Integration tests")
  config.addinivalue_line("markers", "db: Database tests")
  config.addinivalue_line("markers", "slow: Slow running tests")


def pytest_collection_modifyitems(config, items):
  """Modify test collection to add markers automatically."""
  for item in items:
    # Auto-mark database tests
    if "db_session" in item.fixturenames or "test_db" in item.nodeid:
      item.add_marker(pytest.mark.db)

    # Auto-mark integration tests based on file name patterns
    if "integration" in item.nodeid:
      item.add_marker(pytest.mark.integration)
    elif "test_" in item.nodeid and "integration" not in item.nodeid:
      item.add_marker(pytest.mark.unit)
