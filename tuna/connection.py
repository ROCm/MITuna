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
"""Connection class represents a DB connection. Used by machine to establish new DB connections"""
import socket
from random import randrange
from subprocess import Popen, PIPE, STDOUT
from time import sleep
from io import StringIO
import paramiko

from tuna.utils.logger import setup_logger
from tuna.abort import chk_abort_file

NUM_SSH_RETRIES = 40
NUM_CMD_RETRIES = 30
SSH_TIMEOUT = 60.0  # in seconds


class Connection():
  """Connection class defined an ssh or ftp client connection. Instantiated by the machine class"""

  #pylint: disable=no-member

  def __init__(self, **kwargs):
    #pylint
    self.logger = None
    self.local_machine = False
    self.subp = None  # Holds the subprocess obj for local_machine
    self.out_channel = None  # Holds the out channel for remote connection

    allowed_keys = set([
        'id', 'hostname', 'user', 'password', 'port', 'local_machine',
        'chk_abort_file', 'logger'
    ])
    self.__dict__.update((key, None) for key in allowed_keys)
    self.__dict__.update(
        (key, value) for key, value in kwargs.items() if key in allowed_keys)

    self.ssh = None

    if self.logger is None:
      self.logger = setup_logger('Connection')

    self.inst_bins = {'which': True, 'cd': True}
    self.connect(self.chk_abort_file)

  def check_binary(self, bin_str):
    """Checking existence of binary"""
    if bin_str in self.inst_bins:
      return self.inst_bins[bin_str]

    cmd = "which {}".format(bin_str)
    _, out, _ = self.exec_command(cmd)
    if not out:
      return False

    ret = False
    for line in out:
      if bin_str in line:
        ret = True
        break

    self.inst_bins[bin_str] = ret
    return ret

  @staticmethod
  def get_bin_str(cmd):
    """Helper function"""
    bin_str = ''
    line = cmd[:]
    args = line.split(' ')
    for arg in args:
      arg = arg.strip()
      if not arg:  # skip empty tokens due to white spaces
        continue
      if '=' in arg:
        continue
      if arg in ('export', 'sudo', '&&'):
        continue
      bin_str = arg
      break

    return bin_str

  def test_cmd_str(self, cmd):
    """Function to look for installed binary"""
    split_cmd = cmd[:]
    split_cmd = split_cmd.replace('|', ';')
    split_cmd = split_cmd.split(';')
    for sub_cmd in split_cmd:
      sub_cmd = sub_cmd.strip()
      bin_str = self.get_bin_str(sub_cmd)
      installed = self.check_binary(bin_str)
      if not installed:
        self.logger.error('Tuna cannot find binary: %s', bin_str)
        return False

    return True

  def is_alive(self):
    ''' Check if the launched process is running '''
    if self.local_machine:  # pylint: disable=no-else-return
      if not self.subp:
        self.logger.error('Checking isAlive when process was not created')
      return self.subp.poll() is None
    else:
      if not self.out_channel:
        self.logger.error('Checking isAlive when channel does not exist')
      return not self.out_channel.exit_status_ready()

  def exec_command_unparsed(self, cmd, timeout=SSH_TIMEOUT, abort=None):
    """Function to exec commands"""
    # pylint: disable=broad-except
    if not self.test_cmd_str(cmd):
      raise Exception('Machine {} failed, missing binary: {}'.format(
          self.id, cmd))

    if self.local_machine:
      #universal_newlines corrects output format to utf-8
      self.subp = Popen(cmd,
                        stdout=PIPE,
                        stderr=STDOUT,
                        shell=True,
                        close_fds=True,
                        universal_newlines=True)
      stdout, stderr = self.subp.stdout, self.subp.stderr
      return 0, stdout, stderr

    for cmd_idx in range(NUM_CMD_RETRIES):
      try:
        if self.ssh is None or not self.ssh.get_transport(
        ) or not self.ssh.get_transport().is_active():
          self.ssh_connect()
        i_var, o_var, e_var = self.ssh.exec_command(cmd, timeout=timeout)
      except Exception as exc:
        self.logger.warning('Machine %s failed to execute command: %s', self.id,
                            cmd)
        self.logger.warning('Exception occurred %s', exc)
        self.logger.warning('Retrying ... %s', cmd_idx)
        retry_interval = randrange(SSH_TIMEOUT)
        self.logger.warning('sleeping for %s seconds', retry_interval)
        sleep(retry_interval)
      else:
        self.out_channel = o_var.channel
        return i_var, o_var, e_var

      if abort is not None and chk_abort_file(self.id, self.logger):
        self.logger.warning('Machine %s aborted command execution: %s', self.id,
                            cmd)
        return None, None, None

    self.logger.error('cmd_exec retries exhausted, giving up')
    return None, None, None

  def exec_command(self, cmd, timeout=SSH_TIMEOUT, abort=None, proc_line=None):
    """Function to exec commands"""
    _, o_var, e_var = self.exec_command_unparsed(cmd, timeout, abort)

    if not o_var:
      return 1, o_var, e_var

    if not proc_line:
      proc_line = lambda x: self.logger.info(line.strip())
    ret_out = StringIO()
    ret_err = e_var
    try:
      while True:
        line = o_var.readline()
        if line == '' and not self.is_alive():
          break
        if line:
          proc_line(line)
          ret_out.write(line)
      ret_out.seek(0)
      if self.local_machine:
        ret_code = self.subp.returncode
        if ret_out:
          ret_out.seek(0)
          ret_err = StringIO()
          err_str = ret_out.readlines()
          for line in err_str[-5:]:
            ret_err.write(line)
          ret_err.seek(0)
          ret_out.seek(0)
      else:
        ret_code = self.out_channel.recv_exit_status()
    except (socket.timeout, socket.error) as exc:
      self.logger.warning('Exception occurred %s', exc)
      ret_code = 1
      ret_out = None

    return ret_code, ret_out, ret_err

  def connect(self, abort=None):
    """Establishing new connecion"""
    if not self.local_machine:
      self.ssh_connect(abort)

  def ssh_connect(self, abort=None):
    """Establishing ssh connection"""
    ret = True
    if self.ssh is not None and self.ssh.get_transport(
    ) and self.ssh.get_transport().is_active():
      ret = False
      return ret

    self.ssh = paramiko.SSHClient()
    self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    for ssh_idx in range(NUM_SSH_RETRIES):
      if abort is not None and chk_abort_file(self.id, self.logger):
        self.logger.warning('Machine %s aborted ssh connection', self.id)
        return False

      try:
        self.ssh.connect(self.hostname,
                         username=self.user,
                         password=self.password,
                         port=self.port,
                         timeout=SSH_TIMEOUT,
                         allow_agent=False)
      except paramiko.ssh_exception.BadHostKeyException:
        self.ssh = None
        self.logger.error('Bad host exception which connecting to host: %s',
                          self.hostname)
      except (paramiko.ssh_exception.SSHException, socket.error):
        retry_interval = randrange(SSH_TIMEOUT)
        self.logger.warning(
            'Attempt %s to connect to machine %s (%s p%s) via ssh failed, sleeping for %s seconds',
            ssh_idx, self.id, self.hostname, self.port, retry_interval)
        sleep(retry_interval)
      else:
        self.logger.info(
            'SSH connection successfully established to machine %s', self.id)
        return True

    self.logger.error('SSH retries exhausted machine: %s', self.hostname)
    return False

  def open_sftp(self):
    """Helper function for ftp client"""
    ftp_client = None
    if self.ssh and not self.local_machine:
      ftp_client = self.ssh.open_sftp()
    return ftp_client
