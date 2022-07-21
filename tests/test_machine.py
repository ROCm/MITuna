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

sys.path.append("../tuna")
sys.path.append("tuna")

from tuna.machine import Machine
from tuna.sql import DbCursor


def config_cpus(m):
  for cpu in m.cpus:
    assert (cpu['rinfo']['Device Type'] == 'CPU')
  m.getusedspace()


def config_gpus(m):
  for i, gpu in enumerate(m.gpus):
    assert (gpu['rinfo']['Device Type'] == 'GPU')
    assert (m.chk_gpu_status(i))
    m.get_gpu_clock(i)
    #print('{}: {}'.format(i, m.chk_gpu_status(i)))


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
        'port': port,
        'arch': arch,
        'num_cu': num_cu,
        'avail_gpus': avail_gpus,
        'sclk': sclk,
        'mclk': mclk,
        'ipmi_ip': ipmi_ip,
        'ipmi_port': ipmi_port,
        'ipmi_user': ipmi_user,
        'ipmi_password': ipmi_password,
        'ipmi_inaccessible': ipmi_inaccessible
    }

  m = Machine(**keys)

  config_cpus(m)
  config_gpus(m)
