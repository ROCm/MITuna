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
from tuna.utils.logger import setup_logger
from tuna.utils.utility import SimpleDict
from tuna.utils.utility import get_env_vars, get_mmi_env_vars, arch2targetid
from tuna.utils.db_utility import build_dict_val_key

LOGGER = setup_logger('utility')


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


def test_get_env_vars():
  # set the env variable to test data
  os.environ['TUNA_DB_USER_NAME'] = 'xyz_123'
  os.environ['TUNA_DB_USER_PASSWORD'] = 'xyz1234'
  os.environ['TUNA_DB_HOSTNAME'] = 'xyz.test.com'
  os.environ['TUNA_DB_NAME'] = 'testdb'

  ENV_VARS = get_env_vars()

  assert 'xyz_123' == (ENV_VARS['user_name'])
  assert 'xyz1234' == (ENV_VARS['user_password'])
  assert 'xyz.test.com' == (ENV_VARS['db_hostname'])
  assert 'testdb' == (ENV_VARS['db_name'])


def test_get_mmi_env_vars():
  # set the env variable to test data
  os.environ['gateway_ip'] = '10.100.00.000'
  os.environ['gateway_port'] = '1234'
  os.environ['gateway_user'] = 'xyz'

  ENV_VARS = get_mmi_env_vars()

  assert '10.100.00.000' == (ENV_VARS['gateway_ip'])
  assert '1234' == (ENV_VARS['gateway_port'])
  assert 'xyz' == (ENV_VARS['gateway_user'])

def test_key_builder():
  keyset = SimpleDict()
  keyset.setattr('d', 3)
  keyset.setattr('e', 4)
  keyset.setattr('f', 5)

  keystr = build_dict_val_key(keyset)
  assert keystr == '3-4-5'

  build_dict_val_key(keyset, ['e'])
  assert keystr == '3-5'

  keyset.setattr('a', 1)
  keystr = build_dict_val_key(keyset)
  assert keystr == '1-3-4-5'
