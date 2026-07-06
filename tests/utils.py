#############################################################################
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
import sys
import copy
from multiprocessing import Value

sys.path.append("../tuna")
sys.path.append("tuna")

this_path = os.path.dirname(__file__)

from tuna.miopen.db.session import Session
from tuna.miopen.utils.config_type import ConfigType
from tuna.miopen.db.find_db import ConvolutionFindDB
from tuna.miopen.miopen_lib import MIOpen
from tuna.miopen.db.solver import get_solver_ids
from tuna.utils.logger import setup_logger
from tuna.miopen.utils.metadata import ALG_SLV_MAP
from tuna.utils.db_utility import connect_db
from tuna.miopen.subcmd.import_configs import import_cfgs
from tuna.miopen.subcmd.load_job import add_jobs
from tuna.utils.machine_utility import load_machines
from tuna.machine import Machine
from tuna.miopen.utils.lib_helper import get_worker
from tuna.miopen.worker.fin_class import FinClass
from tuna.miopen.db.tables import MIOpenDBTables

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
  rich_data = False
  label = 'pytest'
  docker_name = 'miopentuna'
  ticket = 'N/A'
  solver_id = None
  find_mode = 1
  blacklist = None
  init_session = True
  check_status = True
  subcommand = None
  shutdown_workers = None


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


def add_test_session(arch='gfx90a',
                     num_cu=104,
                     label=None,
                     session_table=Session):
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
  session_id = session_table().add_new_session(args, worker)
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


def add_cfgs(tag, filename, logger_name):
  #import configs
  args = CfgImportArgs()
  args.tag = tag
  args.mark_recurrent = True
  args.file_name = f"{this_path}/../utils/configs/{filename}"

  dbt = MIOpenDBTables(config_type=args.config_type)
  counts = import_cfgs(args, dbt, setup_logger(logger_name))
  return dbt


def add_test_jobs(miopen,
                  session_id,
                  dbt,
                  label,
                  tag,
                  fin_steps,
                  logger_name,
                  algo=None):
  machine_lst = load_machines(miopen.args)
  machine = machine_lst[0]
  #update solvers
  kwargs = get_worker_args(miopen.args, machine, miopen)
  fin_worker = FinClass(**kwargs)
  assert (fin_worker.get_solvers())

  #get applicability
  dbt = add_cfgs(label, 'conv_configs_NCHW.txt', label)
  miopen.args.update_applicability = True
  worker_lst = miopen.compose_worker_list(machine_lst)
  for worker in worker_lst:
    worker.join()
  #load jobs
  args = LdJobArgs
  args.label = label
  args.tag = tag
  args.fin_steps = fin_steps
  args.session_id = session_id
  logger = setup_logger(logger_name)

  #limit job scope
  if algo:
    args.algo = algo
    solver_arr = ALG_SLV_MAP[args.algo]
    solver_id_map = get_solver_ids()
    if solver_arr:
      solver_ids = []
      for solver in solver_arr:
        sid = solver_id_map.get(solver, None)
        solver_ids.append((solver, sid))
      args.solvers = solver_ids
    args.only_applicable = True

  connect_db()
  return add_jobs(args, dbt, logger)


# ============================================================================
# Additional Test Helpers for Enhanced Testing
# ============================================================================


def create_test_config_dict(**kwargs):
  """
  Factory function to create test configuration dictionaries with defaults.
  
  Args:
      **kwargs: Override default configuration values
      
  Returns:
      dict: Configuration dictionary with merged values
  """
  defaults = {
      'batchsize': 256,
      'spatial_dim': 2,
      'in_channels': 128,
      'in_h': 28,
      'in_w': 28,
      'in_d': 1,
      'fil_h': 3,
      'fil_w': 3,
      'fil_d': 1,
      'out_channels': 128,
      'pad_h': 1,
      'pad_w': 1,
      'pad_d': 0,
      'conv_stride_h': 1,
      'conv_stride_w': 1,
      'conv_stride_d': 0,
      'dilation_h': 1,
      'dilation_w': 1,
      'dilation_d': 0,
      'group_count': 1,
      'in_layout': 'NCHW',
      'fil_layout': 'NCHW',
      'out_layout': 'NCHW',
      'data_type': 'FP32',
      'direction': 'F',
  }
  defaults.update(kwargs)
  return defaults


def create_test_job_dict(**kwargs):
  """
  Factory function to create test job dictionaries with defaults.
  
  Args:
      **kwargs: Override default job values
      
  Returns:
      dict: Job dictionary with merged values
  """
  defaults = {
      'id': 1,
      'config': 1,
      'solver': 1,
      'session': 1,
      'state': 'new',
      'valid': 1,
      'reason': None,
      'retries': 0,
  }
  defaults.update(kwargs)
  return defaults


def create_test_solver_dict(**kwargs):
  """
  Factory function to create test solver dictionaries with defaults.
  
  Args:
      **kwargs: Override default solver values
      
  Returns:
      dict: Solver dictionary with merged values
  """
  defaults = {
      'id': 1,
      'solver': 'ConvAsm1x1U',
      'tunable': True,
      'dynamic': False,
  }
  defaults.update(kwargs)
  return defaults


def assert_config_equal(config1, config2, ignore_fields=None):
  """
  Assert that two configuration objects/dicts are equal, optionally ignoring fields.
  
  Args:
      config1: First configuration (dict or object with to_dict method)
      config2: Second configuration (dict or object with to_dict method)
      ignore_fields: List of field names to ignore in comparison
  """
  if hasattr(config1, 'to_dict'):
    config1 = config1.to_dict()
  if hasattr(config2, 'to_dict'):
    config2 = config2.to_dict()

  ignore_fields = ignore_fields or []

  for key in config1:
    if key not in ignore_fields:
      assert key in config2, f"Key '{key}' not found in config2"
      assert config1[key] == config2[key], \
          f"Mismatch for key '{key}': {config1[key]} != {config2[key]}"


def assert_job_state(session, job_id, expected_state):
  """
  Assert that a job has the expected state.
  
  Args:
      session: Database session
      job_id: Job ID to check
      expected_state: Expected job state
  """
  from tuna.miopen.db.convolutionjob_tables import ConvolutionJob
  job = session.query(ConvolutionJob).filter(ConvolutionJob.id == job_id).one()
  assert job.state == expected_state, \
      f"Job {job_id} has state '{job.state}', expected '{expected_state}'"


def create_mock_args(**kwargs):
  """
  Create a mock arguments object for testing.
  
  Args:
      **kwargs: Attribute values for the mock args
      
  Returns:
      Mock args object with specified attributes
  """
  from unittest.mock import MagicMock

  args = MagicMock()
  defaults = {
      'arch': 'gfx90a',
      'num_cu': 110,
      'config_type': ConfigType.convolution,
      'session_id': 1,
      'label': 'test_session',
      'docker_name': 'test_docker',
      'version': '1.0.0',
      'machines': None,
      'local_machine': True,
  }
  defaults.update(kwargs)

  for key, value in defaults.items():
    setattr(args, key, value)

  return args


def count_table_rows(session, table_class):
  """
  Count rows in a database table.
  
  Args:
      session: Database session
      table_class: SQLAlchemy table class
      
  Returns:
      int: Number of rows in table
  """
  return session.query(table_class).count()


def cleanup_test_data(session, table_class, filter_func=None):
  """
  Clean up test data from a table.
  
  Args:
      session: Database session
      table_class: SQLAlchemy table class
      filter_func: Optional function to filter which rows to delete
  """
  query = session.query(table_class)
  if filter_func:
    query = query.filter(filter_func(table_class))
  query.delete(synchronize_session=False)
  session.commit()


def generate_driver_commands(num_commands=5, cmd_type='conv'):
  """
  Generate a list of driver commands for testing.
  
  Args:
      num_commands: Number of commands to generate
      cmd_type: Type of command ('conv' or 'bnorm')
      
  Returns:
      List of driver command strings
  """
  commands = []

  if cmd_type == 'conv':
    for i in range(num_commands):
      batchsize = 256 * (i + 1)
      channels = 64 * (i + 1)
      cmd = (f"./bin/MIOpenDriver conv --pad_h 1 --pad_w 1 "
             f"--out_channels {channels} --fil_w 3 --fil_h 3 "
             f"--dilation_w 1 --dilation_h 1 --conv_stride_w 1 "
             f"--conv_stride_h 1 --in_channels {channels} --in_w 28 "
             f"--in_h 28 --batchsize {batchsize} --group_count 1 "
             f"--forw 1 --in_layout NCHW -V 0")
      commands.append(cmd)
  elif cmd_type == 'bnorm':
    for i in range(num_commands):
      batchsize = 256 * (i + 1)
      channels = 64 * (i + 1)
      cmd = (f"./bin/MIOpenDriver bnorm -n {batchsize} -c {channels} "
             f"-H 56 -W 56 -m 1 --forw 1 -b 0 -s 1 -r 1")
      commands.append(cmd)

  return commands


def create_temp_config_file(temp_dir, commands):
  """
  Create a temporary configuration file with driver commands.
  
  Args:
      temp_dir: Directory path for temporary file
      commands: List of driver commands
      
  Returns:
      Path to created file
  """
  import os
  file_path = os.path.join(temp_dir, 'test_configs.txt')
  with open(file_path, 'w') as f:
    for cmd in commands:
      f.write(cmd + '\n')
  return file_path


def validate_fdb_entry(fdb_entry, required_fields=None):
  """
  Validate that an FDB entry has required fields.
  
  Args:
      fdb_entry: Find database entry to validate
      required_fields: List of required field names
      
  Returns:
      bool: True if valid, False otherwise
  """
  required_fields = required_fields or [
      'config', 'solver', 'fdb_key', 'params', 'session'
  ]

  for field in required_fields:
    if not hasattr(fdb_entry, field):
      return False
    if getattr(fdb_entry, field) is None:
      return False

  return True


def compare_driver_objects(driver1, driver2, ignore_fields=None):
  """
  Compare two driver objects for equality.
  
  Args:
      driver1: First driver object
      driver2: Second driver object
      ignore_fields: List of fields to ignore
      
  Returns:
      bool: True if equal, False otherwise
  """
  ignore_fields = ignore_fields or ['id', 'created_date']

  dict1 = driver1.to_dict() if hasattr(driver1, 'to_dict') else vars(driver1)
  dict2 = driver2.to_dict() if hasattr(driver2, 'to_dict') else vars(driver2)

  for key in dict1:
    if key in ignore_fields:
      continue
    if key not in dict2:
      return False
    if dict1[key] != dict2[key]:
      return False

  return True
