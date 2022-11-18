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
"""Module that encapsulates the DB representation of a Driver cmd"""
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query
from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.logger import setup_logger
from tuna.miopen.miopen_tables import TensorTable
from tuna.metadata import TENSOR_PRECISION
from tuna.parsing import parse_line

LOGGER = setup_logger('driver_base')


#pylint: disable=no-member
#pylint: disable=too-many-instance-attributes
#NOTE:remove pylint flag after driver implementation throughout code
class DriverBase():
  """Represents db tables based on ConfigType"""

  def __init__(self, line=None, db_obj=None):
    if line:
      if not self.construct_driver(line):
        raise ValueError(f"Error creating Driver from line: '{line}'")
    elif db_obj:
      if not self.construct_driver_from_db(db_obj):
        raise ValueError(
            f"Error creating Driver from db obj: '{db_obj.to_dict()}'")
    else:
      raise ValueError(
          "Error creating Driver. MIOpen Driver cmd line or db_obj required")

  @staticmethod
  def get_common_cols():
    """Returns common MIOpenDriver command line args"""
    return ['wall', 'time', 'iter', 'verify']

  def construct_driver(self, line):
    """Takes a MIOpenDriver cmd or PDB key"""

    LOGGER.info('Processing line: %s', line)
    if line.find('=') != -1:
      self.parse_fdb_key(line)
    elif line.find('MIOpenDriver') != -1:
      self.parse_driver_line(line)
    else:
      LOGGER.warning('Skipping line: %s', line)
      return False

    self.config_set_defaults()

    return True

  def construct_driver_from_db(self, db_obj):
    """Takes a <>_config row and returns a driver cmd"""
    LOGGER.info('Processing db_row: %s', db_obj.to_dict())
    #common tensor among convolution and batch norm
    self.decompose_input_t(db_obj)
    self.parse_row(db_obj)

    return True

  @staticmethod
  def get_tensor_id(session, tensor_dict):
    """Return tensor id based on dict"""

    query = Query(TensorTable.id).filter_by(**tensor_dict)
    ret_id = None
    try:
      res = session.execute(query).fetchall()
      if len(res) > 1:
        LOGGER.error(tensor_dict)
        for row in res:
          LOGGER.error(row)
        raise ValueError('Tensor table duplication. Only one row should match')
      if not res:
        raise ValueError('Missing from Tensor table. One row should match')
      ret_id = res[0][0]
    except IntegrityError as err:
      session.rollback()
      LOGGER.error("Error occurred: %s \n", err)
      raise ValueError(
          'Something went wrong with getting input tensor id from tensor table'
      ) from err
    except IndexError as err:
      raise ValueError(f'Tensor not found in table: {tensor_dict}') from err

    return ret_id

  def insert_tensor(self, tensor_dict):
    """Insert new row into tensor table and return primary key"""

    ret_id = None
    with DbSession() as session:
      try:
        tid = TensorTable(**tensor_dict)
        session.add(tid)
        session.commit()
        ret_id = tid.id
        LOGGER.info("Insert Tensor: %s", ret_id)
      except IntegrityError as err:
        LOGGER.warning(err)
        session.rollback()
        ret_id = self.get_tensor_id(session, tensor_dict)
        LOGGER.info("Get Tensor: %s", ret_id)

    return ret_id

  def get_input_t_id(self):
    """Build 1 row in tensor table based on layout from fds param
       Details are mapped in metadata LAYOUT"""
    i_dict = self.compose_input_t()

    return self.insert_tensor(i_dict)

  def compose_input_t(self):
    """Build input_tensor"""
    i_dict = {}
    i_dict['data_type'] = TENSOR_PRECISION[self.cmd]
    i_dict['num_dims'] = self.num_dims
    i_dict['dim0'] = 1

    if self.in_layout in ('NCHW', 'NCDHW'):
      i_dict['dim1'] = self.in_channels
      i_dict['dim2'] = self.in_d
      i_dict['dim3'] = self.in_h
      i_dict['dim4'] = self.in_w
      i_dict['layout'] = self.in_layout
    elif self.in_layout == 'NHWC':
      i_dict['dim1'] = self.in_d
      i_dict['dim2'] = self.in_h
      i_dict['dim3'] = self.in_w
      i_dict['dim4'] = self.in_channels
      i_dict['layout'] = self.in_layout

    return i_dict

  def decompose_input_t(self, db_obj):
    """Use input_tensor to assign local variables to build driver cmd """
    #pylint: disable=attribute-defined-outside-init

    self.set_cmd(db_obj.input_t.data_type)
    self.num_dims = db_obj.input_t.num_dims
    self.in_layout = db_obj.input_t.layout

    if self.in_layout == 'NCHW':
      self.in_channels = db_obj.input_t.dim1
      self.in_d = db_obj.input_t.dim2
      self.in_h = db_obj.input_t.dim3
      self.in_w = db_obj.input_t.dim4
    elif self.in_layout == 'NHWC':
      self.in_d = db_obj.input_t.dim1
      self.in_h = db_obj.input_t.dim2
      self.in_w = db_obj.input_t.dim3
      self.in_channels = db_obj.input_t.dim4

    return True

  def get_weight_t_id(self):
    """Build 1 row in tensor table based on layout from fds param
     Details are mapped in metadata LAYOUT"""
    w_dict = self.compose_weight_t()

    return self.insert_tensor(w_dict)

  def parse_driver_line(self, line):
    """Parse line and set attributes"""
    line = parse_line(line)
    tok = line.split()
    #pylint: disable=attribute-defined-outside-init
    self.cmd = tok[1]
    assert tok[1] != ''

    self.compose_fds(tok, line)

  def compose_fds(self, tok, line):
    """Compose fds from driver line"""

    for (tok1, tok2) in zip(tok[2::2], tok[3::2]):
      # the following would not work for a full name argument
      if tok1[0] == '-':
        tok1 = tok1[1:]
      if self.test_skip_arg(tok1):
        continue
      tok2 = tok2.strip()
      if tok2.isdigit():
        tok2 = int(tok2)
      tok1 = self.get_params(tok1)
      if self.get_check_valid(tok1[0], tok2):
        setattr(self, tok1[0], tok2)
      else:
        raise ValueError(
            f'Invalid command line arg for {self.cmd}: {tok1[0]} - {tok2} line: {line}'
        )

    return True

  def to_dict(self):
    """Return class to dictionary"""
    copy_dict = {}
    for key, value in vars(self).items():
      if key == "_cmd":
        copy_dict["cmd"] = value
      else:
        copy_dict[key] = value
    return copy_dict

  def __eq__(self, other):
    """Defining equality functionality"""
    if self.__class__ != other.__class__:
      return False
    return vars(self) == vars(other)
