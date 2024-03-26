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

LOGGER: logging.Logger = setup_logger('celery')


def launch_worker_per_node(q_name, machines, session_id):
  """Launch celery worker for compile"""
  for machine in machines:
    cmd = f"celery -A tuna.celery_app.celery_app worker -l info -E -n tuna_{machine.hostname}_sess_{session_id} -Q {q_name}".split(  #pylint: disable=line-too-long
        ' ')
    try:
      _ = subprocess.Popen(cmd)  #pylint: disable=consider-using-with
    except Exception as exp:  #pylint: disable=broad-exception-caught
      LOGGER.warning(exp)
      return False

    LOGGER.info('Successfully launched celery worker for compile')

  return True


def launch_worker_per_gpu(q_name, machines, session_id):
  """Launch celery worker for eval"""
  curr_env = dict(os.environ.copy())
  for machine in machines:
    num_gpus = machine.get_avail_gpus()
    try:
      for gpu_id in num_gpus:
        cmd = f"celery -A tuna.celery_app.celery_app worker -l info -E -c 1 -n tuna_{machine.hostname}_sess_{session_id}_gpu_id{gpu_id} -Q {q_name}".split(' ')  #pylint: disable=line-too-long
        curr_env['HIP_VISIBLE_DEVICES'] = str(gpu_id)
        _ = subprocess.Popen(cmd, env=curr_env)  #pylint: disable=consider-using-with
        LOGGER.info("Successfully launched celery worker #%s for eval", gpu_id)
    except Exception as exp:  #pylint: disable=broad-exception-caught
      LOGGER.warning(exp)
      return False

  return True


def launch_celery_worker(library, q_name, machines, worker_granularity):
  """Helper function to launch celery workers"""
  if worker_granularity == 'worker_per_node':
    ret = launch_worker_per_node(q_name, machines, library.dbt.session_id)
  elif worker_granularity == 'worker_per_gpu':
    ret = launch_worker_per_gpu(q_name, machines, library.dbt.session_id)
  else:
    raise ValueError('Operation does not support celery workers')

  return ret
