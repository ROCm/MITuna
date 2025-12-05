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
"""Tests for tuna.example.build_schema"""
import os
import sys
from unittest.mock import Mock, patch, MagicMock

sys.path.append("../tuna")
sys.path.append("tuna")

from tuna.example import build_schema


def test_main_function():
  """Test main() function execution"""
  with patch('tuna.example.build_schema.create_tables') as mock_create_tables, \
       patch('tuna.example.build_schema.get_tables') as mock_get_tables, \
       patch('tuna.example.build_schema.LOGGER') as mock_logger:

    # Setup mocks
    mock_tables = [Mock(), Mock()]
    mock_get_tables.return_value = mock_tables
    mock_create_tables.return_value = True

    # Call main
    build_schema.main()

    # Verify create_tables was called with correct tables
    mock_get_tables.assert_called_once()
    mock_create_tables.assert_called_once_with(mock_tables)

    # Verify logger was called with success message
    mock_logger.info.assert_called_once()
    call_args = mock_logger.info.call_args[0]
    assert 'DB creation successful' in call_args[0]
    assert call_args[1] is True


def test_main_function_failure():
  """Test main() function when table creation fails"""
  with patch('tuna.example.build_schema.create_tables') as mock_create_tables, \
       patch('tuna.example.build_schema.get_tables') as mock_get_tables, \
       patch('tuna.example.build_schema.LOGGER') as mock_logger:

    # Setup mocks
    mock_tables = [Mock()]
    mock_get_tables.return_value = mock_tables
    mock_create_tables.return_value = False

    # Call main
    build_schema.main()

    # Verify logger was called with failure message
    mock_logger.info.assert_called_once()
    call_args = mock_logger.info.call_args[0]
    assert 'DB creation successful' in call_args[0]
    assert call_args[1] is False


def test_main_as_script():
  """Test main() execution path (module structure check)"""
  # Verify main function exists and is callable
  assert hasattr(build_schema, 'main')
  assert callable(build_schema.main)


def test_module_imports():
  """Test that module imports correctly"""
  assert hasattr(build_schema, 'LOGGER')
  assert hasattr(build_schema, 'setup_logger')
  assert hasattr(build_schema, 'create_tables')
  assert hasattr(build_schema, 'get_tables')
