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

import random
from time import sleep
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Query

from tuna.utils.logger import setup_logger
from tuna.dbBase.sql_alchemy import DbSession
from tuna.machine import Machine
from tuna.utils.utility import check_qts
from tuna.metadata import MYSQL_LOCK_WAIT_TIMEOUT, CONV_CONFIG_COLS, TENSOR_PRECISION
from tuna.metadata import BN_DEFAULTS, BN_CONFIG_COLS
from tuna.metadata import FUSION_DEFAULTS, CONV_2D_DEFAULTS, CONV_3D_DEFAULTS
from tuna.worker_interface import NUM_SQL_RETRIES
from tuna.miopen_tables import TensorTable, Session
from tuna.config_type import ConfigType
from tuna.metadata import get_solver_ids

LOGGER = setup_logger('helper')


#NOTE:remove pylint flag after driver implementation throughout code
#pylint: disable=duplicate-code
def get_qts_machine_data(mid, mhost, slogger):
  """Get machine local QTS info"""
  with DbSession() as session:
    query = session.query(Machine).filter(Machine.id == mid)
    rows = query.all()

    if rows:
      machine_obj = rows[0][0]
      machine_cfg = machine_obj.to_dict()
      machine_cfg['logger'] = slogger
      if check_qts(mhost):
        machine_cfg['hostname'] = machine_cfg['local_ip']
        machine_cfg['port'] = machine_cfg['local_port']
    else:
      slogger.warning('No machine found mid %u', mid)
      return None

    return machine_cfg


def print_solvers():
  """Pretty print solvers list"""
  slv_dict, _ = get_solver_ids()
  for name, sid in slv_dict.items():
    print("{0:>4} - {1}".format(sid, name))


# fill in the missing columns with defaults to avoid duplicate entries
def config_set_defaults(fds):
  """Setting config DB defaults to avoid duplicates through SELECT"""
  if 'conv' in fds['cmd']:
    if 'spatial_dim' in fds and fds['spatial_dim'] == 3:
      fds = set_defaults(fds, CONV_3D_DEFAULTS)
    else:
      fds = set_defaults(fds, CONV_2D_DEFAULTS)
  elif 'cbainfer' in fds['cmd']:
    fds = set_defaults(fds, FUSION_DEFAULTS)
  elif 'bnorm' in fds['cmd']:
    fds = set_defaults(fds, BN_DEFAULTS)


def set_defaults(fds, defaults):
  """Set fds defaults"""
  for k, val in defaults.items():
    if k not in fds:
      fds[k] = val

  return fds


def valid_cfg_dims(in_perf_cfg):
  """prune 3rd dimension off 2d config"""
  perf_cfg = in_perf_cfg.copy()
  keys = list(perf_cfg.keys())[:]

  if 'spatial_dim' not in perf_cfg or perf_cfg['spatial_dim'] < 3:
    for key in keys:
      if key.endswith("_d"):
        perf_cfg[key] = CONV_2D_DEFAULTS[key]

  return perf_cfg


def prune_cfg_dims(in_perf_cfg):
  """prune 3rd dimension off 2d config"""
  perf_cfg = in_perf_cfg.copy()
  keys = list(perf_cfg.keys())[:]

  if 'spatial_dim' not in perf_cfg or perf_cfg['spatial_dim'] < 3:
    for key in keys:
      if key.endswith("_d"):
        perf_cfg.pop(key)

  return perf_cfg


def mysqldb_insert_dict(table, in_dict, filter_dict):
  """insert/update dict obj to mysql table"""
  with DbSession() as session:
    for idx in range(NUM_SQL_RETRIES):
      try:
        query = session.query(table).filter_by(**filter_dict)
        query = query.order_by(table.id.asc())
        res = query.first()

        if res:
          LOGGER.warning("%s update : %s", table.__tablename__, in_dict)
          query = session.query(table).filter(table.id == res.id)
          query.update(in_dict, synchronize_session='fetch')
          session.commit()
          return True, res.id

        LOGGER.warning("%s insert : %s", table.__tablename__, in_dict)
        entry = table(**in_dict)
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return True, entry.id

      except OperationalError as error:
        handle_op_error(LOGGER, error)
      except IntegrityError as error:
        session.rollback()
        LOGGER.warning('insert failed (%s) attempt %s, retrying ... ', error,
                       idx)
        sleep(5)

    return False, -1


def mysqldb_overwrite_table(table, dict_list, filter_cols):
  """insert/update rows to mysql"""
  insert_ids = []
  ret = False
  for i, in_dict in enumerate(dict_list):
    filter_dict = {}
    for col in filter_cols:
      filter_dict[col] = in_dict[col]

    ret, ins_id = mysqldb_insert_dict(table, in_dict, filter_dict)
    if ret:
      insert_ids.append(ins_id)
    else:
      return False, insert_ids

    if i % 100 == 0:
      LOGGER.info('Inserting sql... %s', i)

  return ret, insert_ids


def handle_op_error(logger, error):
  """error handling for sql OperationalError"""
  if error.orig.args[0] == MYSQL_LOCK_WAIT_TIMEOUT:
    logger.warning('Db contention, sleeping ...')
    sleep(random.randint(1, 30))
  else:
    raise error


#DEPRECATED
def get_conv_dict(c_dict, fds):
  """Compose db cols for conv_config table"""
  for col in CONV_CONFIG_COLS:
    if col in fds.keys():
      c_dict[col] = fds[col]

  c_dict['input_tensor'] = get_input_t_id(fds)
  c_dict['weight_tensor'] = get_weight_t_id(fds)

  return c_dict


#DEPRECATED
def get_bn_dict(c_dict, fds):
  """Compose db cols for BN table"""
  for col in BN_CONFIG_COLS:
    if col in fds.keys():
      c_dict[col] = fds[col]

  c_dict['input_tensor'] = get_input_t_id(fds)

  return c_dict


#DEPRECATED
def compose_tensors(fds, args, keep_id=False):
  """Get tensors needed for DB table based on config type"""
  c_dict = {}
  if args.config_type is ConfigType.batch_norm:
    get_bn_dict(c_dict, fds)
  else:
    c_dict = get_conv_dict(c_dict, fds)

  if keep_id:
    c_dict['id'] = fds['id']

  return c_dict


#DEPRECATED
def insert_tensor(fds, tensor_dict):
  """Insert new row into tensor table and return primary key"""

  set_tensor_defaults(fds, tensor_dict)

  ret_id = None
  with DbSession() as session:
    try:
      tid = TensorTable(**tensor_dict)
      session.add(tid)
      session.commit()
      ret_id = tid.id
    except IntegrityError:
      session.rollback()
      ret_id = get_tid(session, tensor_dict)

  return ret_id


#DEPRECATED
def get_tid(session, tensor_dict):
  """Return tensor id based on dict"""

  query = Query(TensorTable.id).filter_by(**tensor_dict)
  ret_id = None
  try:
    res = session.execute(query).fetchall()
    if len(res) != 1:
      raise ValueError('Tensor table duplication. Only one row should match')
    ret_id = res[0][0]
  except IntegrityError as err:
    LOGGER.error("Error occurred: %s \n", err)
    raise ValueError(
        'Something went wrong with getting input tensor id from tensor table')
  except IndexError:
    raise ValueError('Tensor not found in table: {}'.format(tensor_dict))

  return ret_id


#DEPRECATED
def get_input_t_id(fds):
  """Build 1 row in tensor table based on layout from fds param
     Details are mapped in metadata LAYOUT"""
  i_dict = compose_input_t(fds, {})

  return insert_tensor(fds, i_dict)


#DEPRECATED
def get_weight_t_id(fds):
  """Build 1 row in tensor table based on layout from fds param
     Details are mapped in metadata LAYOUT"""
  w_dict = compose_weight_t(fds, {})

  return insert_tensor(fds, w_dict)


#DEPRECATED
def compose_weight_t(fds, w_dict):
  """Build weight_tensor dict from fds"""

  if 'fil_layout' not in fds.keys():
    fds['fil_layout'] = 'NCHW'

  if fds['fil_layout'] == 'NCHW':
    w_dict['dim0'] = fds['out_channels']
    w_dict['dim1'] = fds['in_channels']
    w_dict['dim2'] = fds['fil_d']
    w_dict['dim3'] = fds['fil_h']
    w_dict['dim4'] = fds['fil_w']
    w_dict['layout'] = 'NCHW'
  elif fds['fil_layout'] == 'NHWC':
    w_dict['dim0'] = fds['out_channels']
    w_dict['dim1'] = fds['in_channels']
    w_dict['dim2'] = fds['fil_d']
    w_dict['dim3'] = fds['fil_h']
    w_dict['dim4'] = fds['fil_w']
    w_dict['layout'] = 'NHWC'
  if 'cmd' in fds:
    w_dict['data_type'] = TENSOR_PRECISION[fds['cmd']]

  return w_dict


#DEPRECATED
def compose_input_t(fds, i_dict):
  """Build input_tensor dict from fds"""

  i_dict['dim0'] = 1

  if 'in_layout' not in fds.keys():
    fds['in_layout'] = 'NCHW'

  if fds['in_layout'] == 'NCHW':
    i_dict['dim1'] = fds['in_channels']
    i_dict['dim2'] = fds['in_d']
    i_dict['dim3'] = fds['in_h']
    i_dict['dim4'] = fds['in_w']
    i_dict['layout'] = 'NCHW'
  elif fds['in_layout'] == 'NHWC':
    i_dict['dim1'] = fds['in_d']
    i_dict['dim2'] = fds['in_h']
    i_dict['dim3'] = fds['in_w']
    i_dict['dim4'] = fds['in_channels']
    i_dict['layout'] = 'NHWC'
  if 'cmd' in fds:
    i_dict['data_type'] = TENSOR_PRECISION[fds['cmd']]

  return i_dict


#DEPRECATED
def set_tensor_defaults(fds, tensor_dict):
  """Set tensor num_dims and data_type"""
  if 'spatial_dim' in fds.keys():
    tensor_dict['num_dims'] = fds['spatial_dim']
  else:
    tensor_dict['num_dims'] = 2

  if 'data_type' not in tensor_dict:
    tensor_dict['data_type'] = 'FP32'

  return tensor_dict


def get_db_id(db_elems, config_table):
  """Return unique DB id for config dict"""
  cid = None
  query = Query(config_table.id).filter_by(**db_elems)
  with DbSession() as session:
    try:
      res = session.execute(query).fetchall()
      session.commit()
    except IntegrityError as err:
      session.rollback()
      LOGGER.error("Error occurred: %s \n", err)
      return False
    if res:
      cid = res[0][0]
  return cid


def add_new_session(args, worker):
  """Add new session entry"""
  new_sesh_id = None
  session_entry = Session()
  session_entry.arch = args.arch
  session_entry.num_cu = args.num_cu
  session_entry.rocm_v = worker.get_branch_hash()
  session_entry.miopen_v = worker.get_rocm_v()
  session_entry.reason = args.label
  if args.ticket:
    session_entry.ticket = args.ticket
  session_entry.docker = args.docker_name

  with DbSession() as session:
    try:
      session.add(session_entry)
      session.commit()
      session.flush(session_entry)
      new_sesh_id = session_entry.id
      LOGGER.info('Added new session id: %s', session_entry.id)
    except IntegrityError as err:
      LOGGER.warning("Err occurred trying to add new session: %s \n %s", err,
                     session_entry)

  return new_sesh_id
