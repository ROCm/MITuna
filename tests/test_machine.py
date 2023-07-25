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


def config_cpus(m):
  for cpu in m.cpus:
    assert (cpu['rinfo']['Device Type'] == 'CPU')
  m.getusedspace()


def config_gpus(m):
  for i, gpu in enumerate(m.gpus):
    assert (gpu == m.get_gpu(i))
    assert (gpu['rinfo']['Device Type'] == 'GPU')
    assert (m.chk_gpu_status(i))
    m.get_gpu_clock(i)
    #print('{}: {}'.format(i, m.chk_gpu_status(i)))


def write_read_bytes(m):
  contents = bytes('8756abd', 'utf-8')
  tmpfile = m.write_file(contents, is_temp=True)
  retval = m.read_file(tmpfile, byteread=True)
  assert (contents == retval)


def test_machine():
  keys = {'local_machine': True}

  m = Machine(**keys)

  config_cpus(m)
  config_gpus(m)

  write_read_bytes(m)
