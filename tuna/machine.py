#!/usr/bin/env python3
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
"""class for maintaining machine characteristics and interactions"""

import os
import socket
from time import sleep
from io import BytesIO
import tempfile
from subprocess import Popen, PIPE
from sqlalchemy import Text, Column, orm
from sqlalchemy.dialects.mysql import TINYINT, INTEGER

from tuna.machine_management_interface import MachineManagementInterface
from tuna.utils.logger import setup_logger
from tuna.connection import Connection
from tuna.dbBase.base_class import BASE
from tuna.abort import chk_abort_file
from tuna.utils.utility import check_qts
from tuna.metadata import DOCKER_CMD, LOG_TIMEOUT

ROCMINFO = '/opt/rocm/bin/rocminfo'
ROCMSMI = '/opt/rocm/bin/rocm-smi'
CLINFO = '/opt/rocm/opencl/bin/clinfo'


class Machine(BASE):  #pylint: disable=too-many-instance-attributes
  """class for maintaining machine characteristics and interactions """
  __tablename__ = "machine"
  hostname = Column(Text, nullable=False)
  port = Column(INTEGER(11, unsigned=True), nullable=False, server_default="22")
  local_ip = Column(Text, nullable=True)
  local_port = Column(INTEGER, server_default="22")
  user = Column(Text, nullable=False)
  password = Column(Text, nullable=False)
  avail_gpus = Column(Text, nullable=False)
  arch = Column(Text, nullable=False)
  num_cu = Column(INTEGER, nullable=False, server_default="64")
  sclk = Column(INTEGER)
  mclk = Column(INTEGER)
  available = Column(TINYINT(1), server_default="0")
  remarks = Column(Text)
  ipmi_inaccessible = Column(TINYINT, server_default="0")
  ipmi_ip = Column(Text)
  ipmi_port = Column(INTEGER(40, unsigned=True))
  ipmi_user = Column(Text)
  ipmi_password = Column(Text)

  @orm.reconstructor
  def __init__(self, **kwargs):
    #for the sake of pylint, this is explicitly populated
    allowed_keys = set([
        'id', 'hostname', 'user', 'password', 'port', 'ipmi_ip', 'ipmi_port',
        'ipmi_user', 'ipmi_password', 'ipmi_inaccessible', 'sclk', 'mclk',
        'arch', 'num_cu', 'avail_gpus', 'local_machine'
    ])
    self.__dict__.update(
        (key, None) for key in allowed_keys if key not in self.__dict__)
    self.__dict__.update(
        (key, value) for key, value in kwargs.items() if key in allowed_keys)

    self.cnx_list = {}
    self.log_list = {}
    self.num_cpus = 0
    if self.local_machine:
      self.logger = setup_logger('Machine_{}'.format(self.hostname))
      self.connect()
      self.mmi = None
      self.id = 0  # pylint: disable=invalid-name
      self.get_properties()

      if self.gpus:
        self.arch = self.gpus[0]['arch']
        self.num_cu = self.gpus[0]['num_cu']
        self.avail_gpus = list(range(len(self.gpus)))
    else:
      cmd = 'hostname'
      subp = Popen(cmd, stdout=PIPE, shell=True, universal_newlines=True)
      hostname = subp.stdout.readline().strip()
      if self.local_ip is not None and check_qts(hostname):
        self.hostname = self.local_ip
        self.port = self.local_port
      self.logger = setup_logger('Machine_{}'.format(self.id))
      self.mmi = MachineManagementInterface(self.ipmi_ip, self.ipmi_port,
                                            self.ipmi_user, self.ipmi_password)

      if not self.avail_gpus is None:
        self.avail_gpus = [int(val) for val in self.avail_gpus.split(',')]
        self.num_gpus = len(self.avail_gpus)
      self.cpus = []
      self.gpus = []
      #self.get_properties()
      #self.avail_gpus = range(self.num_gpus)

    self.logger.info("avail gpus: %s", self.avail_gpus)

  def set_logger(self, logger):
    """set logging for machine, use this to associate the machine with a subprocess"""
    pid = os.getpid()
    self.log_list[pid] = logger
    self.logger.info('Set logger for process %u', pid)
    return True

  def get_logger(self):
    """return the logger for the current process"""
    pid = os.getpid()
    if pid in self.log_list:
      return self.log_list[pid]

    #self.logger.warning(
    #    'No logger set for this pid (%u), using default logging', pid)
    return self.logger

  def connect(self, abort=None):
    """get the connection for the current process, or create a new one"""
    logger = self.get_logger()

    pid = os.getpid()
    if pid in self.cnx_list:
      return self.cnx_list[pid]

    logger.info('No connection for process %u, creating now', pid)
    # JD: Create a local connection wrapping local process shell
    keys = {
        'id': self.id,
        'hostname': self.hostname,
        'user': self.user,
        'password': self.password,
        'port': self.port,
        'local_machine': self.local_machine,
        'chk_abort_file': chk_abort_file
    }
    keys['logger'] = logger
    keys['chk_abort_file'] = abort
    connection = Connection(**keys)
    self.cnx_list[pid] = connection

    return connection

  def get_num_cpus(self):
    """return number of available cpus"""
    _, stdout, _ = self.connect().exec_command('nproc')
    self.num_cpus = int(stdout.readline())

    return self.num_cpus

  def get_avail_gpus(self):
    """return list of available gpus"""
    if not self.avail_gpus:
      if not self.gpus:
        self.get_properties()
        self.avail_gpus = range(len(self.gpus))
        self.num_gpus = len(self.avail_gpus)
    return self.avail_gpus

  def get_gpu(self, idx):
    """return gpu details"""
    if not self.gpus:
      self.get_properties()
    if idx >= len(self.gpus):
      return None

    return self.gpus[idx]

  def get_cpus(self):
    """return cpu details array"""
    if not self.cpus:
      self.get_properties()

    return self.cpus

  def parse_agents(self):  #pylint: disable=too-many-locals
    #pylint: disable=too-many-branches
    """create agent dictionary from rocminfo"""
    _, stdout, _ = self.connect().exec_command(ROCMINFO)

    agent = None
    agents = {}
    stack = []
    stack.append(agents)
    for line in stdout:
      decoded_line = line.strip()  # lines.strip().decode()
      indent = 0
      if decoded_line:
        indent = line.find(decoded_line[0])

      if 'Agent ' in decoded_line:
        agent = int(decoded_line.split(' ')[1])
        agents[agent] = {}
        sub = agents[agent]
        last_indent = None
        last_div = agents
        continue
      if indent == 0:
        continue

      if agent:
        if last_indent and indent > last_indent:
          stack.append(sub)
          sub = last_div
        elif last_indent and indent < last_indent:
          num_levels = int((last_indent - indent) / 2)
          for _ in range(num_levels):
            sub = stack.pop()

        if ':' in decoded_line:
          cols = decoded_line.split(':')
          field = cols[0].strip()
          val = cols[1].strip()
          if val == '':
            sub[field] = {}
            last_div = sub[field]
          else:
            sub[field] = val
        else:
          arr = decoded_line.split(' ', 1)
          if arr[0] in ('x', 'y', 'z'):
            sub[arr[0]] = arr[1].strip()
          else:
            field = decoded_line.strip()
            sub[field] = {}
            last_div = sub[field]

        last_indent = indent

    return agents

  def get_properties(self):
    """return cpu and gpu device info as dicts"""
    agents = self.parse_agents()

    self.cpus = []
    self.gpus = []

    if not agents:  # on a compile only machine ROCMINFO fails
      self.get_num_cpus()
      self.num_gpus = 0
      return self.cpus, self.gpus

    alist = list(agents.keys())
    if alist:
      alist.sort()
    for i in alist:
      agent = agents[i]
      if agent['Device Type'] == 'GPU':
        details = {
            'rinfo': agent,
            'arch': agent['Name'],
            'num_cu': int(agent['Compute Unit'])
        }
        self.gpus.append(details)
      if agent['Device Type'] == 'CPU':
        details = {'rinfo': agent, 'num_cu': int(agent['Compute Unit'])}
        self.cpus.append(details)
    self.num_cpus = 0
    for cpu in self.cpus:
      self.num_cpus += cpu['num_cu']
    self.num_gpus = len(self.gpus)

    return self.cpus, self.gpus

  def write_file(self, contents, filename=None, is_temp=False):
    """
    Write a file to this machine containing contents
    """
    if is_temp:
      assert filename is None
      _, filename = tempfile.mkstemp()
    else:
      assert filename is not None
    if self.local_machine:
      with open(filename, 'wb') as fout:
        fout.write(contents)
        fout.flush()
    else:
      cnx = self.connect()
      ftp = cnx.ssh.open_sftp()
      with ftp.open(filename, 'wb') as fout:
        fout.write(contents)
        fout.flush()
    return filename

  def read_file(self, filename, byteread=False):
    """
    Read a file from this machine and return the contents
    """
    if self.local_machine:
      with open(filename, 'rb' if byteread else 'r') as rfile:
        return rfile.read()
    else:
      cnx = self.connect()
      ftp = cnx.ssh.open_sftp()
      content_io = BytesIO()
      ftp.getfo(filename, content_io)
      ret = content_io.getvalue()
      if not byteread:
        ret = ret.decode()
      return ret

  def make_temp_file(self):
    """
    Make an empty temp file on this machine
    """
    return self.write_file(b'', is_temp=True)

  def exec_command(self, command, docker_name=None, timeout=LOG_TIMEOUT):
    """
    Execute a command on this machine
    - through docker if on a remote machine
    - no docker with --local_machine
    """
    logger = self.get_logger()
    if isinstance(command, list):
      command = ' '.join(command)
    if not self.local_machine:
      assert docker_name
      command = DOCKER_CMD.format(docker_name, command)
    logger.info('Running command: %s', command)
    cnx = self.connect()
    ret_code, out, err = cnx.exec_command(command, timeout=timeout)
    if err is not None and hasattr(err, 'channel'):
      err.channel.settimeout(LOG_TIMEOUT)

    return ret_code, out, err

  def get_gpu_clock(self, gpu_num=0):
    """query gpu clock levels with rocm-smi"""

    gpu_clk_cmd = '{} -c'.format(ROCMSMI)
    _, stdout, _ = self.connect().exec_command(gpu_clk_cmd)

    base_idx = None
    gpu_clk = []
    for line in stdout:
      if 'GPU' in line:
        idx1 = line.find('[') + 1
        idx2 = line.find(']')
        gpu_idx = int(line[idx1:idx2])
        if base_idx is None or base_idx > gpu_idx:
          base_idx = gpu_idx
        gpu_idx -= base_idx
        if gpu_idx >= len(gpu_clk):
          gpu_clk.append({})
        if 'sclk' in line:
          level = int(line[line.find('level'):].split(' ')[1])
          gpu_clk[gpu_idx]['sclk'] = level
        if 'mclk' in line:
          level = int(line[line.find('level'):].split(' ')[1])
          gpu_clk[gpu_idx]['mclk'] = level

    sclk = gpu_clk[gpu_num]['sclk']
    mclk = gpu_clk[gpu_num]['mclk']

    return sclk, mclk

  def set_gpu_clock(self):
    """set gpu clock level with rocm-smi"""
    cnx = self.connect()

    if self.sclk is not None:
      sclk_cmd = '{} --setsclk {}'.format(ROCMSMI, self.sclk)
      cnx.exec_command(sclk_cmd)
    if self.mclk is not None:
      mclk_cmd = '{} --setmclk {}'.format(ROCMSMI, self.mclk)
      cnx.exec_command(mclk_cmd)

  def restart_server(self, wait=True):
    """restart the machine"""
    logger = self.get_logger()

    logger.warning('Sending remote reboot command')
    if self.ipmi_ip is not None and not self.ipmi_inaccessible:
      logger.info('Using IPMI to reboot machine')
      self.mmi.restart_server()
    else:
      logger.info('No IPMI credentials, using shell to reboot machine')
      cnx = self.connect()
      cnx.exec_command('sudo reboot')
    if not wait:
      return True
    if wait:
      logger.warning('Waiting for machine to reboot')
      sleep(40)
      return True
    return False

  def chk_gpu_status(self, gpu_id):
    """check gpu status, can clinfo find the device"""
    logger = self.get_logger()
    cnx = self.connect()

    if gpu_id not in self.avail_gpus:
      logger.info('GPU index %u out of bounds', gpu_id)
      return False
    logger.info('Checking GPU %u status', gpu_id)
    _, stdout, _ = cnx.exec_command(
        'GPU_DEVICE_ORDINAL={} {} | grep gfx'.format(gpu_id, CLINFO),
        timeout=30)
    if stdout is None:
      return False
    if hasattr(stdout, 'channel'):
      stdout.channel.settimeout(30)
    for line in stdout:
      try:
        line = line.strip()
        logger.info(line)
        if line.find('{}'.format(self.get_gpu(gpu_id)['arch'])) == -1:
          logger.warning('clinfo failed: %s', line)
          logger.warning('clinfo failed for Device ID: %u', gpu_id)
          return False

        logger.info('GPU %u status success', gpu_id)
        return True
      except (socket.timeout, socket.error) as error:
        logger.warning('clinfo failed for Device ID: %u', gpu_id)
        logger.warning('%s', error)
        return False

    logger.warning('clinfo failed by default for Device ID: %u', gpu_id)
    return False

  def getusedspace(self):
    """examine used space on disk"""
    logger = self.get_logger()
    logger.info("Getting free space")
    if self.local_machine:
      file_stat = os.statvfs('/')
      total = file_stat.f_blocks * file_stat.f_frsize
      used = (file_stat.f_blocks - file_stat.f_bfree) * file_stat.f_frsize
      per = (float(used) / float(total)) * 100.0
    else:
      cnx = self.connect()
      _, ssh_stdout, _ = cnx.exec_command(
          "df -h / | grep dev")  # does not work in docker
      if ssh_stdout is None:
        return None
      output = ssh_stdout.read()
      lst = output.split()
      per = int(lst[4][:-1])
    logger.info("Used space on %s : %u", self.hostname, per)
    return per

  def clear_cache(self):
    """clear the machine cache"""
    logger = self.get_logger()
    cnx = self.connect()

    logger.warning('Initiating the cleanup')
    cnx.exec_command("rm -rf ~/.cache/miopen/*")
    logger.warning("Cache for %s cleared", self.hostname)
