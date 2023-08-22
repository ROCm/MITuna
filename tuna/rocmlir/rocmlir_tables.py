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
""" The necessary tables for rocMLIR tuning integration.
    Copied and adapted from example and miopen support.
"""

import sys
import enum
from typing import List
from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy import Text, Enum, Float, DateTime, orm
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.sql import func as sqla_func
from sqlalchemy.inspection import inspect

from tuna.dbBase.sql_alchemy import DbSession
from tuna.dbBase.base_class import BASE
from tuna.machine import Machine
from tuna.session_mixin import SessionMixin
from tuna.utils.logger import setup_logger
from tuna.tables_interface import DBTablesInterface

#pylint: disable=too-few-public-methods


class SessionRocMLIR(BASE, SessionMixin):
  """Session table to keep track of tuning sessions"""
  #pylint: disable=attribute-defined-outside-init

  mlir_v = Column(String(length=64), nullable=False)

  __tablename__ = "session_rocmlir"
  __table_args__ = (UniqueConstraint("arch",
                                     "num_cu",
                                     "rocm_v",
                                     "mlir_v",
                                     "reason",
                                     name="uq_idx"),)

  def get_query(self, sess, sess_obj, entry):
    """get session matching this object"""
    query = sess.query(sess_obj.id)\
        .filter(sess_obj.arch == entry.arch)\
        .filter(sess_obj.num_cu == entry.num_cu)\
        .filter(sess_obj.rocm_v == entry.rocm_v)\
        .filter(sess_obj.mlir_v == entry.mlir_v)\
        .filter(sess_obj.reason == entry.reason)\

    return query

  def add_new_session(self, args, worker):
    """Add new session entry"""
    super().add_new_session(args, worker)

    if hasattr(args, 'mlir_v') and args.mlir_v:
      self.mlir_v = args.mlir_v
    else:
      self.mlir_v = worker.get_mlir_v()

    return self.insert_session()


class JobEnum(enum.Enum):
  """Job status.  Numbers chosen to match miopen, which has more states."""
  # pylint: disable=invalid-name ; names represent entries in job_enum column
  # pylint: disable=duplicate-code
  new = 1
  running = 3
  completed = 4
  error = 5


class JobMixin():
  """Essential attributes for all jobs in the job tables"""

  @declared_attr
  def session(self):
    """session key, as a function to connect at run time"""
    return Column(Integer, ForeignKey("session_rocmlir.id"), nullable=False)

  reason = Column(String(length=60), nullable=False, server_default="")
  state = Column(Enum(JobEnum), nullable=False, server_default="new")
  retries = Column(Integer, nullable=False, server_default="0")
  result = Column(Text, nullable=True)

  compile_start = Column(DateTime,
                         nullable=False,
                         server_default=sqla_func.now())
  compile_end = Column(DateTime, nullable=False, server_default=sqla_func.now())
  gpu_id = Column(Integer, nullable=False, server_default="-1")
  machine_name = Column(String(length=60), nullable=False, server_default="")


class ConvolutionJob(BASE, JobMixin):
  """Represents convolutions job table"""
  __tablename__ = "rocmlir_conv_job"
  __table_args__ = (UniqueConstraint('config', 'session', name="uq_idx"),)

  config = Column(Integer,
                  ForeignKey("rocmlir_conv_config.id"),
                  nullable=False,
                  index=True)


class ConvolutionConfig(BASE):
  """Represents convolution config table"""
  __tablename__ = "rocmlir_conv_config"

  data_type = Column(String(length=60), nullable=False, server_default="")
  fil_layout = Column(String(60), nullable=False, server_default="NCHW")
  in_layout = Column(String(60), nullable=False, server_default="NCHW")
  out_layout = Column(String(60), nullable=False, server_default="NCHW")
  direction = Column(String(length=8), nullable=False)
  in_channels = Column(Integer, nullable=False, server_default="0")
  in_h = Column(Integer, nullable=False, server_default="0")
  in_w = Column(Integer, nullable=False, server_default="0")
  fil_h = Column(Integer, nullable=False, server_default="0")
  fil_w = Column(Integer, nullable=False, server_default="0")
  out_channels = Column(Integer, nullable=False, server_default="0")
  batchsize = Column(Integer, nullable=False, server_default="0")
  pad_h = Column(Integer, nullable=False, server_default="0")
  pad_w = Column(Integer, nullable=False, server_default="0")
  conv_stride_h = Column(Integer, nullable=False, server_default="0")
  conv_stride_w = Column(Integer, nullable=False, server_default="0")
  dilation_h = Column(Integer, nullable=False, server_default="0")
  dilation_w = Column(Integer, nullable=False, server_default="0")
  group_size = Column(Integer, nullable=False, server_default="0")
  kernel_repeats = Column(Integer, nullable=False, server_default="0")

  def __repr__(self) -> str:
    return f"ConvolutionConfig {self.to_dict()}"

  # This dict maps field names, which are also the long option names, to
  # the short forms used in the configs.  Necessary to turn a
  # ConvolutionConfig back into a string that we can pass to the runner.
  options = {
      'direction': '-F',
      'fil_layout': '-f',
      'in_layout': '-I',
      'out_layout': '-O',
      'batchsize': '-n',
      'in_channels': '-c',
      'in_h': '-H',
      'in_w': '-W',
      'out_channels': '-k',
      'fil_h': '-y',
      'fil_w': '-x',
      'pad_h': '-p',
      'pad_w': '-q',
      'conv_stride_h': '-u',
      'conv_stride_w': '-v',
      'dilation_h': '-l',
      'dilation_w': '-j',
      'group_size': '-g',
      'data_type': '-t',
      # getopt in ConvConfiguration.fromCommandLine only does single-char options.
      # Count on tuneMLIRKernels to set config.MLIR_N_REPEATS to 1.
      #    'kernel_repeats': '--kernel-repeats',
      'kernel_repeats': None,
      'id': None,
      'valid': None
  }

  def config_string(self):
    """Return config as a flag/value string suitable for tuningRunner.py."""
    string = "conv "  # +++pf:  of course generalise for gemm
    for field, value in self.to_dict().items():
      flag = self.options[field]
      if flag:
        string += f"{flag} {value} "
    string += "-m conv"
    return string


class ConvolutionResults(BASE):  # pylint: disable=too-many-instance-attributes
  """Collects the results of convolution tuning.
  """
  __tablename__ = "rocmlir_conv_results"
  __table_args__ = (UniqueConstraint("config", "session", name="uq_idx"),)

  @orm.reconstructor
  def __init__(self, **kwargs):
    if 'logger' in kwargs:
      self.logger = kwargs['logger']
    else:
      self.logger = setup_logger('results')

  @declared_attr
  def session(self):
    """session column"""
    return Column(Integer, ForeignKey("session_rocmlir.id"), nullable=False)

  config = Column(Integer, ForeignKey("rocmlir_conv_config.id"), nullable=False)
  config_str = Column(Text, nullable=False)

  perf_config = Column(Text, nullable=False)
  kernel_tflops = Column(Float, nullable=False)

  def get_query(self, sess, result_obj, session_id):
    """Construct a Db query for the find object
    """
    query = sess.query(result_obj).filter(result_obj.session == session_id,
                                          result_obj.config == self.config)
    self.logger.info("result query %s-%s", session_id, self.config)
    return query

  # +++pf:  rewrite me for tuningRunner.py output!
  def parse(self, lines):
    """parse logger output line for result data """
    line = lines.splitlines()[-1]
    print(f"line being parsed is '{line}'", file=sys.stderr)
    return line.split('\t')


#pylint: disable=too-few-public-methods
class RocMLIRDBTables(DBTablesInterface):
  """Represents db tables for rocMLIR lib"""

  def __init__(self, **kwargs):
    """Constructor"""
    super().__init__(**kwargs)
    allowed_keys = set(['config_type', 'session_id'])

    self.config_type = None
    self.job_table = None
    self.session_table = SessionRocMLIR
    self.config_table = None
    self.results = None

    self.__dict__.update(
        (key, value) for key, value in kwargs.items() if key in allowed_keys)
    self.set_tables()

  def set_tables(self, sess_class=SessionRocMLIR):
    """Set appropriate tables based on requirements"""
    super().set_tables(sess_class)
    # +++pf:  branch on self.config_type when we have GEMM, too.
    self.job_table = ConvolutionJob
    self.config_table = ConvolutionConfig
    self.results = ConvolutionResults


def get_tables() -> List[BASE]:
  """Returns a list of all Example lib DB tables"""
  tables: List[BASE] = []
  with DbSession() as session:
    engine = session.bind
    connect = session.connection()
    def append_if_not_exists(table):
      # Note: this changes in sqlalchemy 1.4.
      if not inspect(engine).dialect.has_table(connect, table.__tablename__):
        tables.append(table)

    append_if_not_exists(SessionRocMLIR())
    append_if_not_exists(Machine(local_machine=True))
    append_if_not_exists(ConvolutionConfig())
    append_if_not_exists(ConvolutionJob())
    append_if_not_exists(ConvolutionResults())

  return tables
