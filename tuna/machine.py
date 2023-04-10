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
from os import statvfs_result
import socket
from time import sleep
from io import BytesIO
import tempfile
from subprocess import Popen, PIPE
import logging

from typing import Set, List, Optional, TextIO, Tuple, Dict, Union, IO, Any, Callable
from typing_extensions import SupportsIndex
from sqlalchemy import Text, Column, orm
from sqlalchemy.dialects.mysql import TINYINT, INTEGER

from paramiko.channel import ChannelFile
from paramiko import SSHClient
import paramiko
from tuna.machine_management_interface import MachineManagementInterface
from tuna.utils.logger import setup_logger
from tuna.connection import Connection
from tuna.dbBase.base_class import BASE
from tuna.abort import chk_abort_file
from tuna.utils.utility import check_qts
from tuna.miopen.utils.metadata import DOCKER_CMD, LOG_TIMEOUT

ROCMINFO: str = '/opt/rocm/bin/rocminfo'
ROCMSMI: str = '/opt/rocm/bin/rocm-smi'
CLINFO: str = '/opt/rocm/opencl/bin/clinfo'


class Machine(BASE):  #pylint: disable=too-many-instance-attributes
  """class for maintaining machine characteristics and interactions """
  __tablename__: str = "machine"
  hostname: str = Column(Text, nullable=False)
  port: int = Column(INTEGER(11, unsigned=True),
                     nullable=False,
                     server_default="22")
  local_ip: str = Column(Text, nullable=True)
  local_port: int = Column(INTEGER, server_default="22")
  user: str = Column(Text, nullable=False)
  password: str = Column(Text, nullable=False)
  avail_gpus: List[Dict[int, str]] = Column(Text, nullable=False)
  arch: str = Column(Text, nullable=False)
  num_cu: int = Column(INTEGER, nullable=False, server_default="64")
  sclk: int = Column(INTEGER)
  mclk: int = Column(INTEGER)
  available: int = Column(TINYINT(1), server_default="0")
  remarks: str = Column(Text)
  ipmi_inaccessible: int = Column(TINYINT, server_default="0")
  ipmi_ip: str = Column(Text)
  ipmi_port: int = Column(INTEGER(40, unsigned=True))
  ipmi_user: str = Column(Text)
  ipmi_password: str = Column(Text)

  @orm.reconstructor
  def __init__(self, **kwargs: dict) -> None:
    #for the sake of pylint, this is explicitly populated
    allowed_keys: Set = set([
        'id', 'hostname', 'user', 'password', 'port', 'ipmi_ip', 'ipmi_port',
        'ipmi_user', 'ipmi_password', 'ipmi_inaccessible', 'sclk', 'mclk',
        'arch', 'num_cu', 'avail_gpus', 'local_machine'
    ])
    self.__dict__.update(
        (key, None) for key in allowed_keys if key not in self.__dict__)
    self.__dict__.update(
        (key, value) for key, value in kwargs.items() if key in allowed_keys)

    self.cnx_list: dict = {}
    self.log_list: dict = {}
    self.num_cpus: int = 0
    self.avail_gpus: List[Dict[int, str]]
    self.sclk: int
    self.mclk: int
    self.gpus: List[Dict[Any, Any]]
    self.cpus: List[dict]
    self.logger: logging.Logger
    self.mmi: MachineManagementInterface
    self.cnx: Connection
    self.ssh: paramiko.SSHClient = SSHClient()

    if self.local_machine:  # pylint: disable=no-member ; false alarm
      self.logger = setup_logger(f'Machine_{self.hostname}')
      self.connect()
      self.mmi = None

      self.id: int = 0  # pylint: disable=invalid-name
      self.get_properties()

      if self.gpus:
        self.arch = self.gpus[0]['arch']
        self.num_cu = self.gpus[0]['num_cu']
        self.avail_gpus = list(range(len(self.gpus)))  #type: ignore
    else:
      cmd: str = 'hostname'
      with Popen(cmd, stdout=PIPE, shell=True, universal_newlines=True) as subp:
        if subp.stdout is not None:
          hostname: str = subp.stdout.readline().strip()
      if self.local_ip is not None and check_qts(hostname):
        self.hostname = self.local_ip
        self.port: int = self.local_port
      self.logger = setup_logger('Machine_{self.id}')
      self.mmi = MachineManagementInterface(self.ipmi_ip, self.ipmi_port,
                                            self.ipmi_user, self.ipmi_password)

      if not self.avail_gpus is None:
        self.avail_gpus = [
            int(val) for val in self.avail_gpus.split(',')  #type: ignore
        ]  #type: ignore
        self.num_gpus = len(self.avail_gpus)
      self.cpus = []  # type: ignore
      self.gpus = []  # type: ignore

    self.logger.info("avail gpus: %s", self.avail_gpus)

  def set_logger(self, logger: logging.Logger) -> bool:
    """set logging for machine, use this to associate the machine with a subprocess"""
    pid: int = os.getpid()
    self.log_list[pid] = logger
    self.logger.info('Set logger for process %u', pid)
    return True

  def get_logger(self) -> logging.Logger:
    """return the logger for the current process"""
    pid: int = os.getpid()
    if pid in self.log_list:
      return self.log_list[pid]

    return self.logger

  def connect(self, abort: Callable = None) -> Connection:
    """get the connection for the current process, or create a new one"""
    logger = self.get_logger()

    pid: int = os.getpid()
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
        'local_machine': self.local_machine,  # pylint: disable=no-member ; false alarm
        'chk_abort_file': chk_abort_file
    }
    keys['logger'] = logger
    keys['chk_abort_file'] = abort
    connection = Connection(**keys)
    self.cnx_list[pid] = connection

    return connection

  def get_num_cpus(self) -> int:
    """return number of available cpus"""
    stdout: TextIO
    _, stdout, _ = self.connect().exec_command('nproc')
    self.num_cpus = int(stdout.readline())  #type: ignore

    return self.num_cpus

  def get_avail_gpus(self) -> List[Dict[int, str]]:
    """return list of available gpus"""
    if not self.avail_gpus:
      if not self.gpus:
        self.get_properties()
        self.avail_gpus = range(len(self.gpus))  #type: ignore
        self.num_gpus = len(self.avail_gpus)
    return self.avail_gpus

  def get_gpu(self, idx: int) -> Optional[Dict[int, str]]:
    """return gpu details"""
    if not self.gpus:
      self.get_properties()
    if idx >= len(self.gpus):
      return None

    return self.gpus[idx]

  def parse_agents(self) -> dict:  #pylint: disable=too-many-locals
    #pylint: disable=too-many-branches
    """create agent dictionary from rocminfo"""
    stdout: TextIO
    _, stdout, _ = self.connect().exec_command(ROCMINFO)

    agent: Optional[int] = None
    agents: dict = {}
    stack: list = []
    decoded_line: str
    last_div: dict
    sub: dict
    cols: list
    field: str
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
          arr: list = decoded_line.split(' ', 1)
          if arr[0] in ('x', 'y', 'z'):
            sub[arr[0]] = arr[1].strip()
          else:
            field = decoded_line.strip()
            sub[field] = {}
            last_div = sub[field]

        last_indent = indent

    return agents

  def get_properties(self) -> Tuple[List[Any], List[Any]]:
    """return cpu and gpu device info as dicts"""
    agents: dict = self.parse_agents()

    self.cpus = []
    self.gpus = []
    alist: list
    agent: dict
    details: dict

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

  def write_file(self, contents: bytes, filename: str = None, \
  is_temp: bool = False) -> str:
    """
    Write a file to this machine containing contents
    """
    cnx: Connection
    ftp: Optional[paramiko.sftp_client.SFTPClient] = None

    if is_temp:
      assert filename is None
      _, filename = tempfile.mkstemp()
    else:
      assert filename is not None

    if self.local_machine:  # pylint: disable=no-member ; false alarm
      with open(filename, 'wb') as fout:
        fout.write(contents)
        fout.flush()
    else:
      cnx = self.connect()
      ftp = cnx.ssh.open_sftp()
      with ftp.open(filename, 'wb') as fout:  #type: ignore
        fout.write(contents)
        fout.flush()

    return filename

  def read_file(self,
                filename: str,
                byteread: bool = False) -> Union[bytes, str]:
    """
    Read a file from this machine and return the contents
    """
    ret: Union[str, bytes]
    cnx: Connection
    ftp: paramiko.sftp_client.SFTPClient
    content_io: BytesIO

    if self.local_machine:  # pylint: disable=no-member ; false alarm
      # pylint: disable-next=unspecified-encoding
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

  def make_temp_file(self) -> Union[str, Text]:
    """
    Make an empty temp file on this machine
    """
    return self.write_file(b'', is_temp=True)

  def exec_command(self, command: str, timeout: int = LOG_TIMEOUT) -> Tuple[int, str,\
  ChannelFile]:
    """
    Execute a command on this machine
    - through docker if on a remote machine
    - no docker on local machine
    """
    cnx: Connection
    ret_code: int
    out: str
    err: ChannelFile

    logger = self.get_logger()
    if isinstance(command, list):
      command = ' '.join(command)
    if not self.local_machine:  # pylint: disable=no-member ; false alarm
      command = DOCKER_CMD.format(command)
    logger.info('Running command: %s', command)
    cnx = self.connect()
    ret_code, out, err = cnx.exec_command(command, timeout=timeout)
    if err is not None and hasattr(err, 'channel'):
      err.channel.settimeout(LOG_TIMEOUT)

    return ret_code, out, err

  def get_gpu_clock(self, gpu_num: int = 0) -> Tuple[Union[SupportsIndex, slice], \
  Union[SupportsIndex, slice]]:
    """query gpu clock levels with rocm-smi"""
    stdout = Optional[IO[str]]
    gpu_clk_cmd: str = f'{ROCMSMI} -c'
    _, stdout, _ = self.connect().exec_command(gpu_clk_cmd)

    base_idx: Union[int, None] = None
    gpu_clk: List[Dict[str, int]] = []
    gpu_idx: int = 0
    level: Union[int, str]
    sclk: Union[SupportsIndex, slice]
    mclk: Union[SupportsIndex, slice]
    line: str
    idx1: Optional[int]
    idx2: Optional[int]

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

  def restart_server(self, wait: bool = True) -> bool:
    """restart the machine"""
    logger = self.get_logger()

    logger.warning('Sending remote reboot command')
    if self.ipmi_ip is not None and not self.ipmi_inaccessible and self.mmi is not None:
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

  def chk_gpu_status(self, gpu_id: int) -> bool:
    """check gpu status, can clinfo find the device"""
    line: str
    stdout: ChannelFile
    logger: logging.Logger = self.get_logger()
    cnx = self.connect()

    if gpu_id not in self.avail_gpus:  #type: ignore
      logger.info('GPU index %u out of bounds', gpu_id)
      return False
    logger.info('Checking GPU %u status', gpu_id)
    _, stdout, _ = cnx.exec_command(
        f'GPU_DEVICE_ORDINAL={gpu_id} {CLINFO} | grep gfx', timeout=30)
    if stdout is None:
      return False
    if hasattr(stdout, 'channel'):
      stdout.channel.settimeout(30)
    for line in stdout:
      try:
        line = line.strip()
        logger.info(line)
        if line.find(f"{self.get_gpu(gpu_id)['arch']}") == -1:  #type: ignore
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

  def getusedspace(self) -> float:
    """examine used space on disk"""
    logger: logging.Logger = self.get_logger()
    logger.info("Getting free space")
    lst: list
    per: float
    output: bytes
    ssh_stdout: ChannelFile
    cnx: Connection
    if self.local_machine:  # pylint: disable=no-member ; false alarm
      file_stat: statvfs_result = os.statvfs('/')
      total: int = file_stat.f_blocks * file_stat.f_frsize
      used: int = (file_stat.f_blocks - file_stat.f_bfree) * file_stat.f_frsize
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
