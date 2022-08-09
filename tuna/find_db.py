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
"""find db class"""
from sqlalchemy import Column, Integer, String, UniqueConstraint, ForeignKey, orm
from sqlalchemy import Float, BigInteger, Boolean, and_
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declared_attr

from tuna.dbBase.base_class import BASE

FDB_SLV_NUM_FIELDS = 5


class FindDBMixin():  # pylint: disable=too-many-instance-attributes
  """Represents find_db Mixin for find_db concrete classes with
     methods and data for reading / writing find db
  """
  __table_args__ = {'mysql_engine': 'InnoDB'}
  __mapper_args__ = {'always_refresh': True}

  @declared_attr
  def solver(self):
    """solver column"""
    return Column(Integer, ForeignKey("solver.id"), nullable=False)

  @declared_attr
  def session(self):
    """session column"""
    return Column(Integer, ForeignKey("session.id"), nullable=False)

  fdb_key = Column(String(length=128), nullable=True)
  kernel_time = Column(Float, nullable=False)
  workspace_sz = Column(BigInteger, nullable=False)
  alg_lib = Column(String(length=64), nullable=True)
  opencl = Column(Boolean, nullable=False)

  def get_query(self, sess, fdb_obj, slv_app, session_id):
    """Construct a Db query for the find object
    """

    # CE: Solver applicability can change between miopen versions
    # find if this fdb entry is currently applicable
    query = sess.query(fdb_obj, slv_app).filter(
        and_(fdb_obj.session == session_id, slv_app.session == session_id,
             fdb_obj.config == self.config, fdb_obj.opencl == self.opencl),
        fdb_obj.valid == 1, fdb_obj.solver == slv_app.solver,
        fdb_obj.config == slv_app.config, slv_app.applicable == 1)

    if self.solver:
      query = query.filter(fdb_obj.solver == self.solver)

    fdb_entries = query.all()
    if not fdb_entries:
      self.logger.warning(
          "No applicable fdb entries for config %s, session id %s", self.config,
          session_id)
    ids = tuple([str(fdb_e.id) for fdb_e, _ in fdb_entries])
    query = sess.query(fdb_obj).filter(fdb_obj.id.in_(ids))

    return query

  def parse(self, decoded_line):
    """parse logger output line for find db data """
    retval = False
    if '[SetValues]' in decoded_line:
      message = decoded_line.split('[SetValues]')[1]
      key = message.split(',')[0].strip()

      if key != '':
        fdb = {}
        direction = key.split('-')[-1][:1]
        lead_str = 'content inserted: '
        #each entry has 5 fields, 0 - alg:slv, 1 - kernel_time, 2 - workspace size,
        #3 - alg, 4 - kernel cache key
        idx_start = message.index(lead_str) + len(lead_str)
        slv_info = message[idx_start:]
        columns = slv_info.split(',')
        while len(columns) >= FDB_SLV_NUM_FIELDS:
          (_, slv) = columns[0].split(':')
          if slv not in self.fdb_slv_dir:
            self.fdb_slv_dir[slv] = {}
          if direction not in self.fdb_slv_dir[slv]:
            self.fdb_slv_dir[slv][direction] = {}
            if 'ktimes' not in self.fdb_slv_dir[slv][direction]:
              self.fdb_slv_dir[slv][direction]['ktimes'] = []

          fdb = self.fdb_slv_dir[slv][direction]

          fdb['fdb_key'] = key
          kernel_time = float(columns[1])
          fdb['workspace_size'] = int(columns[2])
          fdb['alg_lib'] = columns[3]
          fdb['kcache_key'] = columns[4]
          fdb['is_ocl'] = 0
          if 'MIOpen(OpenCL)' in decoded_line:
            fdb['is_ocl'] = 1

          fdb['ktimes'].append(kernel_time)

          self.fdb_slv_dir[slv][direction] = fdb

          retval = True

          for _ in range(FDB_SLV_NUM_FIELDS):
            columns.pop(0)

    return retval


class ConvolutionFindDB(BASE, FindDBMixin):  #pylint: disable=too-many-instance-attributes
  """Concrete convolution find_db class"""
  __tablename__ = "conv_find_db"
  __table_args__ = (UniqueConstraint("config",
                                     "solver",
                                     "fdb_key",
                                     "alg_lib",
                                     "opencl",
                                     "session",
                                     name="uq_idx"),)

  config = Column(Integer, ForeignKey("conv_config.id"), nullable=False)
  blobs = relationship("ConvolutionKernelCache",
                       back_populates="conv_find_db_entries",
                       cascade="all, delete-orphan")

  @orm.reconstructor
  def __init__(self, **kwargs):
    self.logger = kwargs['logger'] if 'logger' in kwargs.keys() else None  #pylint: disable=multiple-statements
    self.fdb_slv_dir = {}


class BNFindDB(BASE, FindDBMixin):  #pylint: disable=too-many-instance-attributes
  """Concrete batch norm find_db class"""
  __tablename__ = "bn_find_db"
  __table_args__ = (UniqueConstraint("config",
                                     "solver",
                                     "fdb_key",
                                     "alg_lib",
                                     "opencl",
                                     name="uq_idx"),)

  config = Column(Integer, ForeignKey("bn_config.id"), nullable=False)
  blobs = relationship("BNKernelCache",
                       back_populates="bn_find_db_entries",
                       cascade="all, delete-orphan")

  @orm.reconstructor
  def __init__(self, **kwargs):
    self.logger = kwargs.get('logger', None)  #pylint: disable=multiple-statements
    self.fdb_slv_dir = {}
