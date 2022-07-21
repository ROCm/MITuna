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

import sys
import pytest

sys.path.append("../tuna")
sys.path.append("tuna")

from tuna.connection import Connection
from tuna.sql import DbCursor


def commands(cnx):
  assert (cnx.check_binary('ls'))

  cmd = 'ENVVAR=1 TWOVAR=2 ls -al -h'
  bin_str = cnx.get_bin_str(cmd)
  assert (bin_str == 'ls')

  _, o, _ = cnx.exec_command(cmd)
  assert (o is not None)

  cmd2 = 'ENVVAR=1 TWOVAR=2 ls -al -h | flala'

  with pytest.raises(Exception):
    _, o, _ = cnx.exec_command(cmd2)

  cmd3 = 'ENVVAR=1 TWOVAR=2 ls -al -h | ls'
  _, o, _ = cnx.exec_command(cmd3)
  assert (o is not None)


def test_machine():
  res = None
  with DbCursor() as cur:
    select_text = "SELECT id, hostname, avail_gpus, user, password, port, arch, num_cu, sclk, mclk, ipmi_ip, ipmi_port, ipmi_user, ipmi_password, ipmi_inaccessible FROM machine WHERE available = TRUE LIMIT 1"
    cur.execute(select_text)
    res = cur.fetchall()
  assert (len(res) > 0)

  keys = {}
  for machine_id, hostname, avail_gpus, user, password, port, arch, num_cu, sclk, mclk, ipmi_ip, ipmi_port, ipmi_user, ipmi_password, ipmi_inaccessible in res:

    keys = {
        'id': machine_id,
        'hostname': hostname,
        'user': user,
        'password': password,
        'port': port
    }

  keys['local_machine'] = True
  cnx1 = Connection(**keys)

  keys['local_machine'] = False
  cnx2 = Connection(**keys)

  commands(cnx1)

  commands(cnx2)
