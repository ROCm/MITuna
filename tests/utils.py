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

from multiprocessing import Value

#from tuna.worker_interface import WorkerInterface
from tuna.miopen.worker.fin_class import FinClass
from tuna.miopen.db.session import Session
from tuna.machine import Machine
from tuna.miopen.utils.config_type import ConfigType
from tuna.miopen.db.find_db import ConvolutionFindDB
from tuna.miopen.miopen_lib import MIOpen

# TODO: This is a copy and is unacceptable
sqlite_config_cols = [
    'layout', 'direction', 'data_type', 'spatial_dim', 'in_channels', 'in_h',
    'in_w', 'in_d', 'fil_h', 'fil_w', 'fil_d', 'out_channels', 'batchsize',
    'pad_h', 'pad_w', 'pad_d', 'conv_stride_h', 'conv_stride_w',
    'conv_stride_d', 'dilation_h', 'dilation_w', 'dilation_d', 'bias',
    'group_count'
]

sqlite_perf_db_cols = ["solver", "config", "arch", "num_cu", "params"]

#valid_arch_cu = [("gfx803", 36), ("gfx803", 64), ("gfx900", 56), ("gfx900", 64),
#                 ("gfx906", 60), ("gfx906", 64), ("gfx908", 120),
#                 ("gfx1030", 36)]


def get_sqlite_table(cnx, table_name):
  query = "SELECT * from {}".format(table_name)
  c = cnx.cursor()
  c.execute(query)
  rows = c.fetchall()
  columns = [x[0] for x in c.description]
  return rows, columns


class DummyArgs(object):
  """Dummy args object class to be used for testing"""

  # pylint: disable=too-many-instance-attributes

  def __init__(self, **kwargs):
    """Constructor"""
    pass


class CfgImportArgs():
  config_type = ConfigType.convolution
  command = None
  batches = None
  batch_list = []
  file_name = None
  mark_recurrent = False
  tag = None
  tag_only = False


class LdJobArgs():
  config_type = ConfigType.convolution,
  tag = None
  all_configs = False
  algo = None
  solvers = [('', None)]
  only_app = False
  tunable = False
  cmd = None
  label = None
  fin_steps = None
  session_id = None
  only_dynamic = False


class GoFishArgs():
  local_machine = True
  fin_steps = None
  session_id = None
  arch = None
  num_cu = None
  machines = None
  restart_machine = None
  update_applicability = None
  find_mode = None
  blacklist = None
  update_solvers = None
  config_type = None
  reset_interval = None
  dynamic_solvers_only = False
  label = 'pytest'
  docker_name = 'miopentuna'
  ticket = 'N/A'
  solver_id = None
  find_mode = 1
  blacklist = None
  init_session = True
  check_status = True


class ExampleArgs():
  arch = 'gfx90a'
  num_cu = 104
  local_machine = True
  remote_machine = False
  session_id = None
  machines = None
  restart_machine = None
  reset_interval = None
  label = 'pytest_example'
  docker_name = 'miopentuna'
  init_session = True
  ticket = 'N/A'


def get_worker_args(args, machine, miopen):
  worker_ids = range(machine.get_num_cpus())
  f_vals = miopen.get_f_vals(machine, worker_ids)
  kwargs = miopen.get_kwargs(0, f_vals)
  return kwargs


def add_test_session(arch='gfx90a', num_cu=104, label=None):
  args = GoFishArgs()
  if label:
    args.label = label
  machine = Machine(local_machine=True)
  machine.arch = arch
  machine.num_cu = num_cu

  #create a session
  miopen = MIOpen()
  miopen.args = args
  kwargs = get_worker_args(args, machine, miopen)
  worker = FinClass(**kwargs)
  session_id = Session().add_new_session(args, worker)
  assert (session_id)
  return session_id


def build_fdb_entry(session_id):
  fdb_entry = ConvolutionFindDB()
  fdb_entry.config = 1
  fdb_entry.solver = 1
  fdb_entry.session = session_id
  fdb_entry.opencl = False

  fdb_entry.fdb_key = 'key'
  fdb_entry.alg_lib = 'Test'
  fdb_entry.params = 'param'
  fdb_entry.workspace_sz = 0
  fdb_entry.valid = True
  fdb_entry.kernel_time = 11111
  fdb_entry.kernel_group = 1

  return fdb_entry


class CfgEntry:
  valid = 1

  def __init__(self):
    self.direction = 'B'
    self.out_channels = 10
    self.in_channels = 5
    self.in_w = 8
    self.conv_stride_w = 1
    self.fil_w = 3
    self.pad_w = 0
    self.in_h = 8
    self.conv_stride_h = 1
    self.fil_h = 3
    self.pad_h = 0
    self.spatial_dim = 3
    self.in_d = 8
    self.conv_stride_d = 1
    self.fil_d = 3
    self.pad_d = 0

  def to_dict(self):
    return vars(self)


class TensorEntry:

  def __init__(self):
    self.id = 1
    self.tensor_id_1 = 'cfg_value_1'
    self.tensor_id_2 = 'cfg_value_2'

  def to_dict(self, ommit_valid=False):
    return vars(self)
