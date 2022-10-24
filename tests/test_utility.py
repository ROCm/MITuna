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

  retvalue = check_qts('198.51.100.0', False)
  print(bool(retvalue))
  assert (retvalue == True)


def test_get_env_vars():
  env_vars = get_env_vars()

  assert 'xyz_123' == (env_vars['user_name'])
  assert 'xyz1234' == (env_vars['user_password'])
  assert 'xyz.test.com' == (env_vars['db_hostname'])
  assert 'testdb' == (env_vars['db_name'])


def test_get_mmi_env_vars():
  env_vars = get_mmi_env_vars()

  assert '10.100.00.000' == env_vars['gateway_ip']
  assert '1234' == env_vars['gateway_port']
  assert 'xyz' == env_vars['gateway_user']
