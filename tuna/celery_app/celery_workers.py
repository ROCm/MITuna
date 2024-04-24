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

LOGGER: logging.Logger = setup_logger('celery_workers')


def launch_worker_per_node(machines, cmd, formatted=False):
  """Launch celery worker for compile"""
  final_cmd = cmd
  pid_list = []
  for machine in machines:
    try:
      if formatted:
        final_cmd = cmd.replace('HOSTNAME', machine.hostname)
      subp = subprocess.Popen(  #pylint: disable=consider-using-with
          final_cmd.split(' '))
      pid_list.append(subp.pid)
    except Exception as exp:  #pylint: disable=broad-exception-caught
      LOGGER.warning(exp)
      return False

    LOGGER.info('Successfully launched celery worker for compile')

  return pid_list


def launch_worker_per_gpu(machines, cmd, formatted=False):
  """Launch celery worker for eval"""
  curr_env = dict(os.environ.copy())
  final_cmd = cmd
  pid_list = []

  for machine in machines:
    num_gpus = machine.get_avail_gpus()
    try:
      if not num_gpus:
        LOGGER.warning(
            'No available GPUs detected, unable to launch celery worker')
        return False
      for gpu_id in num_gpus:
        if formatted:
          try:
            temp = cmd.replace('HOSTNAME', machine.hostname)
            final_cmd = temp.replace('GPUID', str(gpu_id))
          except Exception as exp:  #pylint: disable=broad-exception-caught
            LOGGER.warning(exp)
            return False
        curr_env['HIP_VISIBLE_DEVICES'] = str(gpu_id)
        subp = subprocess.Popen(  #pylint: disable=consider-using-with
            final_cmd.split(),
            env=curr_env)
        pid_list.append(subp)
        LOGGER.info("Successfully launched celery worker #%s for eval", gpu_id)
    except Exception as exp:  #pylint: disable=broad-exception-caught
      LOGGER.info('Error ocurred: %s', exp)
      return False

  return pid_list


def launch_celery_worker(machines, worker_granularity, cmd, formatted=False):
  """Helper function to launch celery workers"""
  if worker_granularity == 'worker_per_node':
    ret = launch_worker_per_node(machines, cmd, formatted)
  elif worker_granularity == 'worker_per_gpu':
    ret = launch_worker_per_gpu(machines, cmd, formatted)
  else:
    raise ValueError('Operation does not support celery workers')

  return ret
