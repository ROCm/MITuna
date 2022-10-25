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

import os
import socket
from tuna.utils.utility import arch2targetid
from tuna.utils.utility import check_qts
from tuna.machine import Machine
from tuna.utils.logger import setup_logger
from tuna.utils.utility import get_env_vars
from tuna.utils.utility import get_mmi_env_vars

LOGGER = setup_logger('utility')


def test_utility():
  test_arch2targetid
  test_check_qts
  test_get_env_vars
  test_get_mmi_env_vars


def test_arch2targetid():
  arch_value = arch2targetid('gfx1030')
  assert (arch_value == "gfx1030")

  arch = 'gfx900'
  arch_value = arch2targetid(arch)
  assert (arch_value == f"{arch}:xnack-")

  arch = 'gfx908'
  arch_value = arch2targetid(arch)
  assert (arch_value == f"{arch}:sram-ecc+:xnack-")

  arch = 'gfx906'
  arch_value = arch2targetid(arch)
  assert (arch_value == f"{arch}:sram-ecc+:xnack-")


def test_check_qts():

  hostname = socket.gethostname()
  m = Machine(hostname=hostname, local_machine=True)
  retvalue = check_qts(hostname, logger=LOGGER)
  print(retvalue)
  assert (retvalue == False)

  m = Machine(hostname=hostname, local_machine=True)
  retvalue = check_qts(hostname, logger=LOGGER)
  print(retvalue)
  assert (retvalue == False)

  retvalue = check_qts('192.0.2.0')
  print(retvalue)
  assert (retvalue == False)

  retvalue = check_qts('198.51.100.0')
  print(bool(retvalue))
  assert (retvalue == False)


def test_get_env_vars():

  os.environ['user_name'] = 'xyz_123'
  os.environ['user_password'] = 'xyz1234'
  os.environ['db_hostname'] = 'xyz.test.com'
  os.environ['db_name'] = 'testdb'

  assert 'xyz_123' == (os.environ['user_name'])
  assert 'xyz1234' == (os.environ['user_password'])
  assert 'xyz.test.com' == (os.environ['db_hostname'])
  assert 'testdb' == (os.environ['db_name'])


def test_get_mmi_env_vars():

  os.environ['gateway_ip'] = '10.100.00.000'
  os.environ['gateway_port'] = '1234'
  os.environ['gateway_user'] = 'xyz'

  assert '10.100.00.000' == os.environ['gateway_ip']
  assert '1234' == os.environ['gateway_port']
  assert 'xyz' == os.environ['gateway_user']
