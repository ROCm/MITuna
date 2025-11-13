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
"""Extended tests for Machine class to improve coverage"""

import sys
import os
from io import StringIO
from unittest.mock import Mock, patch, MagicMock, mock_open
import socket
import tempfile

sys.path.append("../tuna")
sys.path.append("tuna")

from tuna.machine import Machine
from tuna.db.session_mixin import DbSession
from tuna.utils.db_utility import create_tables


def test_remote_machine_init():
  """Test initialization of remote machine (non-local)"""
  keys = {
      'id': 1,
      'hostname': 'test-host',
      'user': 'test-user',
      'password': 'test-pass',
      'port': 22,
      'local_ip': '192.168.1.100',
      'local_port': 22,
      'arch': 'gfx908',
      'num_cu': 120,
      'avail_gpus': '0,1,2,3',
      'local_machine': False,
      'ipmi_ip': '192.168.1.101',
      'ipmi_port': 623,
      'ipmi_user': 'ipmi_user',
      'ipmi_password': 'ipmi_pass',
      'ipmi_inaccessible': 0
  }

  # Mock hostname check
  with patch('subprocess.Popen') as mock_popen:
    mock_process = Mock()
    mock_process.stdout = Mock()
    mock_process.stdout.readline = Mock(return_value='test-host\n')
    mock_popen.return_value.__enter__ = Mock(return_value=mock_process)
    mock_popen.return_value.__exit__ = Mock(return_value=False)

    m = Machine(**keys)

    # Verify remote machine setup
    assert m.id == 1
    assert m.hostname == keys['hostname']
    assert m.avail_gpus == [0, 1, 2, 3]
    assert m.num_gpus == 4
    assert m.cpus == []
    assert m.gpus == []


def test_get_avail_gpus_empty():
  """Test get_avail_gpus when gpus list is initially empty"""
  keys = {'local_machine': True}
  m = Machine(**keys)

  # Clear the gpus to simulate empty state
  m.avail_gpus = None
  m.gpus = []

  # Mock get_properties to populate gpus (with side effect)
  def mock_get_properties_side_effect():
    """Mock that also sets self.gpus like the real method does"""
    m.gpus = [{'arch': 'gfx908', 'num_cu': 120}]
    return ([], m.gpus)

  with patch.object(
      m, 'get_properties',
      side_effect=mock_get_properties_side_effect) as mock_get_props:
    gpus = m.get_avail_gpus()

    # get_properties should be called when gpus is empty
    mock_get_props.assert_called_once()
    # Should now have GPU 0 available
    assert gpus == [0]


def test_get_gpu_out_of_bounds():
  """Test get_gpu with invalid index"""
  keys = {'local_machine': True}
  m = Machine(**keys)

  # Try to get GPU beyond available range
  result = m.get_gpu(999)
  assert result is None


def test_get_gpu_no_gpus():
  """Test get_gpu when gpus list is empty"""
  keys = {'local_machine': True}
  m = Machine(**keys)

  m.gpus = []
  result = m.get_gpu(0)
  assert result is None


def test_parse_agents_keyerror():
  """Test parse_agents when ISA Info has KeyError"""
  keys = {'local_machine': True}
  m = Machine(**keys)

  # Mock exec_command to return agent without ISA Info
  mock_output = """Agent 1
  Device Type:                 GPU
  Name:                        gfx908
  Compute Unit:                120
"""
  with patch.object(m, 'connect') as mock_connect:
    mock_cnx = Mock()
    mock_stdout = StringIO(mock_output)
    mock_cnx.exec_command = Mock(return_value=(0, mock_stdout, StringIO()))
    mock_connect.return_value = mock_cnx

    cpus, gpus = m.get_properties()

    # Verify fallback to Name when ISA Info is missing
    assert len(gpus) == 1
    assert gpus[0]['arch'] == 'gfx908'
    assert gpus[0]['arch_full'] == 'gfx908'


def test_write_file_with_filename():
  """Test write_file with explicit filename"""
  keys = {'local_machine': True}
  m = Machine(**keys)

  with tempfile.NamedTemporaryFile(delete=False) as tmp:
    filename = tmp.name

  try:
    contents = b'test content'
    result = m.write_file(contents, filename=filename, is_temp=False)
    assert result == filename
    assert os.path.exists(filename)

    # Verify content
    with open(filename, 'rb') as f:
      assert f.read() == contents
  finally:
    if os.path.exists(filename):
      os.unlink(filename)


def test_remote_write_file():
  """Test write_file on remote machine"""
  keys = {
      'id': 1,
      'hostname': 'test-host',
      'user': 'test-user',
      'password': 'test-pass',
      'port': 22,
      'avail_gpus': '0,1',
      'arch': 'gfx908',
      'num_cu': 120,
      'local_machine': False
  }

  with patch('subprocess.Popen') as mock_popen:
    mock_process = Mock()
    mock_process.stdout = Mock()
    mock_process.stdout.readline = Mock(return_value='test-host\n')
    mock_popen.return_value.__enter__ = Mock(return_value=mock_process)
    mock_popen.return_value.__exit__ = Mock(return_value=False)

    m = Machine(**keys)

    # Mock connection and sftp
    mock_cnx = Mock()
    mock_sftp = Mock()
    mock_file = Mock()
    mock_sftp.open = Mock(return_value=mock_file)
    mock_file.__enter__ = Mock(return_value=mock_file)
    mock_file.__exit__ = Mock(return_value=False)
    mock_cnx.ssh = Mock()
    mock_cnx.ssh.open_sftp = Mock(return_value=mock_sftp)

    with patch.object(m, 'connect', return_value=mock_cnx):
      contents = b'remote content'
      filename = '/tmp/test_file.txt'
      result = m.write_file(contents, filename=filename, is_temp=False)

      assert result == filename
      mock_sftp.open.assert_called_once()


def test_remote_read_file():
  """Test read_file on remote machine"""
  keys = {
      'id': 1,
      'hostname': 'test-host',
      'user': 'test-user',
      'password': 'test-pass',
      'port': 22,
      'avail_gpus': '0,1',
      'arch': 'gfx908',
      'num_cu': 120,
      'local_machine': False
  }

  with patch('subprocess.Popen') as mock_popen:
    mock_process = Mock()
    mock_process.stdout = Mock()
    mock_process.stdout.readline = Mock(return_value='test-host\n')
    mock_popen.return_value.__enter__ = Mock(return_value=mock_process)
    mock_popen.return_value.__exit__ = Mock(return_value=False)

    m = Machine(**keys)

    # Mock connection and sftp
    mock_cnx = Mock()
    mock_sftp = Mock()
    mock_sftp.getfo = Mock(side_effect=lambda fn, io: io.write(b'remote data'))
    mock_cnx.ssh = Mock()
    mock_cnx.ssh.open_sftp = Mock(return_value=mock_sftp)

    with patch.object(m, 'connect', return_value=mock_cnx):
      filename = '/tmp/remote_file.txt'

      # Test byte read
      result_bytes = m.read_file(filename, byteread=True)
      assert result_bytes == b'remote data'

      # Test text read
      result_text = m.read_file(filename, byteread=False)
      assert result_text == 'remote data'


def test_exec_command_remote():
  """Test exec_command on remote machine - tests line 395"""
  keys = {
      'id': 1,
      'hostname': 'test-host',
      'user': 'test-user',
      'password': 'test-pass',
      'port': 22,
      'avail_gpus': '0,1',
      'arch': 'gfx908',
      'num_cu': 120,
      'local_machine': False
  }

  with patch('subprocess.Popen') as mock_popen:
    mock_process = Mock()
    mock_process.stdout = Mock()
    mock_process.stdout.readline = Mock(return_value='test-host\n')
    mock_popen.return_value.__enter__ = Mock(return_value=mock_process)
    mock_popen.return_value.__exit__ = Mock(return_value=False)

    m = Machine(**keys)

    # Mock connection
    mock_cnx = Mock()
    mock_stdout = StringIO('output')
    mock_stderr = StringIO('')
    mock_cnx.exec_command = Mock(return_value=(0, mock_stdout, mock_stderr))

    # Mock DOCKER_CMD with single placeholder to match actual usage at line 395
    with patch('tuna.machine.DOCKER_CMD', 'docker_wrapper {}'):
      with patch.object(m, 'connect', return_value=mock_cnx):
        ret, out, err = m.exec_command('ls -la')

        assert ret == 0
        # Verify the command was wrapped (covers line 395)
        call_args = mock_cnx.exec_command.call_args[0][0]
        assert 'docker_wrapper' in call_args


def test_get_gpu_clock():
  """Test get_gpu_clock parsing"""
  keys = {'local_machine': True}
  m = Machine(**keys)

  # Mock rocm-smi output
  mock_output = """
GPU[0] : sclk level: 7
GPU[0] : mclk level: 3
GPU[1] : sclk level: 5
GPU[1] : mclk level: 2
"""
  mock_cnx = Mock()
  mock_stdout = StringIO(mock_output)
  mock_cnx.exec_command = Mock(return_value=(0, mock_stdout, StringIO()))

  with patch.object(m, 'connect', return_value=mock_cnx):
    result = m.get_gpu_clock(0)
    assert result == (7, 3)

    # Test for GPU 1
    mock_stdout = StringIO(mock_output)
    mock_cnx.exec_command = Mock(return_value=(0, mock_stdout, StringIO()))
    result = m.get_gpu_clock(1)
    assert result == (5, 2)


def test_get_gpu_clock_no_output():
  """Test get_gpu_clock when command returns None"""
  keys = {'local_machine': True}
  m = Machine(**keys)

  mock_cnx = Mock()
  mock_cnx.exec_command = Mock(return_value=(1, None, StringIO()))

  with patch.object(m, 'connect', return_value=mock_cnx):
    result = m.get_gpu_clock(0)
    assert result is False


def test_restart_server_with_ipmi():
  """Test restart_server using IPMI"""
  keys = {
      'id': 1,
      'hostname': 'test-host',
      'user': 'test-user',
      'password': 'test-pass',
      'port': 22,
      'avail_gpus': '0,1',
      'arch': 'gfx908',
      'num_cu': 120,
      'local_machine': False,
      'ipmi_ip': '192.168.1.101',
      'ipmi_port': 623,
      'ipmi_user': 'ipmi_user',
      'ipmi_password': 'ipmi_pass',
      'ipmi_inaccessible': 0
  }

  with patch('subprocess.Popen') as mock_popen:
    mock_process = Mock()
    mock_process.stdout = Mock()
    mock_process.stdout.readline = Mock(return_value='test-host\n')
    mock_popen.return_value.__enter__ = Mock(return_value=mock_process)
    mock_popen.return_value.__exit__ = Mock(return_value=False)

    m = Machine(**keys)
    m.mmi = Mock()
    m.mmi.restart_server = Mock()

    # Test restart with IPMI
    result = m.restart_server(wait=False)
    assert result is True
    m.mmi.restart_server.assert_called_once()


def test_restart_server_without_ipmi():
  """Test restart_server without IPMI (using shell)"""
  keys = {
      'id': 1,
      'hostname': 'test-host',
      'user': 'test-user',
      'password': 'test-pass',
      'port': 22,
      'avail_gpus': '0,1',
      'arch': 'gfx908',
      'num_cu': 120,
      'local_machine': False,
      'ipmi_inaccessible': 1
  }

  with patch('subprocess.Popen') as mock_popen:
    mock_process = Mock()
    mock_process.stdout = Mock()
    mock_process.stdout.readline = Mock(return_value='test-host\n')
    mock_popen.return_value.__enter__ = Mock(return_value=mock_process)
    mock_popen.return_value.__exit__ = Mock(return_value=False)

    m = Machine(**keys)

    mock_cnx = Mock()
    mock_cnx.exec_command = Mock(return_value=(0, StringIO(), StringIO()))

    with patch.object(m, 'connect', return_value=mock_cnx):
      with patch('time.sleep'):
        result = m.restart_server(wait=True)
        assert result is True
        mock_cnx.exec_command.assert_called_with('sudo reboot')


def test_chk_gpu_status_out_of_bounds():
  """Test chk_gpu_status with GPU ID out of bounds"""
  keys = {'local_machine': True}
  m = Machine(**keys)

  # Test with GPU ID not in avail_gpus
  result = m.chk_gpu_status(999)
  assert result is False


def test_chk_gpu_status_no_avail_gpus():
  """Test chk_gpu_status when avail_gpus is None"""
  keys = {'local_machine': True}
  m = Machine(**keys)

  m.avail_gpus = None

  mock_cnx = Mock()
  mock_cnx.exec_command = Mock(return_value=(0, None, StringIO()))

  with patch.object(m, 'connect', return_value=mock_cnx):
    result = m.chk_gpu_status(0)
    assert result is False


def test_chk_gpu_status_stdout_none():
  """Test chk_gpu_status when stdout is None"""
  keys = {'local_machine': True}
  m = Machine(**keys)

  mock_cnx = Mock()
  mock_cnx.exec_command = Mock(return_value=(0, None, StringIO()))

  with patch.object(m, 'connect', return_value=mock_cnx):
    result = m.chk_gpu_status(0)
    assert result is False


def test_chk_gpu_status_rocminfo_failed():
  """Test chk_gpu_status when rocminfo output doesn't match arch"""
  keys = {'local_machine': True}
  m = Machine(**keys)

  # Mock output that doesn't contain the expected arch
  mock_output = "gfx906\n"
  mock_cnx = Mock()
  mock_stdout = StringIO(mock_output)
  mock_cnx.exec_command = Mock(return_value=(0, mock_stdout, StringIO()))

  with patch.object(m, 'connect', return_value=mock_cnx):
    with patch.object(m, 'get_gpu', return_value={'arch': 'gfx908'}):
      result = m.chk_gpu_status(0)
      assert result is False


def test_chk_gpu_status_socket_error():
  """Test chk_gpu_status with socket timeout"""
  keys = {'local_machine': True}
  m = Machine(**keys)

  mock_cnx = Mock()
  mock_stdout = StringIO()

  # Make the iteration raise socket.timeout
  def raise_timeout():
    raise socket.timeout("Connection timeout")

  mock_stdout.__iter__ = lambda self: iter([])
  mock_cnx.exec_command = Mock(side_effect=socket.timeout("Connection timeout"))

  with patch.object(m, 'connect', return_value=mock_cnx):
    result = m.chk_gpu_status(0)
    assert result is False


def test_chk_gpu_status_empty_output():
  """Test chk_gpu_status when rocminfo returns no output"""
  keys = {'local_machine': True}
  m = Machine(**keys)

  mock_cnx = Mock()
  mock_stdout = StringIO("")  # Empty output
  mock_cnx.exec_command = Mock(return_value=(0, mock_stdout, StringIO()))

  with patch.object(m, 'connect', return_value=mock_cnx):
    result = m.chk_gpu_status(0)
    assert result is False


def test_getusedspace_remote():
  """Test getusedspace on remote machine"""
  keys = {
      'id': 1,
      'hostname': 'test-host',
      'user': 'test-user',
      'password': 'test-pass',
      'port': 22,
      'avail_gpus': '0,1',
      'arch': 'gfx908',
      'num_cu': 120,
      'local_machine': False
  }

  with patch('subprocess.Popen') as mock_popen:
    mock_process = Mock()
    mock_process.stdout = Mock()
    mock_process.stdout.readline = Mock(return_value='test-host\n')
    mock_popen.return_value.__enter__ = Mock(return_value=mock_process)
    mock_popen.return_value.__exit__ = Mock(return_value=False)

    m = Machine(**keys)

    # Mock df command output
    df_output = "/dev/sda1  50G  25G  23G  53% /"
    mock_cnx = Mock()
    mock_stdout = StringIO(df_output)
    mock_cnx.exec_command = Mock(return_value=(0, mock_stdout, StringIO()))

    with patch.object(m, 'connect', return_value=mock_cnx):
      result = m.getusedspace()
      assert result == 53


def test_getusedspace_remote_no_output():
  """Test getusedspace on remote machine when df returns None"""
  keys = {
      'id': 1,
      'hostname': 'test-host',
      'user': 'test-user',
      'password': 'test-pass',
      'port': 22,
      'avail_gpus': '0,1',
      'arch': 'gfx908',
      'num_cu': 120,
      'local_machine': False
  }

  with patch('subprocess.Popen') as mock_popen:
    mock_process = Mock()
    mock_process.stdout = Mock()
    mock_process.stdout.readline = Mock(return_value='test-host\n')
    mock_popen.return_value.__enter__ = Mock(return_value=mock_process)
    mock_popen.return_value.__exit__ = Mock(return_value=False)

    m = Machine(**keys)

    mock_cnx = Mock()
    mock_cnx.exec_command = Mock(return_value=(1, None, StringIO()))

    with patch.object(m, 'connect', return_value=mock_cnx):
      result = m.getusedspace()
      assert result is None


def test_exec_command_list():
  """Test exec_command with list argument"""
  keys = {'local_machine': True}
  m = Machine(**keys)

  command_list = ['ls', '-la', '/tmp']

  mock_cnx = Mock()
  mock_stdout = StringIO('output')
  mock_stderr = StringIO('')
  mock_cnx.exec_command = Mock(return_value=(0, mock_stdout, mock_stderr))

  with patch.object(m, 'connect', return_value=mock_cnx):
    ret, out, err = m.exec_command(command_list)

    # Verify list was joined into string
    call_args = mock_cnx.exec_command.call_args[0][0]
    assert isinstance(call_args, str)
    assert 'ls' in call_args


def test_make_temp_file():
  """Test make_temp_file method"""
  keys = {'local_machine': True}
  m = Machine(**keys)

  tmpfile = m.make_temp_file()
  assert os.path.exists(tmpfile)
  os.unlink(tmpfile)


def test_remote_machine_with_qts():
  """Test remote machine init with QTS check - covers lines 132-133"""
  keys = {
      'id': 1,
      'hostname': 'test-host',
      'user': 'test-user',
      'password': 'test-pass',
      'port': 22,
      'local_ip': '192.168.1.100',
      'local_port': 2222,
      'avail_gpus': '0,1',
      'arch': 'gfx908',
      'num_cu': 120,
      'local_machine': False
  }

  with patch('subprocess.Popen') as mock_popen:
    mock_process = Mock()
    mock_process.stdout = Mock()
    # Return a hostname that will trigger QTS check
    mock_process.stdout.readline = Mock(return_value='qts-hostname\n')
    mock_popen.return_value.__enter__ = Mock(return_value=mock_process)
    mock_popen.return_value.__exit__ = Mock(return_value=False)

    with patch('tuna.machine.check_qts', return_value=True):
      m = Machine(**keys)

      # Verify that local_ip was used (lines 132-133)
      assert m.hostname == '192.168.1.100'
      assert m.port == 2222


def test_chk_gpu_status_in_bounds_but_fails():
  """Test chk_gpu_status when GPU is in bounds - covers line 471"""
  keys = {'local_machine': True}
  m = Machine(**keys)

  # Set avail_gpus explicitly
  m.avail_gpus = [0, 1, 2, 3]

  # Mock connection that returns output without the expected arch
  mock_cnx = Mock()
  mock_stdout = StringIO("gfx906\n")  # Wrong arch
  mock_cnx.exec_command = Mock(return_value=(0, mock_stdout, StringIO()))

  with patch.object(m, 'connect', return_value=mock_cnx):
    with patch.object(m, 'get_gpu', return_value={'arch': 'gfx908'}):
      # Use GPU ID 2 which is in bounds
      result = m.chk_gpu_status(2)
      # Should still fail due to arch mismatch
      assert result is False


if __name__ == '__main__':
  test_remote_machine_init()
  test_get_avail_gpus_empty()
  test_get_gpu_out_of_bounds()
  test_get_gpu_no_gpus()
  test_parse_agents_keyerror()
  test_write_file_with_filename()
  test_remote_write_file()
  test_remote_read_file()
  test_exec_command_remote()
  test_get_gpu_clock()
  test_get_gpu_clock_no_output()
  test_restart_server_with_ipmi()
  test_restart_server_without_ipmi()
  test_chk_gpu_status_out_of_bounds()
  test_chk_gpu_status_no_avail_gpus()
  test_chk_gpu_status_stdout_none()
  test_chk_gpu_status_rocminfo_failed()
  test_chk_gpu_status_socket_error()
  test_chk_gpu_status_empty_output()
  test_getusedspace_remote()
  test_getusedspace_remote_no_output()
  test_exec_command_list()
  test_make_temp_file()
  test_remote_machine_with_qts()
  test_chk_gpu_status_in_bounds_but_fails()
  print("All extended machine tests passed!")
