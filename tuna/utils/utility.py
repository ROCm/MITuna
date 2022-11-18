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
from multiprocessing import Value, Lock, Queue as mpQueue
from tuna.utils.logger import setup_logger
from tuna.sql import DbCursor
from tuna.config_type import ConfigType

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

def compose_f_vals(args, machine):
  """! Compose dict for WorkerInterface constructor
    @param args The command line arguments
    @param machine Machine instance
  """
  f_vals = {}
  f_vals["barred"] = Value('i', 0)
  f_vals["bar_lock"] = Lock()
  #multiprocess queue for jobs, shared on machine
  f_vals["job_queue"] = mpQueue()
  f_vals["job_queue_lock"] = Lock()
  f_vals["result_queue"] = mpQueue()
  f_vals["result_queue_lock"] = Lock()
  f_vals["machine"] = machine
  f_vals["envmt"] = get_envmt(args)
  f_vals["b_first"] = True
  f_vals["end_jobs"] = Value('i', 0)

  return f_vals


def get_envmt(args):
  """! Function to construct environment var
     @param args The command line arguments
  """
  envmt = ["MIOPEN_LOG_LEVEL=4"]

  envmt.append("MIOPEN_SQLITE_KERN_CACHE=ON")
  envmt.append("MIOPEN_DEBUG_IMPLICIT_GEMM_FIND_ALL_SOLUTIONS=1")

  if args.find_mode:
    envmt.append(f"MIOPEN_FIND_MODE={args.find_mode}")

  if args.blacklist:
    bk_str = ", ".join([f"{arg}=0" for arg in args.blacklist])
    for bk_var in bk_str.split(','):
      envmt.append(bk_var)

  return envmt


def get_kwargs(gpu_idx, f_vals, args):
  """! Helper function to set up kwargs for worker instances
    @param gpu_idx Unique ID of the GPU
    @param f_vals Dict containing runtime information
    @param args The command line arguments
  """
  envmt = f_vals["envmt"].copy()
  if args.config_type is None:
    args.config_type = ConfigType.convolution

  kwargs = {
      'machine': f_vals["machine"],
      'gpu_id': gpu_idx,
      'num_procs': f_vals["num_procs"],
      'barred': f_vals["barred"],
      'bar_lock': f_vals["bar_lock"],
      'envmt': envmt,
      'reset_interval': args.reset_interval,
      'fin_steps': args.fin_steps,
      'dynamic_solvers_only': args.dynamic_solvers_only,
      'job_queue': f_vals["job_queue"],
      'job_queue_lock': f_vals["job_queue_lock"],
      'result_queue': f_vals["result_queue"],
      'result_queue_lock': f_vals["result_queue_lock"],
      'label': args.label,
      'docker_name': args.docker_name,
      'end_jobs': f_vals['end_jobs'],
      'config_type': args.config_type,
      'session_id': args.session_id
  }

  return kwargs
