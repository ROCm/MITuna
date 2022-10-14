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
"""Utility module for helper functions"""

import os
from tuna.utils.logger import setup_logger
from tuna.sql import DbCursor

LOGGER = setup_logger('utility')

QTS_LIST = {}


def arch2targetid(arch):
  """ Convert arch to target ID """
  targetid = ""
  if arch == 'gfx1030':
    targetid = arch
  elif arch == 'gfx900':
    targetid = f'{arch}:xnack-'
  else:
    targetid = f'{arch}:sram-ecc+:xnack-'
  return targetid


def split_packets(elements, pack_sz=1000):
  """break elements into smaller packets"""
  pack_i = 0
  pack = []
  all_packs = []
  for elem in elements:
    pack.append(elem)
    pack_i += 1
    if pack_i == pack_sz:
      all_packs.append(pack)
      pack = []
      pack_i = 0
  if pack:
    all_packs.append(pack)

  return all_packs


def get_filter_time(time_arr):
  """Get filter time"""
  rmid = len(time_arr) // 3
  warm_times = time_arr[rmid:]
  warm_mean = sum(warm_times) / len(warm_times)

  variance = sum(
      (pow(x_var - warm_mean, 2) for x_var in warm_times)) / len(warm_times)
  std_dev = pow(variance, 1 / 2)
  filter_warm = []
  for time in warm_times:
    if abs(time - warm_mean) <= std_dev:
      filter_warm.append(time)
  filter_mean = sum(filter_warm) / len(filter_warm)

  return filter_mean


def check_qts(hostname, logger=LOGGER):
  """find if hostname string has a local ip in qts"""
  if hostname in QTS_LIST:
    return QTS_LIST[hostname]
  if hostname.startswith('192.168'):
    QTS_LIST[hostname] = True
    return True

  inner_qts = False
  with DbCursor() as cur:
    # pylint: disable=consider-using-f-string
    query = "SELECT local_ip FROM machine WHERE remarks='{0}' OR hostname='{0}'"\
            " OR local_ip='{0}';".format(hostname)
    cur.execute(query)
    res = cur.fetchall()

    if res:
      local_ip = res[0][0]
      logger.info('local ip = %s', local_ip)
      if local_ip:
        inner_qts = True

  logger.info('inner_qts = %s', inner_qts)
  QTS_LIST[hostname] = inner_qts
  return inner_qts


def get_env_vars():
  """Utility function to get Tuna specific env_vars"""
  env_vars = {}
  if 'TUNA_DB_USER_NAME' in os.environ:
    env_vars['user_name'] = os.environ['TUNA_DB_USER_NAME']
  else:
    env_vars['user_name'] = ''
  if 'TUNA_DB_USER_PASSWORD' in os.environ:
    env_vars['user_password'] = os.environ['TUNA_DB_USER_PASSWORD']
  else:
    env_vars['user_password'] = ''
  if 'TUNA_DB_HOSTNAME' in os.environ:
    env_vars['db_hostname'] = os.environ['TUNA_DB_HOSTNAME']
  else:
    env_vars['db_hostname'] = 'localhost'
  if 'TUNA_DB_NAME' in os.environ:
    env_vars['db_name'] = os.environ['TUNA_DB_NAME']
  else:
    env_vars['db_name'] = ''
  if 'SLURM_CPUS_ON_NODE' in os.environ:
    env_vars['slurm_cpus'] = int(os.environ['SLURM_CPUS_ON_NODE'])
  else:
    env_vars['slurm_cpus'] = 0

  return env_vars


# pylint: disable=dangerous-default-value ; @ chris, might want to reconsider though
def get_mmi_env_vars(env_vars={}):
  """Utility function to get machine management interface specific env vars"""
  if 'gateway_ip' in os.environ:
    env_vars['gateway_ip'] = os.environ['gateway_ip']
  else:
    env_vars['gateway_ip'] = None
  if 'gateway_port' in os.environ:
    env_vars['gateway_port'] = os.environ['gateway_port']
  else:
    env_vars['gateway_port'] = None
  if 'gateway_user' in os.environ:
    env_vars['gateway_user'] = os.environ['gateway_user']
  else:
    env_vars['gateway_user'] = None

  return env_vars


class DotDict(dict):
  """dot.notation access to dictionary attributes"""
  __getattr__ = dict.get
  __setattr__ = dict.__setitem__
  __delattr__ = dict.__delitem__
