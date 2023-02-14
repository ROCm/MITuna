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
from tuna.miopen.benchmark import Framework, Model, FrameworkEnum
from tuna.miopen.tables import MIOpenDBTables
from tuna.config_type import ConfigType
from tuna.driver_conv import DriverConvolution
from tuna.driver_bn import DriverBatchNorm
from tuna.miopen.parse_miopen_args import get_import_benchmark_parser
from tuna.utils.logger import setup_logger


def print_models(logger):
  """Display models from the db table"""
  with DbSession() as session:
    models = session.query(Model).all()
    for model in models:
      logger.info('model %s version %s ', model.model, model.version)
  return True


def add_model(args, logger):
  """Add new model and version to the db table"""
  with DbSession() as session:
    new_model = Model(model=args.add_model, version=args.md_version)
    try:
      session.add(new_model)
      session.commit()
      logger.info('Added model %s with version %s ', args.add_model,
                  str(args.md_version))
    except IntegrityError as err:
      logger.error(err)
      return False

  return True


def update_frameworks(logger):
  """Bring DB table up to speed with enums defined in FrameworkEnum"""
  with DbSession() as session:
    for elem in FrameworkEnum:
      try:
        new_fmk = Framework(framework=elem)
        session.add(new_fmk)
        session.commit()
        logger.info('Added new framework %s', elem)
      except IntegrityError as ierr:
        logger.warning(ierr)
        session.rollback()
        continue

  return True


def get_database_id(framework, fw_version, model, md_version, dbt, logger):
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
      logger.error(dberr)
      logger.error(
          'Framework not present in the DB. Please run --update_framework to populate the DB table'
      )
    try:
      res = session.query(dbt.model.id).filter(dbt.model.model == model)\
                                       .filter(dbt.model.version == md_version).one()
      mid = res.id
    except NoResultFound as dberr:
      logger.error(
          'Model not present in the DB. Please run --add_mode to populate the DB table'
      )
      logger.error(dberr)
  return mid, fid


def add_benchmark(args, dbt, logger):
  """Add new benchmark"""
  mid, fid = get_database_id(args.framework, args.fw_version, args.model,
                             args.md_version, dbt, logger)
  print(mid, fid)
  if mid is None:
    logger.error('Could not find DB entry for model:%s, version:%s', args.model,
                 args.md_version)
    return False
  if fid is None:
    logger.error('Could not find DB entry for framework:%s, version:%s',
                 args.framework, args.fw_version)
    return False
  commands = []
  if args.driver:
    commands.append(args.driver)
  else:
    with open(os.path.expanduser(args.file_name), "r") as infile:  # pylint: disable=unspecified-encoding
      for line in infile:
        commands.append(line)

  count = 0

  with DbSession() as session:
    for cmd in commands:
      try:
        if args.config_type == ConfigType.convolution:
          driver = DriverConvolution(line=cmd)
        else:
          driver = DriverBatchNorm(line=cmd)
        db_obj = driver.get_db_obj(keep_id=True)
        if db_obj.id is None:
          logger.error('Config not present in the DB: %s', str(driver))
          logger.error('Please use import_configs.py to import configs')

        benchmark = dbt.benchmark()
        benchmark.framework = fid
        benchmark.model = mid
        benchmark.config = db_obj.id
        benchmark.gpu_number = args.gpu_count
        benchmark.driver_cmd = str(driver)
        benchmark.batchsize = args.batchsize
        session.add(benchmark)
        session.commit()
        count += 1
      except (ValueError, IntegrityError) as verr:
        logger.warning(verr)
        session.rollback()
        continue
  logger.info('Tagged %s configs', count)
  return True


def check_import_benchmark_args(args):
  """Checking args for import_benchmark subcommand"""
  if args.add_model and not args.md_version:
    raise ValueError('Version needs to be specified with model')
  if args.add_benchmark and not (args.model and args.framework and
                                 args.gpu_count and args.batchsize and
                                 args.md_version and args.fw_version and
                                 (args.driver or args.file_name)):
    raise ValueError(
        """Model, md_version, framework, fw_version, driver(or filename), batchsize \n
         and gpus need to all be specified to add a new benchmark""")


def run_import_benchmark(args, logger):
  """Main function"""
  dbt = MIOpenDBTables(session_id=None, config_type=args.config_type)
  if args.print_models:
    print_models(logger)
  if args.add_model:
    add_model(args, logger)
  if args.update_framework:
    update_frameworks(logger)
  if args.add_benchmark:
    add_benchmark(args, dbt, logger)


def main():
  """ main """
  parser = get_import_benchmark_parser(with_yaml=False)
  args = parser.parse_args()
  run_import_benchmark(args, setup_logger('import_benchmark'))


if __name__ == '__main__':
  main()
