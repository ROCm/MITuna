# MITuna Testing Guide

This document provides comprehensive guidance for testing the MITuna project, with a focus on the MIOpen subsystem.

## Table of Contents

1. [Test Structure](#test-structure)
2. [Running Tests](#running-tests)
3. [Test Infrastructure](#test-infrastructure)
4. [Writing Tests](#writing-tests)
5. [Test Fixtures](#test-fixtures)
6. [Coverage Reports](#coverage-reports)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

## Test Structure

Tests are organized by module and functionality:

```
tests/
├── conftest.py              # Shared fixtures and pytest configuration
├── utils.py                 # Test helper functions and utilities
├── fixtures/                # Sample data files for testing
│   ├── sample_conv_configs.txt
│   ├── sample_bn_configs.txt
│   ├── sample_fdb.txt
│   └── sample_pdb.json
├── test_*.py                # Test modules (one per source module)
└── README.md                # This file
```

### Test Categories

Tests are categorized using pytest markers:

- `@pytest.mark.unit`: Fast, isolated unit tests
- `@pytest.mark.integration`: Integration tests requiring external resources
- `@pytest.mark.db`: Tests requiring database connection
- `@pytest.mark.slow`: Tests that take significant time
- `@pytest.mark.miopen`: MIOpen-specific tests
- `@pytest.mark.worker`: Worker/Celery tests
- `@pytest.mark.driver`: Driver command parsing tests
- `@pytest.mark.subcmd`: Subcommand functionality tests
- `@pytest.mark.utils`: Utility module tests
- `@pytest.mark.smoke`: Quick smoke tests

## Running Tests

### Prerequisites

Ensure you have the test environment set up:

```bash
# Activate virtual environment
source myvenv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables (source your env file)
source your_env_file.sh
```

### Run All Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with output capturing disabled (see print statements)
pytest -s
```

### Run Specific Test Categories

```bash
# Run only unit tests (fast)
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only database tests
pytest -m db

# Run MIOpen-specific tests
pytest -m miopen

# Exclude slow tests
pytest -m "not slow"

# Run multiple categories
pytest -m "unit or integration"
```

### Run Specific Test Files or Functions

```bash
# Run a specific test file
pytest tests/test_driver.py

# Run a specific test function
pytest tests/test_driver.py::test_driver

# Run tests matching a pattern
pytest -k "driver"

# Run tests in a directory
pytest tests/
```

### Run with Coverage

```bash
# Run tests with coverage report
pytest --cov=tuna --cov-report=html --cov-report=term

# Run with coverage for specific module
pytest --cov=tuna/miopen --cov-report=html

# Generate coverage report for CI
pytest --cov=tuna --cov-report=xml --cov-report=term

# View HTML coverage report
# Open htmlcov/index.html in browser
```

### Parallel Execution

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel (4 workers)
pytest -n 4

# Auto-detect number of CPUs
pytest -n auto
```

## Test Infrastructure

### conftest.py

The `conftest.py` file provides shared fixtures:

#### Database Fixtures

- `test_env_vars`: Test environment variables
- `test_db_engine`: Database engine for testing
- `db_session`: Database session with automatic rollback

#### File System Fixtures

- `temp_dir`: Temporary directory (cleaned up after test)
- `temp_file`: Temporary file path
- `isolated_filesystem`: Change to temp directory for test

#### Mock Fixtures

- `mock_machine`: Mock Machine object
- `mock_session`: Mock Session object
- `mock_subprocess`: Mock subprocess calls
- `mock_ssh`: Mock SSH connections
- `mock_redis`: Mock Redis connections
- `mock_celery`: Mock Celery task queue

#### Data Fixtures

- `config_factory`: Factory for creating test configs
- `job_factory`: Factory for creating test jobs
- `sample_conv_driver_cmd`: Sample convolution command
- `sample_bn_driver_cmd`: Sample batch norm command
- `sample_fdb_entry`: Sample find database entry

### utils.py

The `utils.py` module provides helper functions:

#### Factory Functions

- `create_test_config_dict(**kwargs)`: Create test configuration
- `create_test_job_dict(**kwargs)`: Create test job
- `create_test_solver_dict(**kwargs)`: Create test solver
- `create_mock_args(**kwargs)`: Create mock arguments object

#### Assertion Helpers

- `assert_config_equal(config1, config2, ignore_fields)`: Compare configs
- `assert_job_state(session, job_id, expected_state)`: Check job state

#### Database Helpers

- `count_table_rows(session, table_class)`: Count rows in table
- `cleanup_test_data(session, table_class, filter_func)`: Clean up test data

#### Test Data Generators

- `generate_driver_commands(num_commands, cmd_type)`: Generate driver commands
- `create_temp_config_file(temp_dir, commands)`: Create temporary config file

#### Validation Helpers

- `validate_fdb_entry(fdb_entry, required_fields)`: Validate FDB entry
- `compare_driver_objects(driver1, driver2, ignore_fields)`: Compare drivers

## Writing Tests

### Test Naming Conventions

- Test files: `test_<module_name>.py`
- Test functions: `test_<functionality>()`
- Test classes: `Test<ClassName>`

### Example Unit Test

```python
import pytest
from tuna.miopen.driver.convolution import DriverConvolution

@pytest.mark.unit
def test_driver_convolution_parsing(sample_conv_driver_cmd):
    """Test that DriverConvolution parses commands correctly."""
    driver = DriverConvolution(sample_conv_driver_cmd)
    
    assert driver.cmd == 'conv'
    assert driver.batchsize == 256
    assert driver.in_channels == 128
    assert driver.direction == 'F'
```

### Example Integration Test

```python
import pytest
from tuna.miopen.subcmd.import_configs import import_cfgs
from tests.utils import create_mock_args

@pytest.mark.integration
@pytest.mark.db
def test_import_configs_integration(db_session, temp_dir, config_factory):
    """Test importing configurations from file."""
    # Setup
    args = create_mock_args(config_type='convolution')
    config_file = create_temp_config_file(temp_dir, [sample_conv_driver_cmd])
    
    # Execute
    result = import_cfgs(args, dbt, logger)
    
    # Verify
    assert result['cnt_configs'] > 0
```

### Using Fixtures

```python
@pytest.mark.unit
def test_with_temp_file(temp_file):
    """Test using temporary file fixture."""
    temp_file.write_text("test data")
    assert temp_file.read_text() == "test data"

@pytest.mark.db
def test_with_database(db_session):
    """Test using database session fixture."""
    # Changes are automatically rolled back after test
    result = db_session.query(SomeTable).all()
    assert len(result) >= 0
```

### Using Mocks

```python
from unittest.mock import patch, MagicMock

@pytest.mark.unit
def test_with_mock(mock_subprocess):
    """Test using subprocess mock."""
    # subprocess.run is automatically mocked
    result = subprocess.run(['echo', 'test'])
    assert result.returncode == 0
    mock_subprocess['run'].assert_called_once()

@pytest.mark.unit
def test_with_manual_mock():
    """Test with manual mocking."""
    with patch('tuna.miopen.driver.base.subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        # Test code here
```

### Parametrized Tests

```python
@pytest.mark.parametrize("batchsize,in_channels", [
    (64, 64),
    (128, 128),
    (256, 256),
])
def test_driver_with_params(batchsize, in_channels, config_factory):
    """Test driver with multiple parameter combinations."""
    config = config_factory(batchsize=batchsize, in_channels=in_channels)
    # Test code here
```

## Test Fixtures

### Sample Data Files

Sample data files are located in `tests/fixtures/`:

- `sample_conv_configs.txt`: Convolution driver commands
- `sample_bn_configs.txt`: Batch norm driver commands
- `sample_fdb.txt`: Find database entries
- `sample_pdb.json`: Performance database entries

### Using Sample Data

```python
import os

def test_using_sample_data():
    """Test using sample data file."""
    fixture_dir = os.path.join(os.path.dirname(__file__), 'fixtures')
    config_file = os.path.join(fixture_dir, 'sample_conv_configs.txt')
    
    with open(config_file, 'r') as f:
        commands = f.readlines()
    
    assert len(commands) > 0
```

## Coverage Reports

### Viewing Coverage

After running tests with coverage:

```bash
# Terminal report
pytest --cov=tuna --cov-report=term

# HTML report (detailed, interactive)
pytest --cov=tuna --cov-report=html
# Then open: htmlcov/index.html

# XML report (for CI systems)
pytest --cov=tuna --cov-report=xml
```

### Coverage Configuration

Coverage is configured in `.coveragerc`:

- Source directory: `./tuna`
- Omitted files: `__init__.py`, specific scripts
- Excluded lines: `def __repr__`, `raise NotImplementedError`, `if __name__ == .__main__.:`

### Coverage Goals

- Overall project: ≥ 85%
- Individual modules: ≥ 80%
- Critical paths: ≥ 90%

## Best Practices

### Test Isolation

1. **Use fixtures for setup/teardown**: Ensure tests don't affect each other
2. **Use database rollback**: The `db_session` fixture automatically rolls back changes
3. **Use temporary files**: The `temp_dir` and `temp_file` fixtures are cleaned up automatically
4. **Mock external dependencies**: Use mocks for file system, network, subprocess calls

### Test Speed

1. **Keep unit tests fast**: < 1 second each
2. **Use mocks aggressively**: Avoid real I/O in unit tests
3. **Mark slow tests**: Use `@pytest.mark.slow` for tests > 5 seconds
4. **Run unit tests first**: `pytest -m unit` for quick feedback

### Test Coverage

1. **Test both happy and sad paths**: Include error cases
2. **Test edge cases**: Boundary conditions, empty inputs, invalid data
3. **Test all branches**: Aim for 100% branch coverage
4. **Don't test implementation details**: Test behavior, not internals

### Test Maintainability

1. **Use descriptive names**: Test name should describe what is being tested
2. **Use docstrings**: Explain complex test scenarios
3. **Keep tests simple**: One concept per test
4. **Use factories and fixtures**: Reduce duplication
5. **Avoid test interdependencies**: Each test should run independently

### Code Style

1. **Follow PEP 8**: Use yapf for formatting
2. **Use type hints**: Where appropriate
3. **Document complex logic**: Comments for non-obvious code
4. **Keep functions small**: < 50 lines per function

## Troubleshooting

### Common Issues

#### Database Connection Errors

```
Error: Can't connect to MySQL server
```

**Solution**: Ensure MySQL is running and environment variables are set:
```bash
export TUNA_DB_HOSTNAME=localhost
export TUNA_DB_NAME=test_db
export TUNA_DB_USER_NAME=root
export TUNA_DB_USER_PASSWORD=your_password
```

#### Import Errors

```
ImportError: No module named 'tuna'
```

**Solution**: Ensure PYTHONPATH is set:
```bash
export PYTHONPATH=/path/to/MITuna:$PYTHONPATH
```

#### Fixture Not Found

```
fixture 'db_session' not found
```

**Solution**: Ensure `conftest.py` is in the tests directory and pytest is discovering it.

#### Tests Hanging

**Solution**: 
1. Check for infinite loops in test code
2. Use pytest timeout plugin: `pip install pytest-timeout`
3. Add timeout to pytest.ini: `timeout = 300`

### Debugging Tests

```bash
# Run with Python debugger
pytest --pdb

# Drop into debugger on failure
pytest --pdb --maxfail=1

# Show local variables on failure
pytest -l

# Show full diff for assertion failures
pytest -vv
```

### Verbose Output

```bash
# Show print statements
pytest -s

# Show detailed output
pytest -vv

# Show test durations
pytest --durations=10

# Show slowest tests
pytest --durations=0
```

## CI Integration

### Jenkins Pipeline

Tests run automatically in Jenkins pipeline:

1. **pytestSuite1**: Main test suite (no GPU required)
2. **pytestSuite2**: Celery/worker tests
3. **pytestSuite3**: GPU-required tests

### Running CI Locally

```bash
# Run like CI
python3 -m coverage run -a -m pytest tests/test_driver.py -s
python3 -m coverage run -a -m pytest tests/test_importconfigs.py -s
# ... add more tests ...
coverage report -m
```

## Contributing

When adding new features:

1. Write tests first (TDD)
2. Ensure all tests pass: `pytest`
3. Check coverage: `pytest --cov=tuna/miopen`
4. Format code: `yapf -i --style='{based_on_style: google, indent_width: 2}' --recursive tuna/ tests/`
5. Run linters: `pylint` (see README.md for commands)
6. Update this document if adding new test infrastructure

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [Python unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [MITuna main README](../README.md)

## Support

For questions or issues with testing:

1. Check this document
2. Review existing tests for examples
3. Check CI pipeline logs
4. Ask the team

---

**Last Updated**: 2025-10-08
**Maintained By**: MITuna Development Team

