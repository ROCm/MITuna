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
""" Machine Management Module to restart machines remotely
    using BMC or IPMI """
import socket
from time import sleep
from enum import Enum
import os
from subprocess import Popen, PIPE
from typing import Dict, List, Tuple, Union, Any, Optional, IO

import logging
import paramiko
from paramiko.dsskey import DSSKey
from paramiko.ecdsakey import ECDSAKey
from paramiko.ed25519key import Ed25519Key
from paramiko.rsakey import RSAKey
from paramiko.agent import AgentKey
from paramiko.channel import ChannelFile, ChannelStderrFile
from tuna.utils.utility import get_mmi_env_vars
from tuna.utils.logger import setup_logger

ENV_VARS: Dict = get_mmi_env_vars()

GATEWAY_IP: str = ENV_VARS['gateway_ip']
GATEWAY_PORT: int = ENV_VARS['gateway_port']
GATEWAY_USER: str = ENV_VARS['gateway_user']
NUM_SSH_RETRIES: int = 30
SSH_TIMEOUT: float = 30.0


def key_from_file() -> Union[Tuple[AgentKey, ...], List]:
  """ Get private ssh keys from file system """
  keyfiles: List = []
  keys: List = []
  full_path: str
  keytype: Any[type]

  for keytype, name in [
      (RSAKey, "rsa"),
      (DSSKey, "dsa"),
      (ECDSAKey, "ecdsa"),
      (Ed25519Key, "ed25519"),
  ]:
    # ~/ssh/ is for windows
    for directory in [".ssh", "ssh"]:
      full_path = os.path.expanduser(f"~/{directory}/id_{name}")
      if os.path.isfile(full_path):
        keyfiles.append((keytype, full_path))
        keys.append(keytype.from_private_key_file(full_path))
  return keys


def key() -> Union[Tuple[AgentKey, ...], List]:
  """ Get Private key from ssh agent or file system ( fallback) """
  # First try ssh-agent if available
  keys: Union[Tuple[AgentKey, ...], List[Any]]
  agent: paramiko.agent.Agent

  agent = paramiko.Agent()
  keys = agent.get_keys()
  if not keys:
    keys = key_from_file()
    if not keys:
      raise ValueError("Unable to find any keys on the host system")
  return keys


class SSHTunnel():  # pylint: disable=too-few-public-methods
  '''
  Class to create an SSH tunnel
  to access BMC systems via bastion
  '''

  def __init__(self, host: Optional[Tuple[str, int]], \
  user: str, auth: str, via: Union[str] = None, \
  via_user: Optional[str] = None) -> None:

    channel: paramiko.channel.Channel
    via_transport: paramiko.transport.Transport

    if via:
      via_transport = paramiko.Transport(via)
      via_transport.start_client()
      if via_user is not None:
        via_transport.auth_publickey(via_user, key()[0])
      if host is not None:
        channel = via_transport.open_channel('direct-tcpip', host,
                                             ('127.0.0.1', 0))
      self.transport = paramiko.Transport(channel)
    else:
      if host is not None:
        self.transport = paramiko.Transport(host)
        self.transport.start_client()
        self.transport.auth_password(user, auth)

  def run(self, cmd) -> Tuple[str, int]:
    """ Run a shell command on the constructed SSH tunnel """
    channel: paramiko.channel.Channel
    channel = self.transport.open_session()
    channel.set_combine_stderr(True)
    channel.exec_command(cmd)
    retcode: int = channel.recv_exit_status()
    buf: str = ''
    while channel.recv_ready():
      buf += channel.recv(1024).decode()
    return (buf, retcode)


class MgmtBackend(Enum):
  """ Supported Backends """
  IPMI: int = 1
  OpenBMC: int = 2  # pylint: disable=invalid-name ; more readable than all-uppercase


class MachineManagementInterface():
  """
  The static variable per class allows all the instances
  of this class to share a gateway session
  The variable is lazily intialized upon first connection
  """
  gateway_session = None
  obmc_tunnels: dict = {}

  def __init__(self,
               mgmt_ip,
               mgmt_port,
               mgmt_user,
               mgmt_password,
               backend=MgmtBackend.IPMI) -> None:
    self.mgmt_ip: str = mgmt_ip
    self.mgmt_port: int = mgmt_port
    self.mgmt_user: str = mgmt_user
    self.mgmt_password: str = mgmt_password
    self.logger: logging.Logger = setup_logger("MachineMgmt")
    self.backend: MgmtBackend = backend

  def connect_to_gateway(self, gw_ip: str, gw_port: int,
                         gw_user: str) -> Union[paramiko.SSHClient, None]:
    """ Establish an SSH connection to the gateway """
    ssh: Optional[paramiko.SSHClient] = paramiko.SSHClient()
    if ssh is not None:
      ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    for ssh_idx in range(NUM_SSH_RETRIES):
      try:
        if ssh is not None:
          ssh.connect(gw_ip,
                      username=gw_user,
                      port=gw_port,
                      timeout=SSH_TIMEOUT)
      except paramiko.ssh_exception.BadHostKeyException:
        ssh = None
        self.logger.error(
            'Bad host exception which connecting to host: %s on port: %s',
            gw_ip, gw_port)
      except (paramiko.ssh_exception.SSHException, socket.error):
        self.logger.warning(
            'Gateway connection attempt %s to %s:%s via ssh failed, sleeping for %s seconds',
            ssh_idx, gw_ip, gw_port, SSH_TIMEOUT)
        sleep(SSH_TIMEOUT)
      else:
        self.logger.info("Connected to machine: %s on port: %s", gw_ip, gw_port)
        self.logger.info('SSH connection successfully established')
        return ssh
      if os.path.exists('/tmp/tuna_abort_mmi'):
        self.logger.warning(
            '/tmp/tuna_abort_mmi file found, aborting gateway connection attempt'
        )
    self.logger.error(
        "SSH retries exhausted while connecting to MachineManagement "
        "Gateway: %s", gw_ip)
    return None

  def run_bmc_command(self, command: str) -> int:
    """ Exec a BMC command on the remote host """
    tunnel: SSHTunnel
    tunnel = MachineManagementInterface.obmc_tunnels.get(
        (self.mgmt_ip, self.mgmt_port), None)

    if tunnel is None:
      tunnel = SSHTunnel(
          (self.mgmt_ip, self.mgmt_port),
          self.mgmt_user,
          self.mgmt_password,
          (GATEWAY_IP, int(GATEWAY_PORT)),  #type: ignore
          via_user=GATEWAY_USER)
      MachineManagementInterface.obmc_tunnels[(self.mgmt_ip,
                                               self.mgmt_port)] = tunnel
    self.logger.info('Running OBMC command: %s', command)
    (output, retcode) = tunnel.run(f'/usr/sbin/obmcutil {command}')
    self.logger.info('OBMC output: %s', output)
    self.logger.info('OBMC return code: %s', retcode)
    return retcode

  def run_ipmi_command(self, command: str) -> int:
    """ Exec an IPMI command on the remote host """
    # pylint: disable=consider-using-f-string ; more-readable this way
    err_ch: Optional[IO[str]]
    error: List[str]
    er_append: str
    exit_status: int

    # temp variables used in exec command
    out_ch: ChannelFile
    err_out: ChannelStderrFile
    e_result: str

    cmd: str = 'ipmitool -H {} -U {} -P {} -p {} {}'.format(
        self.mgmt_ip, self.mgmt_user, self.mgmt_password, self.mgmt_port,
        command)
    # pylint: enable=consider-using-f-string
    self.logger.info('Running IPMI command: %s', cmd)
    with Popen(cmd,
               stdout=PIPE,
               stderr=PIPE,
               shell=True,
               universal_newlines=True) as subp:
      err_ch = subp.stderr
      if err_ch is not None:
        error = [x.strip() for x in err_ch.readlines()]
        er_append = '\n'.join(error)
        exit_status = 0
      if er_append:
        exit_status = 1
        try:
          if (not MachineManagementInterface.gateway_session or
              not MachineManagementInterface.gateway_session.get_transport(
              ).is_active()):
            MachineManagementInterface.gateway_session = self.connect_to_gateway(
                GATEWAY_IP, GATEWAY_PORT, GATEWAY_USER)

          ssh = MachineManagementInterface.gateway_session
          if ssh is not None:
            _, out_ch, err_out = ssh.exec_command(cmd, timeout=SSH_TIMEOUT)
          if err_out is not None:
            error = [x.strip() for x in err_out.readlines()]
            e_result = '\n'.join(error)
            exit_status = out_ch.channel.exit_status
        except paramiko.ssh_exception.SSHException:
          self.logger.warning('Failed to execute ipmitool command')

      output = [x.strip() for x in out_ch.readlines()]
      rstr: str = '\n'.join(output)
      self.logger.warning('IPMI std output: %s', rstr)
      self.logger.warning('IPMI err output: %s', e_result)
      return exit_status

  def restart_server(self) -> int:
    """ Method to restart a remote machine """

    ret: Optional[int] = None
    if self.backend == MgmtBackend.IPMI:
      ret = self.run_ipmi_command("chassis status")
    else:
      ret = self.run_bmc_command("chassisstate")
    return ret


if __name__ == '__main__':
  pass
