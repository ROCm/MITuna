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
from multiprocessing import Value, Lock, Queue as mpQueue
from typing import Optional, Dict, Any, List
from io import StringIO
import logging
import argparse
from paramiko.channel import ChannelFile
from tuna.worker_interface import WorkerInterface
from tuna.machine import Machine
from tuna.libraries import Library
from tuna.utils.logger import setup_logger
from tuna.utils.utility import get_env_vars


class MITunaInterface():
  """ Interface class extended by libraries. The purpose of this class is to define
  common functionalities. """

  def __init__(self, library=Library.MIOPEN) -> None:

    self.library: Library = library

    self.logger: logging.Logger = setup_logger(logger_name=self.library.value,
                                               add_streamhandler=True)
    self.args: argparse.Namespace

    self.worker_type: str = WorkerInterface.name
    self.fetch_state: set = set()
    #self.fetch_state.add('new')
    self.max_job_retries = 10
    self.dbt = None

  def check_docker(self,
                   worker: WorkerInterface,
                   dockername="miopentuna") -> None:
    """! Checking for docker
      @param worker The worker interface instance
      @param dockername The name of the docker
    """
    out2: ChannelFile
    self.logger.warning("docker not installed or requires sudo .... ")
    _, out2, _ = worker.exec_command("sudo docker info")
    while not out2.channel.exit_status_ready():
      self.logger.warning(out2.readline())
    if out2.channel.exit_status > 0:
      self.logger.warning(
          "docker not installed or failed to run with sudo .... ")
    else:
      out: StringIO = StringIO()
      line: Optional[str] = None
      _, out, _ = worker.exec_command(f"sudo docker images | grep {dockername}")
      for line in out.readlines():
        if line is not None:
          if line.find(dockername) != -1:
            self.logger.warning('%s docker image exists', dockername)
            break
      if line is None:
        self.logger.warning('%s docker image does not exist', dockername)

  def check_status(self,
                   worker: WorkerInterface,
                   b_first: int,
                   gpu_idx: int,
                   machine: Machine,
                   dockername: str = "miopentuna") -> bool:
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
      line: Optional[str] = None
      for line in out.readlines():
        if line is not None:
          if line.find(dockername) != -1:
            self.logger.warning('%s docker image exists', dockername)
            break
        else:
          self.logger.warning('%s docker image does not exist', dockername)

    return True

  def add_tables(self) -> bool:
    """Add library specific tables"""
    return self.add_tables()

  def get_num_procs(self, machine: Machine) -> List:
    """Determine number of processes by compute capacity"""
    worker_ids: List = []
    num_procs: int
    env: Dict[str, Any]
    env = get_env_vars()
    if env['slurm_cpus'] > 0:
      num_procs = int(env['slurm_cpus'])
    else:
      num_procs = int(machine.get_num_cpus() * .6)

    worker_ids = list(range(num_procs))

    if len(worker_ids) == 0:
      self.logger.error('num_procs must be bigger than zero to launch worker')
      self.logger.error('Cannot launch worker on machine: %s', machine.id)
      worker_ids = []

    return worker_ids

  def get_f_vals(self, machine: Machine, worker_ids: range) -> Dict[str, Any]:
    #pylint:disable=unused-argument
    """Determine kwargs for worker_interface"""
    f_vals: Dict[str, Any]
    f_vals = self.compose_f_vals(machine)
    #f_vals["num_procs"] = Value('i', len(worker_ids))
    f_vals['envmt'] = self.get_envmt()
    return f_vals

  def get_envmt(self):
    """Get runtime envmt"""
    raise NotImplementedError("Not implemented")

  def compose_f_vals(self, machine: Machine, tuning=False) -> Dict[str, Any]:
    """! Compose dict for WorkerInterface constructor
      @param args The command line arguments
      @param machine Machine instance
    """
    f_vals: Dict[str, Any] = {}
    #f_vals["barred"] = Value('i', 0)
    #f_vals["bar_lock"] = Lock()
    #multiprocess queue for jobs, shared on machine
    #f_vals["job_queue"] = mpQueue()
    #f_vals["job_queue_lock"] = Lock()
    #f_vals["result_queue"] = mpQueue()
    #f_vals["result_queue_lock"] = Lock()
    #f_vals["machine"] = machine
    f_vals["b_first"] = True
    #f_vals["end_jobs"] = Value('i', 0)

    #adding non-serializable obj when not running through celery
    if not tuning:
      f_vals["machine"] = machine
      f_vals["barred"] = Value('i', 0)
      f_vals["bar_lock"] = Lock()
      #multiprocess queue for jobs, shared on machine
      f_vals["job_queue"] = mpQueue()
      f_vals["job_queue_lock"] = Lock()

    return f_vals

  def get_kwargs(self,
                 gpu_idx: int,
                 f_vals: Dict[str, Any],
                 tuning=False) -> Dict[str, Any]:
    """! Helper function to set up kwargs for worker instances
      @param gpu_idx Unique ID of the GPU
      @param f_vals Dict containing runtime information
    """
    envmt: Dict[str, Any] = f_vals["envmt"].copy()
    kwargs: Dict[str, Any] = {}

    kwargs = {
        #'machine': f_vals["machine"],
        'gpu_id': gpu_idx,
        #'num_procs': f_vals["num_procs"],
        #'barred': f_vals["barred"],
        #'bar_lock': f_vals["bar_lock"],
        'envmt': envmt,
        #'job_queue': f_vals["job_queue"],
        #'job_queue_lock': f_vals["job_queue_lock"],
        #'resu,lt_queue': f_vals["result_queue"],
        #'result_queue_lock': f_vals["result_queue_lock"],
        'label': self.args.label,
        'docker_name': self.args.docker_name,
        #'end_jobs': f_vals['end_jobs'],
        'session_id': self.args.session_id
    }

    #adding non-serializable obj when not running through celery
    if not tuning:
      kwargs["machine"] = f_vals["machine"]
      kwargs["job_queue"] = f_vals["job_queue"]
      kwargs["job_queue_lock"] = f_vals["job_queue_lock"]

    return kwargs

  def get_jobs(self, find_state: str, session_id: int) -> bool:
    """Interface function to get jobs based on find_state"""
    raise NotImplementedError("Not implemented")
