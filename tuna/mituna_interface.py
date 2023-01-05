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
"""Interface class to set up and launch tuning functionality"""
from multiprocessing import Value

from tuna.libraries import Library
from tuna.utils.logger import setup_logger
from tuna.utils.utility import get_env_vars, compose_f_vals


class MITunaInterface():
  """ Interface class extended by libraries. The purpose of this class is to define
  common functionalities. """

  def __init__(self, library=Library.MIOPEN):
    self.library = library

    self.logger = setup_logger(logger_name=self.library.value,
                               add_streamhandler=True)

  def check_docker(self, worker, dockername="miopentuna"):
    """! Checking for docker
      @param worker The worker interface instance
      @param dockername The name of the docker
    """
    self.logger.warning("docker not installed or requires sudo .... ")
    _, out2, _ = worker.exec_command("sudo docker info")
    while not out2.channel.exit_status_ready():
      self.logger.warning(out2.readline())
    if out2.channel.exit_status > 0:
      self.logger.warning(
          "docker not installed or failed to run with sudo .... ")
    else:
      _, out, _ = worker.exec_command(f"sudo docker images | grep {dockername}")
      line = None
      for line in out.readlines():
        if line.find(dockername) != -1:
          self.logger.warning('%s docker image exists', dockername)
          break
      if line is None:
        self.logger.warning('%s docker image does not exist', dockername)

  def check_status(self,
                   worker,
                   b_first,
                   gpu_idx,
                   machine,
                   dockername="miopentuna"):
    """! Function to check gpu_status
      @param worker The worker interface instance
      @param b_first Flag to keep track of visited GPU
      @param gpu_idx Unique ID of the GPU
      @param machine The machine instance
      @param dockername The name of the docker
    """

    if machine.chk_gpu_status(worker.gpu_id):
      self.logger.info('Machine: (%s, %u) GPU_ID: %u OK', machine.hostname,
                       machine.port, gpu_idx)
    else:
      self.logger.info('Machine: (%s, %u) GPU_ID: %u ERROR', machine.hostname,
                       machine.port, gpu_idx)

    if not b_first:
      return False
    b_first = False
    _, out, _ = worker.exec_command("docker info")
    while not out.channel.exit_status_ready():
      pass

    if out.channel.exit_status > 0:
      self.check_docker(worker, dockername)
    else:
      _, out, _ = worker.exec_command(f"docker images | grep {dockername}")
      line = None
      for line in out.readlines():
        if line.find(dockername) != -1:
          self.logger.warning('%s docker image exists', dockername)
          break
      if line is None:
        self.logger.warning('%s docker image does not exist', dockername)

    return True

  def execute_docker(self, worker, docker_cmd, machine):
    """! Function to executed docker cmd
      @param worker The worker interface instance
      @param docker_cmd The command to be executed in the docker
      @param machine The machine instance
    """
    self.logger.info('Running on host: %s port: %u', machine.hostname,
                     machine.port)
    _, _, _ = worker.exec_docker_cmd(docker_cmd + " 2>&1")
    #logger output already printed by exec_docker_cmd
    #self.logger.info(docker_cmd)
    #while not out.channel.exit_status_ready():
    #  lines = out.readline()
    #  self.logger.info(lines.rstrip())
    #for line in out.readlines():
    #  self.logger.info(line.rstrip())

    return True

  def add_tables(self):
    """Add library specific tables"""
    return self.add_tables()

  def determine_num_procs(self, machine):
    """Determine number of processes by compute capacity"""
    worker_ids = None
    env = get_env_vars()
    if env['slurm_cpus'] > 0:
      num_procs = int(env['slurm_cpus'])
    else:
      # JD: This sould be the responsibility of the machine class
      num_procs = int(machine.get_num_cpus() * .6)

    worker_ids = range(num_procs)

    if len(worker_ids) == 0:
      self.logger.error('num_procs must be bigger than zero to launch worker')
      self.logger.error('Cannot launch worker on machine: %s', machine.id)
      worker_ids = None

    return worker_ids

  def get_f_vals(self, args, machine, worker_ids):
    """Determine kwargs for worker_interface"""
    f_vals = compose_f_vals(args, machine)
    f_vals["num_procs"] = Value('i', len(worker_ids))
    return f_vals
