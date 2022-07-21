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
import paramiko
from paramiko.dsskey import DSSKey
from paramiko.ecdsakey import ECDSAKey
from paramiko.ed25519key import Ed25519Key
from paramiko.rsakey import RSAKey
from tuna.utils.utility import get_mmi_env_vars

from tuna.utils.logger import setup_logger

ENV_VARS = get_mmi_env_vars()

GATEWAY_IP = ENV_VARS['gateway_ip']
GATEWAY_PORT = ENV_VARS['gateway_port']
GATEWAY_USER = ENV_VARS['gateway_user']
NUM_SSH_RETRIES = 30
SSH_TIMEOUT = 30.0


def key_from_file():
  """ Get private ssh keys from file system """
  keyfiles = []
  keys = []
  for keytype, name in [
      (RSAKey, "rsa"),
      (DSSKey, "dsa"),
      (ECDSAKey, "ecdsa"),
      (Ed25519Key, "ed25519"),
  ]:
    # ~/ssh/ is for windows
    for directory in [".ssh", "ssh"]:
      full_path = os.path.expanduser("~/{}/id_{}".format(directory, name))
      if os.path.isfile(full_path):
        keyfiles.append((keytype, full_path))
        keys.append(keytype.from_private_key_file(full_path))
  return keys


def key():
  """ Get Private key from ssh agent or file system ( fallback) """
  # First try ssh-agent if available
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

  def __init__(self, host, user, auth, via=None, via_user=None):
    if via:
      via_transport = paramiko.Transport(via)
      via_transport.start_client()
      via_transport.auth_publickey(via_user, key()[0])
      # via_transport.auth_none(via_user, via_auth)
      # setup forwarding from 127.0.0.1:<free_random_port> to |host|
      channel = via_transport.open_channel('direct-tcpip', host,
                                           ('127.0.0.1', 0))
      self.transport = paramiko.Transport(channel)
    else:
      self.transport = paramiko.Transport(host)
    self.transport.start_client()
    self.transport.auth_password(user, auth)

  def run(self, cmd):
    """ Run a shell command on the constructed SSH tunnel """
    channel = self.transport.open_session()
    channel.set_combine_stderr(True)
    channel.exec_command(cmd)
    retcode = channel.recv_exit_status()
    buf = ''
    while channel.recv_ready():
      buf += channel.recv(1024).decode()
    return (buf, retcode)


class MgmtBackend(Enum):
  """ Supported Backends """
  IPMI = 1
  OpenBMC = 2


class MachineManagementInterface():
  """
  The static variable per class allows all the instances
  of this class to share a gateway session
  The variable is lazily intialized upon first connection
  """
  gateway_session = None
  obmc_tunnels = {}

  def __init__(self,
               mgmt_ip,
               mgmt_port,
               mgmt_user,
               mgmt_password,
               backend=MgmtBackend.IPMI):
    self.mgmt_ip = mgmt_ip
    self.mgmt_port = mgmt_port
    self.mgmt_user = mgmt_user
    self.mgmt_password = mgmt_password
    self.logger = setup_logger("MachineMgmt")
    self.backend = backend

  def connect_to_gateway(self, gw_ip, gw_port, gw_user):
    """ Establish an SSH connection to the gateway """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    for ssh_idx in range(NUM_SSH_RETRIES):
      try:
        ssh.connect(gw_ip, username=gw_user, port=gw_port, timeout=SSH_TIMEOUT)
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

  def run_bmc_command(self, command):
    """ Exec a BMC command on the remote host """
    tunnel = MachineManagementInterface.obmc_tunnels.get(
        (self.mgmt_ip, self.mgmt_port), None)
    if tunnel is None:
      tunnel = SSHTunnel((self.mgmt_ip, self.mgmt_port),
                         self.mgmt_user,
                         self.mgmt_password, (GATEWAY_IP, int(GATEWAY_PORT)),
                         via_user=GATEWAY_USER)
      MachineManagementInterface.obmc_tunnels[(self.mgmt_ip,
                                               self.mgmt_port)] = tunnel
    self.logger.info('Running OBMC command: %s', command)
    (output, retcode) = tunnel.run('/usr/sbin/obmcutil {}'.format(command))
    self.logger.info('OBMC output: %s', output)
    self.logger.info('OBMC return code: %s', retcode)
    return retcode

  def run_ipmi_command(self, command):
    """ Exec an IPMI command on the remote host """
    cmd = 'ipmitool -H {} -U {} -P {} -p {} {}'.format(self.mgmt_ip,
                                                       self.mgmt_user,
                                                       self.mgmt_password,
                                                       self.mgmt_port, command)
    self.logger.info('Running IPMI command: %s', cmd)
    subp = Popen(cmd,
                 stdout=PIPE,
                 stderr=PIPE,
                 shell=True,
                 universal_newlines=True)
    out_ch = subp.stdout
    err_ch = subp.stderr
    error = [x.strip() for x in err_ch.readlines()]
    error = '\n'.join(error)
    exit_status = 0
    if error:
      exit_status = 1
      try:
        if (not MachineManagementInterface.gateway_session or
            not MachineManagementInterface.gateway_session.get_transport(
            ).is_active()):
          MachineManagementInterface.gateway_session = self.connect_to_gateway(
              GATEWAY_IP, GATEWAY_PORT, GATEWAY_USER)

        ssh = MachineManagementInterface.gateway_session
        _, out_ch, err_ch = ssh.exec_command(cmd, timeout=SSH_TIMEOUT)
        error = [x.strip() for x in err_ch.readlines()]
        error = '\n'.join(error)
        exit_status = out_ch.channel.exit_status
      except paramiko.ssh_exception.SSHException:
        self.logger.warning('Failed to execute ipmitool command')

    output = [x.strip() for x in out_ch.readlines()]
    output = '\n'.join(output)
    self.logger.warning('IPMI std output: %s', output)
    self.logger.warning('IPMI err output: %s', error)
    return exit_status

  def restart_server(self):
    """ Method to restart a remote machine """
    ret = None
    if self.backend == MgmtBackend.IPMI:
      ret = self.run_ipmi_command("chassis power cycle")
    else:
      ret = self.run_bmc_command("chassisoff")
      ret |= self.run_bmc_command("chassison")
    return ret

  def server_status(self):
    """ Return the status of the management backend of the remote machine """
    ret = None
    if self.backend == MgmtBackend.IPMI:
      ret = self.run_ipmi_command("chassis status")
    else:
      ret = self.run_bmc_command("chassisstate")
    return ret


if __name__ == '__main__':
  pass
