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
from sqlalchemy.exc import IntegrityError

from tuna.dbBase.sql_alchemy import DbSession
from tuna.parse_args import TunaArgs, setup_arg_parser
from tuna.utils.logger import setup_logger
from tuna.miopen.benchmark import Framework, Model, FrameworkEnum, ModelEnum

LOGGER = setup_logger('import_benchmarks')


def parse_args():
  """Parsing arguments"""
  parser = setup_arg_parser('Import benchmark performance related items',
                            [TunaArgs.VERSION])
  parser.add_argument('--update_framework',
                      action="store_true",
                      dest='update_framework',
                      help='Populate framework table with all framework enums')
  parser.add_argument('--add_model',
                      dest='add_model',
                      type=ModelEnum,
                      choices=ModelEnum,
                      help='Populate table with new model and version')
  parser.add_argument('--print_models',
                      dest='print_models',
                      action='store_true',
                      help='Print models from table')
  parser.add_argument('--version',
                      dest='version',
                      type=str,
                      default=None,
                      required=False,
                      help='Specify model version')

  args = parser.parse_args()
  if args.add_model and not args.version:
    parser.error('Version needs to be specified with model')
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
    new_model = Model(model=args.add_model, version=args.version)
    try:
      session.add(new_model)
      session.commit()
      LOGGER.info('Added model %s with version %s ', args.add_model,
                  str(args.version))
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
        continue

  return True


def main():
  """Main function"""
  args = parse_args()
  if args.print_models:
    print_models()
  if args.add_model:
    add_model(args)
  if args.update_framework:
    update_frameworks()


if __name__ == '__main__':
  main()
