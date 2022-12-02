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
""" Module adding frameworks/models/benchmarks"""
import os
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound

from tuna.dbBase.sql_alchemy import DbSession
from tuna.parse_args import TunaArgs, setup_arg_parser
from tuna.utils.logger import setup_logger
from tuna.miopen.benchmark import Framework, Model, FrameworkEnum, ModelEnum
from tuna.miopen.tables import MIOpenDBTables
from tuna.config_type import ConfigType
from tuna.driver_conv import DriverConvolution
from tuna.driver_bn import DriverBatchNorm

LOGGER = setup_logger('import_benchmarks')


def parse_args():
  """Parsing arguments"""
  parser = setup_arg_parser('Import benchmark performance related items',
                            [TunaArgs.CONFIG_TYPE])
  group1 = parser.add_mutually_exclusive_group()
  group2 = parser.add_mutually_exclusive_group()
  group3 = parser.add_mutually_exclusive_group()
  group1.add_argument('--update_framework',
                      action="store_true",
                      dest='update_framework',
                      help='Populate framework table with all framework enums')
  group2.add_argument('--add_model',
                      dest='add_model',
                      type=ModelEnum,
                      choices=ModelEnum,
                      help='Populate table with new model and version')
  group3.add_argument('--print_models',
                      dest='print_models',
                      action='store_true',
                      help='Print models from table')
  parser.add_argument('--add_benchmark',
                      dest='add_benchmark',
                      action='store_true',
                      help='Insert new benchmark')
  parser.add_argument('-m',
                      '--model',
                      dest='model',
                      type=ModelEnum,
                      choices=ModelEnum,
                      required=False,
                      help='Specify model')
  parser.add_argument('-F',
                      '--framework',
                      dest='framework',
                      type=FrameworkEnum,
                      choices=FrameworkEnum,
                      help='Specify framework.')
  parser.add_argument('-d',
                      '--driver',
                      dest='driver',
                      type=str,
                      default=None,
                      required=False,
                      help='Specify driver cmd')
  parser.add_argument('-g',
                      '--gpu_count',
                      dest='gpu_count',
                      type=int,
                      default=None,
                      required=False,
                      help='Specify number of gpus the benchmark runs on')
  parser.add_argument('-f',
                      '--file_name',
                      type=str,
                      dest='file_name',
                      help='File to specify multiple Driver commands')
  parser.add_argument('--md_version',
                      dest='md_version',
                      type=str,
                      default=None,
                      required=False,
                      help='Specify model version')
  parser.add_argument('--fw_version',
                      dest='fw_version',
                      type=str,
                      default=None,
                      required=False,
                      help='Specify model version')
  parser.add_argument('--batchsize',
                      dest='batchsize',
                      type=int,
                      default=None,
                      required=False,
                      help='Specify model batchsize')

  args = parser.parse_args()
  if args.add_model and not args.md_version:
    parser.error('Version needs to be specified with model')
  if args.add_benchmark and not (args.model and args.framework and
                                 args.gpu_count and args.batchsize and
                                 args.md_version and args.fw_version and
                                 (args.driver or args.file_name)):
    parser.error(
        """Model, md_version, framework, fw_version, driver(or filename), batchsize \n
         and gpus need to all be specified to add a new benchmark""")
  return args


def print_models():
  """Display models from the db table"""
  with DbSession() as session:
    models = session.query(Model).all()
    for model in models:
      LOGGER.info('model %s version %s ', model.model, model.version)
  return True


def add_model(args):
  """Add new model and version to the db table"""
  with DbSession() as session:
    new_model = Model(model=args.add_model, version=args.md_version)
    try:
      session.add(new_model)
      session.commit()
      LOGGER.info('Added model %s with version %s ', args.add_model,
                  str(args.md_version))
    except IntegrityError as err:
      LOGGER.error(err)
      return False

  return True


def update_frameworks():
  """Bring DB table up to speed with enums defined in FrameworkEnum"""
  with DbSession() as session:
    for elem in FrameworkEnum:
      try:
        new_fmk = Framework(framework=elem)
        session.add(new_fmk)
        session.commit()
        LOGGER.info('Added new framework %s', elem)
      except IntegrityError as ierr:
        LOGGER.warning(ierr)
        session.rollback()
        continue

  return True


def get_database_id(framework, model, md_version, fw_version, dbt):
  """Get DB id of item"""

  mid = None
  fid = None
  with DbSession() as session:
    try:
      res = session.query(
          dbt.framework.id).filter(dbt.framework.framework == framework)\
                           .filter(dbt.framework.version == fw_version).one()
      fid = res.id
    except NoResultFound as dberr:
      LOGGER.error(dberr)
      LOGGER.error(
          'Framework not present in the DB. Please run --update_framework to populate the DB table'
      )
    try:
      res = session.query(dbt.model.id).filter(dbt.model.model == model)\
                                       .filter(dbt.model.version == md_version).one()
      mid = res.id
    except NoResultFound as dberr:
      LOGGER.error(
          'Model not present in the DB. Please run --add_mode to populate the DB table'
      )
      LOGGER.error(dberr)
  return mid, fid


def add_benchmark(args, dbt):
  """Add new benchmark"""
  mid, fid = get_database_id(args.framework, args.model, args.md_version, args.fw_version, dbt)
  print(mid, fid)
  if mid is None:
    LOGGER.error('Could not find DB entry for model:%s, version:%s', args.model, args.md_version)
    return False
  if fid is None:
    LOGGER.error('Could not find DB entry for framework:%s, version:%s', args.framework, args.fw_version)
    return False
  commands = []
  if args.driver:
    commands.append(args.driver)
  else:
    with open(os.path.expanduser(args.file_name), "r") as infile:  # pylint: disable=unspecified-encoding
      for line in infile:
        commands.append(line)

  count=0

  with DbSession() as session:
    for cmd in commands:
      try:
        if args.config_type == ConfigType.convolution:
          driver = DriverConvolution(line=cmd)
        else:
          driver = DriverBatchNorm(line=cmd)
        db_obj = driver.get_db_obj(keep_id=True)
        if db_obj.id is None:
          LOGGER.error('Config not present in the DB: %s', str(driver))
          LOGGER.error('Please use import_configs.py to import configs')

        benchmark = dbt.benchmark()
        benchmark.framework = fid
        benchmark.model = mid
        benchmark.config = db_obj.id
        benchmark.gpu_number = args.gpu_count
        benchmark.driver_cmd = str(driver)
        benchmark.batchsize = args.batchsize
        session.add(benchmark)
        session.commit()
        count+=1
      except (ValueError, IntegrityError) as verr:
        LOGGER.warning(verr)
        session.rollback()
        continue
  LOGGER.info('Tagged %s configs', count)
  return True


def main():
  """Main function"""
  args = parse_args()
  dbt = MIOpenDBTables(session_id=None, config_type=args.config_type)
  if args.print_models:
    print_models()
  if args.add_model:
    add_model(args)
  if args.update_framework:
    update_frameworks()
  if args.add_benchmark:
    add_benchmark(args, dbt)


if __name__ == '__main__':
  main()
