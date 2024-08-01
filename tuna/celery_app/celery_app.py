#!/usr/bin/env python3
###############################################################################
#
# MIT License
#
# Copyright (c) 2023 Advanced Micro Devices, Inc.
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
"""Module to define celery app"""
import os
import subprocess
from celery import Celery
from celery.utils.log import get_task_logger

#when dockerized: TUNA_CELERY_BROKER = 'mituna_redis'
TUNA_CELERY_BROKER = 'localhost'
TUNA_REDIS_PORT = '6379'
TUNA_BROKER_PORT = '5672'
TUNA_BROKER_USER = None
TUNA_BROKER_PWD = None
TUNA_BROKER_PORT = None
TUNA_V_HOST = None
LOGGER = get_task_logger("celery_app")

#redis
#if 'TUNA_CELERY_BROKER' in os.environ:
#  TUNA_CELERY_BROKER = os.environ['TUNA_CELERY_BROKER']
#if 'TUNA_REDIS_PORT' in os.environ:
#  TUNA_REDIS_PORT = os.environ['TUNA_REDIS_PORT']

def check_broker_env():
  """Check that env is set up for celery"""
  req_env = [
      'TUNA_BROKER_USER',
      'TUNA_BROKER_PWD',
      'TUNA_V_HOST',
  ]
  for env_var in req_env:
    if env_var not in os.environ:
      raise ValueError('%s must be specified in the environment', env_var)

  return True

def set_broker_env():
  """Set rabbitmq required env vars"""

  if 'TUNA_CELERY_BROKER' in os.environ:
    TUNA_CELERY_BROKER = os.environ['TUNA_CELERY_BROKER']
  if 'TUNA_BROKER_USER' in os.environ:
    TUNA_BROKER_USER = os.environ['TUNA_BROKER_USER']
  if 'TUNA_BROKER_PWD' in os.environ:
    TUNA_BROKER_PWD = os.environ['TUNA_BROKER_PWD']
  if 'TUNA_BROKER_PORT' in os.environ:
    TUNA_BROKER_PORT = os.environ['TUNA_BROKER_PORT']
  if 'TUNA_V_HOST' in os.environ:
    TUNA_V_HOST = os.environ['TUNA_V_HOST']
  if 'TUNA_REDIS_PORT' in os.environ:
    TUNA_REDIS_PORT = os.environ['TUNA_REDIS_PORT']

  return True

check_broker_env()
set_broker_env()

app = Celery('celery_app',
             broker_url="amqp://tuna_user:tuna1234@localhost:5672/myvhost",
             result_backend=f"redis://{TUNA_CELERY_BROKER}:{TUNA_REDIS_PORT}/",
             include=['tuna.miopen.celery_tuning.celery_tasks'])

#app = Celery(
#    'celery_app',
#    broker_url=f"redis://{TUNA_CELERY_BROKER}:{TUNA_REDIS_PORT}/14",
#    result_backend=f"redis://{TUNA_CELERY_BROKER}:{TUNA_REDIS_PORT}/15",
#    include=['tuna.miopen.celery_tuning.celery_tasks'])


def stop_active_workers():
  """Shutdown active workers"""

  LOGGER.warning('Shutting down remote workers')
  try:
    if app.control.inspect().active() is not None:
      app.control.shutdown()
  except Exception as err:  #pylint: disable=broad-exception-caught
    LOGGER.warning('Exception occured while trying to shutdown workers: %s',
                   err)
    return False

  return True


def stop_named_worker(hostname):
  """Shutdown a specific worker"""
  LOGGER.warning('Shutting down remote worker: %s', hostname)
  try:
    app.control.shutdown(destination=[hostname])
  except Exception as exp:  #pylint: disable=broad-exception-caught
    LOGGER.warning('Exception occured while trying to shutdown workers: %s',
                   exp)
    return False

  return True


def purge_queue(q_names):
  """Purge jobs in queue"""
  for q_name in q_names:
    try:
      LOGGER.info('Purging Q %s', q_name)
      cmd = f"celery -A tuna.celery_app.celery_app purge -f -Q {q_name}".split(
          ' ')
      _ = subprocess.Popen(cmd)  #pylint: disable=consider-using-with
    except Exception as exp:  #pylint: disable=broad-exception-caught
      LOGGER.info(exp)
      return False

  return True
