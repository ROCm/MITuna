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
import itertools

from typing import List
from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy import Text, Enum, Float, DateTime, Boolean
from sqlalchemy import delete as sql_delete
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.sql import func as sqla_func
from sqlalchemy.inspection import inspect

from tuna.dbBase.sql_alchemy import DbSession
from tuna.dbBase.base_class import BASE
from tuna.machine import Machine
from tuna.session_mixin import SessionMixin
from tuna.utils.logger import setup_logger
from tuna.tables_interface import DBTablesInterface
from tuna.rocmlir.config_type import ConfigType

#pylint: disable=too-few-public-methods


class SessionRocMLIR(BASE, SessionMixin):
  """Session table to keep track of tuning sessions"""
  #pylint: disable=attribute-defined-outside-init
  #pylint: disable=duplicate-code

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
      'group_size': '-m conv -g',  # Hack to get "-m conv -g 1"
      # getopt in ConvConfiguration.fromCommandLine only does single-char options.
      # Count on tuneMLIRKernels to set config.MLIR_N_REPEATS to 1.
      #    'kernel_repeats': '--kernel-repeats',
      'kernel_repeats': None,
      'id': None,
      'valid': None
  }

  def config_string(self):
    """Return config as a flag/value string suitable for tuningRunner.py."""
    string = "conv"
    if self.data_type == 'f16':
      string += 'fp16'
    elif self.data_type == 'i8':
      string += 'int8'
    elif self.data_type == 'bf16':
      string += 'bfp16'
    string += " "

    # In options order for canonicalisation, kind of.
    for field, flag in self.options.items():
      value = getattr(self, field, None)
      if value is not None and flag is not None:
        string += f"{flag} {value} "
    string += "-t 1"  # Dummy "enable timing" option.
    return string

  def parse_line(self, line):
    """Parse a command-line-style conv config into a ConvolutionConfig object."""

    print(f"Parsing line {line}")

    # '-t 1' means 'enable timing' which is confused with -t for type.
    line = line.replace("-t 1", "")

    # Convert the line ("conv -n 256 -c 1024 -H 14 ...") to dict of flag and value.
    i = iter(line.split())
    operation = next(i)
    options = dict(zip(i, i))
    #  print(f"options = {options}")

    # Mapping of flag to field name.
    # -F 1 -n 2 -c 1280 -H 32 -W 32 -k 640 -y 1 -x 1 -p 0 -q 0 -u 1 -v 1 -l 1 -j 1 -m conv -g 1 -t 1
    fields = {
        '-F': 'direction',
        '-f': 'fil_layout',
        '-I': 'in_layout',
        '-O': 'out_layout',
        '-n': 'batchsize',
        '-c': 'in_channels',
        '-H': 'in_h',
        '-W': 'in_w',
        '-k': 'out_channels',
        '-y': 'fil_h',
        '-x': 'fil_w',
        '-p': 'pad_h',
        '-q': 'pad_w',
        '-u': 'conv_stride_h',
        '-v': 'conv_stride_w',
        '-l': 'dilation_h',
        '-j': 'dilation_w',
        '-g': 'group_size',
        '-m': None
    }
    # kernel-repeats has no flag, but perfRunner.py uses 5.
    # ConvConfiguration.fromCommandLine accepts but skips -m and -t.
    #   -m is operation and -t is (I think) -time from MIOpenDriver.
    # data_type is inferred from operation -- conv is f32, convfp16 is f16,
    #   convbfp16 is bf16, convint8 is i8

    self.data_type = 'f32'
    if operation == 'convfp16':
      self.data_type = 'f16'
    elif operation == 'convint8':
      self.data_type = 'i8'
    elif operation == 'convbfp16':
      self.data_type = 'bf16'
    self.kernel_repeats = 1
    for flag, value in options.items():
      field = fields[flag]
      if field:
        setattr(self, field, value)

  ## Adapted from perfRunner.getConvConfigurations.

  #DIRECTIONS = ['-F 1', '-F 2', '-F 4']
  # temporarily disable backward-data until rocmlir-tuning-driver can handle multi-kernel code
  DIRECTIONS = ['-F 1', '-F 4']
  DATA_TYPES = ['conv', 'convfp16', 'convint8']
  LAYOUTS = ['NHWC', 'NCHW']

  def get_configurations(self, filename):
    """Read conv-configs from filename and expand into all combinations of
         direction, type, and layout.
      """

    configs = []
    with open(filename, 'r', encoding='utf8') as config_file:
      lines = config_file.readlines()

      # All combinations of conv direction, type and layouts
      for direction, datatype, layout, line in \
              itertools.product(self.DIRECTIONS, self.DATA_TYPES, self.LAYOUTS,
                                lines):
        line = line.strip()

        # Skip empty lines
        if len(line) == 0 or line[0] == '#':
          continue
        # Skip int8 non-fwd convolutions
        if datatype == 'convint8' and direction != '-F 1':
          continue

        # Skip datatype if already in
        datatype = f"{datatype} "
        # check for the presense of a positional arg
        if line[0][0] != "-":
          datatype = ""

        # Skip direction if already in
        direction = f"{direction} "
        if "-F" in line:
          direction = ""

        # Skip filter layout if already in
        filter_layout = f"-f {layout} "
        if "-f" in line:
          filter_layout = ""

        # Skip input layout if already in
        input_layout = f"-I {layout} "
        if "-I" in line:
          input_layout = ""

        # Skip output layout if already in
        output_layout = f"-O {layout} "
        if "-O" in line:
          output_layout = ""

        one_config = f"{datatype}{direction}{filter_layout}\
                       {input_layout}{output_layout}{line}"

        if one_config not in configs:
          configs.append(one_config)

    return configs


class ResultsMixin():  # pylint: disable=too-many-instance-attributes
  """Collects the results of tuning."""

  def __init__(self, **kwargs):
    if 'logger' in kwargs:
      self.logger = kwargs['logger']
    else:
      self.logger = setup_logger('results')

  @declared_attr
  def session(self):
    """session column"""
    return Column(Integer, ForeignKey("session_rocmlir.id"), nullable=False)

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

  def parse(self, lines):
    """parse logger output line for result data """
    line = lines.splitlines()[-1]
    print(f"line being parsed is '{line}'", file=sys.stderr)
    return line.split('\t')

  def export_as_tsv(self, filename, dbt, append=False):
    """Write the contents of the table as a .tsv file for perfRunner.py."""
    arch = dbt.session.arch
    num_cu = dbt.session.num_cu
    session_id = dbt.session_id

    with open(filename, 'a' if append else 'w', encoding='utf8') as out:
      print("# arch\tnumCUs\ttestVector\tperfConfig (tuna)", file=out)
      with DbSession() as sess:
        tbl = dbt.results
        query = sess.query(tbl).filter(tbl.session == session_id,
                                       tbl.valid == 1)
        res = query.all()
        for row in res:
          # For detailed compatibility, downcase False and True.
          config_str = row.config_str.replace("False",
                                              "false").replace("True", "true")
          print(f"Arch = {arch}({num_cu} CUs), vector = '{config_str}', \
                perfConfig = {row.perf_config}",
                file=sys.stderr)
          print(f"{arch}\t{num_cu}\t{config_str}\t{row.perf_config}", file=out)
        return len(res)


class ConvolutionResults(BASE, ResultsMixin):  # pylint: disable=too-many-instance-attributes
  """Collects the results of convolution tuning."""

  __tablename__ = "rocmlir_conv_results"
  __table_args__ = (UniqueConstraint("config", "session", name="uq_idx"),)

  config = Column(Integer,
                  ForeignKey("rocmlir_conv_config.id"),
                  nullable=False,
                  index=True)


class GEMMJob(BASE, JobMixin):
  """Represents gemm job table"""
  __tablename__ = "rocmlir_gemm_job"
  __table_args__ = (UniqueConstraint('config', 'session', name="uq_idx"),)

  config = Column(Integer,
                  ForeignKey("rocmlir_gemm_config.id"),
                  nullable=False,
                  index=True)


class GEMMConfig(BASE):
  """Represents GEMM config table"""
  __tablename__ = "rocmlir_gemm_config"

  data_type = Column(String(length=60), nullable=False, server_default="")
  out_data_type = Column(String(length=60), nullable=False, server_default="")
  group_size = Column(Integer, nullable=False, server_default="0")
  m = Column(Integer, nullable=False, server_default="0")
  n = Column(Integer, nullable=False, server_default="0")
  k = Column(Integer, nullable=False, server_default="0")
  transpose_A = Column(Boolean, nullable=False, server_default="0")
  transpose_B = Column(Boolean, nullable=False, server_default="0")
  kernel_repeats = Column(Integer, nullable=False, server_default="0")

  def __repr__(self) -> str:
    return f"GEMMConfig {self.to_dict()}"

  # This dict maps field names, which are also the long option names, to
  # the short forms used in the configs.  Necessary to turn a
  # GEMMConfig back into a string that we can pass to the runner.
  options = {
      'data_type': '-t',
      'out_data_type': '-out_datatype',
      'transpose_A': '-transA',
      'transpose_B': '-transB',
      'group_size': '-g',
      'm': '-m',
      'n': '-n',
      'k': '-k',
      # Count on tuneMLIRKernels to set config.MLIR_N_REPEATS to 1.
      #    'kernel_repeats': '--kernel-repeats',
      'kernel_repeats': None,
      'id': None,
      'valid': None
  }

  def config_string(self):
    """Return config as a flag/value string suitable for tuningRunner.py."""
    string = ""
    #     for field, value in self.to_dict().items():
    #       flag = self.options[field]
    #       if flag:
    #         string += f"{flag} {value} "
    # In options order for canonicalisation, kind of.
    for field, flag in self.options.items():
      value = getattr(self, field, None)
      if value is not None and flag is not None:
        string += f"{flag} {value} "
    return string.strip()

  def parse_line(self, line):
    """Parse a command-line-style gemm config into a GEMMConfig object."""

    print(f"Parsing line {line}")

    # Convert the line ("-n 256 -c 1024 -H 14 ...") to dict of flag and value.
    i = iter(line.split())
    options = dict(zip(i, i))
    #  print(f"options = {options}")

    # Mapping of flag to field name.
    # -transA false -transB false -g 64 -m 1024 -n 384 -k 1024
    fields = {
        '-transA': 'transpose_A',
        '-transB': 'transpose_B',
        '-g': 'group_size',
        '-m': 'm',
        '-n': 'n',
        '-k': 'k',
        '-t': 'data_type',
        '-out_datatype': 'out_data_type'
    }
    # kernel-repeats has no flag, but perfRunner.py uses 5.

    self.kernel_repeats = 1
    for flag, value in options.items():
      if value == "true":
        value = 1
      if value == "false":
        value = 0
      field = fields[flag]
      if field:
        setattr(self, field, value)

  ## Adapted from perfRunner.getGemmConfigurations.

  DATA_TYPES = ['f32', 'f16', 'i8']

  def get_configurations(self, filename):
    #pylint: disable=invalid-name
    """Read gemm-configs from filename and expand into all combinations of
         type and transpose.
      """

    configs = []
    with open(filename, 'r', encoding='utf8') as config_file:
      lines = config_file.readlines()

      # All combinations of types and transposition (A and B)
      for datatype, transA, transB, line in \
              itertools.product(self.DATA_TYPES, ['false', 'true'],
                                ['false', 'true'], lines):
        line = line.strip()

        # Skip empty lines
        if len(line) == 0 or line[0] == '#':
          continue

        # We need trailing spaces here to account for the concat below
        # Skip type if already in
        dataTypeString = ""
        if "-t " not in line:
          dataTypeString = f"-t {datatype} "

        # Skip transA if already in
        transAString = ""
        if "-transA " not in line:
          transAString = f"-transA {transA} "

        # Skip transB if already in
        transBString = ""
        if "-transB " not in line:
          transBString = f"-transB {transB} "

        # Skip out_datatype if already in
        outDataTypeString = ""
        if "-out_datatype" not in line:
          outDataTypeString = f"-out_datatype {datatype} "

        # Strip to avoid spurious spaces
        oneConfig = f"{dataTypeString}{outDataTypeString}\
                      {transAString}{transBString}{line}".strip()
        if oneConfig not in configs:
          configs.append(oneConfig)

        # Special case to get both i8_i8 and i8_i32, w/o --data-type or output-type-map.
        if "-out_datatype" not in line and datatype == 'i8':
          outDataTypeString = "-out_datatype i32 "
          oneConfig = f"{dataTypeString}{outDataTypeString}\
                        {transAString}{transBString}{line}".strip()
          if oneConfig not in configs:
            configs.append(oneConfig)

    return configs


class GEMMResults(BASE, ResultsMixin):  # pylint: disable=too-many-instance-attributes
  """Collects the results of GEMM tuning."""

  __tablename__ = "rocmlir_gemm_results"
  __table_args__ = (UniqueConstraint("config", "session", name="uq_idx"),)

  config = Column(Integer,
                  ForeignKey("rocmlir_gemm_config.id"),
                  nullable=False,
                  index=True)


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
    if self.config_type == ConfigType.CONVOLUTION:
      self.job_table = ConvolutionJob
      self.config_table = ConvolutionConfig
      self.results = ConvolutionResults
    elif self.config_type == ConfigType.GEMM:
      self.job_table = GEMMJob
      self.config_table = GEMMConfig
      self.results = GEMMResults
    else:
      raise ValueError(f"Config type {self.config_type} not yet supported.")


def get_tables() -> List[BASE]:
  """Returns a list of all RocMLIR lib DB tables"""
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
    append_if_not_exists(GEMMConfig())
    append_if_not_exists(GEMMJob())
    append_if_not_exists(GEMMResults())

  return tables


def clear_tables(config_type):
  """Get a clean state in the database."""
  dbt = RocMLIRDBTables(session_id=None, config_type=config_type)
  with DbSession() as session:
    session.execute(sql_delete(dbt.results))
    session.execute(sql_delete(dbt.job_table))
    session.execute(sql_delete(dbt.config_table))
    session.execute(sql_delete(dbt.session_table))
