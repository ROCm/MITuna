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
import subprocess
from paramiko.channel import ChannelFile
from tuna.worker_interface import WorkerInterface
from tuna.machine import Machine
from tuna.libraries import Library
from tuna.utils.logger import setup_logger
from tuna.utils.utility import get_env_vars
from tuna.dbBase.sql_alchemy import DbSession
from tuna.celery_app.celery_app import stop_active_workers, stop_named_worker


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

  def get_f_vals(self,
                 machine: Machine,
                 worker_ids: range,
                 tuning=False) -> Dict[str, Any]:
    #pylint:disable=unused-argument
    """Determine kwargs for worker_interface"""
    f_vals: Dict[str, Any]
    f_vals = self.compose_f_vals(machine)
    f_vals['envmt'] = self.get_envmt()

    if not tuning:
      f_vals["num_procs"] = Value('i', len(worker_ids))

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
    f_vals["b_first"] = True

    #adding non-serializable obj when not running through celery
    if not tuning:
      f_vals["machine"] = machine
      f_vals["bar_lock"] = Lock()
      #multiprocess queue for jobs, shared on machine
      f_vals["job_queue"] = mpQueue()
      f_vals["job_queue_lock"] = Lock()
      f_vals["end_jobs"] = Value('i', 0)

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
        'gpu_id': gpu_idx,
        'envmt': envmt,
        'label': self.args.label,
        'docker_name': self.args.docker_name,
        'session_id': self.args.session_id
    }

    #adding non-serializable obj when not running through celery
    if not tuning:
      kwargs["machine"] = f_vals["machine"]
      kwargs["job_queue"] = f_vals["job_queue"]
      kwargs["job_queue_lock"] = f_vals["job_queue_lock"]
      kwargs["num_procs"] = f_vals["num_procs"]
      kwargs["bar_lock"] = f_vals["bar_lock"]
      kwargs["end_jobs"] = f_vals["end_jobs"]
      kwargs["job_queue"] = f_vals["job_queue"]
      kwargs["job_queue_lock"] = f_vals["job_queue_lock"]

    return kwargs

  def get_jobs(self, session: DbSession, find_state: List[str], set_state: str,
               session_id: int, claim_num: int):
    """Interface function to get jobs based on find_state"""
    raise NotImplementedError("Not implemented")

  def shutdown_workers(self):
    """Shutdown all active celery workers regardless of queue"""
    return stop_active_workers()

  def cancel_consumer(self, queue):
    """Cancel consumers for queue"""
    try:
      cmd = f"celery -A tuna.celery_app.celery_app control cancel_consumer {queue}"
      subp = subprocess.Popen(  #pylint: disable=consider-using-with
          cmd,
          stdout=subprocess.PIPE,
          stderr=subprocess.STDOUT,
          shell=True,
          universal_newlines=True)

      #filter the workers by session id
      sess_str = "sess_" + queue.split('_')[-1] + "_"
      stdout, _ = subp.stdout, subp.stderr
      while True:
        line = stdout.readline()
        if not line:
          break
        #stop workers that were feeding from this queue
        if "->" in line and sess_str in line:
          hostname = line.split('->')[1].split()[0].split(':')[0]
          stop_named_worker(hostname)

    except Exception as exp:  #pylint: disable=broad-exception-caught
      self.logger.warning(
          'Error occurred trying to cancel consumer for queue: %s ', queue)
      self.logger.warning(exp)
      return False

    self.logger.info('Sucessfully cancelled consumer for queue: %s', queue)

    return True
