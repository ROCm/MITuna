#!/usr/bin/env python3
###############################################################################
#
# MIT License
#
# Copyright (c) 2024 Advanced Micro Devices, Inc.
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
import os
import logging
import subprocess

from tuna.utils.logger import setup_logger
from tuna.libraries import Operation
from tuna.utils.machine_utility import load_machines

LOGGER: logging.Logger = setup_logger('celery_workers')


def launch_worker_per_node(machines, cmd, formatted=False):
  """Launch celery worker for compile"""
  final_cmd = cmd
  subp_list = []
  for machine in machines:
    try:
      if formatted:
        final_cmd = cmd.replace('HOSTNAME', machine.hostname)
      subp = subprocess.Popen(  #pylint: disable=consider-using-with
          final_cmd.split(' '))
      subp_list.append(subp)
    except Exception as exp:  #pylint: disable=broad-exception-caught
      LOGGER.warning(exp)
      return False

    LOGGER.info('Successfully launched celery worker for compile')

  return subp_list


def launch_worker_per_gpu(machines, cmd, formatted=False, gpu_lim=None):
  """Launch celery worker for eval
  
  Args:
    machines: List of machine objects
    cmd: Command template to run
    formatted: Whether to format the command with hostname/gpu_id
    gpu_lim: Optional limit on number of GPUs to use (uses GPUs 0 to gpu_lim-1)
  """
  final_cmd = cmd
  subp_list = []

  for machine in machines:
    all_gpus = machine.get_avail_gpus()
    try:
      if not all_gpus:
        LOGGER.warning(
            'No available GPUs detected, unable to launch celery worker')
        return False
      
      # Apply GPU limit if specified
      if gpu_lim is not None and gpu_lim < len(all_gpus):
        num_gpus = list(range(gpu_lim))
        LOGGER.info("GPU limit applied: using %d of %d available GPUs (GPUs %s)",
                   gpu_lim, len(all_gpus), ', '.join(map(str, num_gpus)))
      else:
        num_gpus = all_gpus
        LOGGER.info("Using all %d available GPUs (GPUs %s)",
                   len(num_gpus), ', '.join(map(str, num_gpus)))
      
      for gpu_id in num_gpus:
        # Create a separate environment for each worker with GPU pinning
        worker_env = dict(os.environ.copy())
        
        # Set GPU pinning using ROCR_VISIBLE_DEVICES
        worker_env['ROCR_VISIBLE_DEVICES'] = str(gpu_id)
        
        if formatted:
          try:
            temp = cmd.replace('HOSTNAME', machine.hostname)
            final_cmd = temp.replace('GPUID', str(gpu_id))
          except Exception as exp:  #pylint: disable=broad-exception-caught
            LOGGER.warning(exp)
            return False
        subp = subprocess.Popen(  #pylint: disable=consider-using-with
            final_cmd.split(),
            env=worker_env)  # Use GPU-pinned environment
        subp_list.append(subp)
        LOGGER.info("Successfully launched celery worker #%s for eval (pinned to GPU %s), pid %s",
                    gpu_id, gpu_id, subp.pid)
    except Exception as exp:  #pylint: disable=broad-exception-caught
      LOGGER.info('Error ocurred: %s', exp)
      return False

  return subp_list


def launch_celery_worker(operation, cmd, args, formatted=False):
  """Helper function to launch celery workers"""
  machines = load_machines(args)
  
  # Get gpu_lim from args if available
  gpu_lim = getattr(args, 'gpu_lim', None)
  if gpu_lim is not None:
    LOGGER.info("GPU limit from args: %d", gpu_lim)
  
  if operation == Operation.COMPILE:
    ret = launch_worker_per_node(machines, cmd, formatted)
  elif operation == Operation.EVAL:
    ret = launch_worker_per_gpu(machines, cmd, formatted, gpu_lim=gpu_lim)
  else:
    raise ValueError('Operation does not support launching celery workers')

  return ret
