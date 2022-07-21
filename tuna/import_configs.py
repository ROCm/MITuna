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
""" Module for tagging and importing configs """
import os
from sqlalchemy.exc import IntegrityError

from tuna.dbBase.sql_alchemy import DbSession
from tuna.parse_args import TunaArgs, setup_arg_parser
from tuna.utils.logger import setup_logger
from tuna.db_tables import connect_db, ENGINE
from tuna.tables import ConfigType
from tuna.driver_conv import DriverConvolution
from tuna.driver_bn import DriverBatchNorm
from tuna.tables import DBTables

LOGGER = setup_logger('import_configs')


def parse_args():
  """Parsing arguments"""
  parser = setup_arg_parser(
      'Import driver commands and perf db entries ',
      [TunaArgs.ARCH, TunaArgs.NUM_CU, TunaArgs.VERSION, TunaArgs.CONFIG_TYPE])
  parser.add_argument(
      '-c',
      '--command',
      type=str,
      dest='command',
      default=None,
      help='Command override: run a different command on the imported configs',
      choices=[None, 'conv', 'convfp16', 'convbfp16'])
  parser.add_argument('-b',
                      '--batches',
                      type=str,
                      dest='batches',
                      help='Batch sizes to iterate over in the given configs')
  parser.add_argument('-f',
                      '--file_name',
                      type=str,
                      dest='file_name',
                      help='File to import')
  parser.add_argument(
      '--mark_recurrent',
      dest='mark_recurrent',
      action="store_true",
      help='Indicate whether you want the configs to be marked as recurrent')
  parser.add_argument('-t',
                      '--tag',
                      type=str,
                      required=True,
                      dest='tag',
                      help='Tag to mark the origin of this \
                      config, if config not present it will insert. No wildcard columns for \
                      tagging.')
  parser.add_argument(
      '-T',
      '--tag_only',
      action='store_true',
      dest='tag_only',
      help=
      'Tag to mark the origin of this config but skips the insert new config \
                      step in case the config does not exist in the table. Wildcard columns \
                      allowed for tagging')

  args = parser.parse_args()
  if args.batches is not None:
    args.batch_list = [int(x) for x in args.batches.split(',')]
  else:
    args.batch_list = []
  return args


def create_query(tag, mark_recurrent, config_id):
  """Helper function to build query to add tag"""
  query_dict = {}
  if tag is None and mark_recurrent:
    query_dict = {"config": config_id, "recurrent": 1}
  elif tag is not None and not mark_recurrent:
    query_dict = {"config": config_id, "tag": tag}
  else:
    query_dict = {"config": config_id, "tag": tag, "recurrent": 1}
  return query_dict


def tag_config_v2(driver, counts, dbt, args, new_cf=None):
  """Adds tag for a config formatted from the fds structure.
        If mark_recurrent is ussed then it also marks it as such.
        Updates counter for tagged configs"""
  c_id = None
  if new_cf is None:
    c_id = driver.get_db_obj(keep_id=True)
  else:
    c_id = new_cf.id

  with DbSession() as session:
    try:
      query_dict = create_query(args.tag, args.mark_recurrent, c_id)
      session.merge(dbt.config_tags_table(**query_dict))
      session.commit()
      counts['cnt_tagged_configs'].add(c_id)
    except IntegrityError as err:
      #if config/tag already exist we update recurrent=1 if required
      session.rollback()
      if "recurrent" in query_dict.keys():
        query_dict.pop("recurrent")
        #session doesnt support ON DUPLICATE KEY UPDATE, so we have to use the engine to execute
        with ENGINE.connect() as conn:
          conn.execute(dbt.config_tags_table.__table__.update().where(
              (dbt.config_tags_table.config == query_dict["config"]) &
              (dbt.config_tags_table.tag == query_dict["tag"])).values(
                  recurrent="1"))
      if "Duplicate" in str(err):
        LOGGER.warning("Config/tag already present in %s\n",
                       dbt.config_tags_table.__tablename__)
      else:
        LOGGER.error('Err occurred: %s', str(err))

  return True


def insert_config(driver, counts, dbt, args):
  """Inserts new config in the DB computed from the fds structure.
        Tags the newly inserted config. It config already exists,
        it will only tag it and log a warning for duplication."""
  new_cf = driver.get_db_obj(keep_id=True)

  with DbSession() as session:
    if new_cf.id is None:
      try:
        session.add(new_cf)
        session.commit()
        counts['cnt_configs'] += 1
      except IntegrityError as err:
        LOGGER.warning("Err occurred: %s", err)
    else:
      try:
        if args.mark_recurrent or args.tag:
          new_cf_tag = dbt.config_tags_table(tag=args.tag,
                                             recurrent=args.mark_recurrent,
                                             config=new_cf.id)
          session.add(new_cf_tag)
          session.commit()
          counts['cnt_tagged_configs'].add(new_cf.id)
      except IntegrityError as err:
        LOGGER.warning("Err occurred: %s", err)
    if args.mark_recurrent or args.tag:
      _ = tag_config_v2(driver, counts, dbt, args, new_cf)

  return True


def process_config_line_v2(driver, args, counts, dbt):
  """Assumes config passed already exists and will skip the insert step
        if tag_only present. Otherwise it will first try and insert and
        then tag."""
  if args.tag_only:
    _ = tag_config_v2(driver, counts, dbt, args, new_cf=None)
    return False

  _ = insert_config(driver, counts, dbt, args)
  return True


def parse_line(args, line, counts, dbt):
  """parse a driver line or fdb line from an input file and insert the config"""
  if args.config_type == ConfigType.batch_norm:
    driver = DriverBatchNorm(line, args.command)
  else:
    driver = DriverConvolution(line, args.command)

  if not args.batch_list:
    process_config_line_v2(driver, args, counts, dbt)
  else:
    for bsz in args.batch_list:
      LOGGER.info('Batchsize: %s', bsz)
      driver.batchsize = bsz
      process_config_line_v2(driver, args, counts, dbt)

  return True


def import_cfgs(args, dbt):
  """import configs to mysql from file with driver invocations"""
  connect_db()

  counts = {}
  counts['cnt_configs'] = 0
  counts['cnt_tagged_configs'] = set()
  infile = open(os.path.expanduser(args.file_name), "r")
  for line in infile:
    try:
      parse_line(args, line, counts, dbt)
    except ValueError as err:
      LOGGER.warning(err)
      continue

  return counts


def main():
  """Main function"""
  args = parse_args()
  counts = {}

  dbt = DBTables(session_id=None, config_type=args.config_type)

  counts = import_cfgs(args, dbt)

  LOGGER.info('New configs added: %u', counts['cnt_configs'])
  if args.tag or args.tag_only:
    LOGGER.info('Tagged configs: %u', len(counts['cnt_tagged_configs']))


if __name__ == '__main__':
  main()
