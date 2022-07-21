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
"""Utility module for Flask functionality"""

from sqlalchemy import create_engine
from tuna.utils.logger import setup_logger
from tuna.dbBase.sql_alchemy import DbSession
from tuna.miopen_tables import ConvolutionConfig, ConvolutionConfigTags
from tuna.metadata import get_solver_ids, DIRECTION
from tuna.utils.utility import get_env_vars
from tuna.utils.db_utility import get_id_solvers
from tuna.parsing import build_driver_cmd_from_config

LOGGER = setup_logger('flask')
SOLVER_ID_MAP_C, SOLVER_ID_MAP_H = get_solver_ids()
ID_SOLVER_MAP_C, ID_SOLVER_MAP_H = get_id_solvers()
ENV_VARS = get_env_vars()
ENGINE = create_engine("mysql+pymysql://{}:{}@{}:3306/{}".format(
    ENV_VARS['user_name'], ENV_VARS['user_password'], ENV_VARS['db_hostname'],
    ENV_VARS['db_name']))

CFTable = ConvolutionConfig
CFTTable = ConvolutionConfigTags


def get_tag_data(grafana_req, data):
  """Addresses Tag to driver cmd panel query from Grafana"""
  tag_like = None
  if grafana_req[2] != '':
    tag_like = "%{}%".format(grafana_req[2])
  if '(' in grafana_req[1]:
    tags = grafana_req[1][1:-1].split('|')
  else:
    tags = grafana_req[1].split('|')

  query_tags = []
  for tag in tags:
    query_tags.append(tag.replace('\\', ''))

  non_driver_cols = [
      'id', 'insert_ts', 'update_ts', 'md5', 'valid', 'activMode', 'cmd'
  ]
  datapoints = {'title': 'Tag - Driver cmd', 'refId': 'A', 'datapoints': []}

  values = []
  with DbSession() as session:
    try:
      if query_tags != ['']:
        LOGGER.info(query_tags)
        configs = session.query(CFTable, CFTTable.tag)\
                              .filter(CFTable.id == CFTTable.config)\
                              .filter(CFTTable.tag.in_(query_tags))\
                              .filter(CFTable.fusion_mode == -1)\
                              .filter(CFTable.valid == 1).all()
        for conv_config, tag in configs:
          values.append(
              [tag,
               build_driver_cmd_from_config(conv_config, non_driver_cols)])

      if tag_like is not None:
        LOGGER.info(tag_like)
        extra_configs = session.query(CFTable, CFTTable.tag)\
                            .filter(CFTable.id == CFTTable.config)\
                            .filter(CFTTable.tag.like(tag_like))\
                            .filter(CFTable.fusion_mode == -1)\
                            .filter(CFTable.valid == 1).all()
        for conv_config, tag in extra_configs:
          values.append(
              [tag,
               build_driver_cmd_from_config(conv_config, non_driver_cols)])

    except Exception as exp:  #pylint: disable=broad-except
      LOGGER.error(exp)

  datapoints['datapoints'] = values
  LOGGER.info(values)
  data.append(datapoints)

  return True


def get_direction(filters):
  """ Return direction from filter"""
  direction = []
  if filters and '-F' in filters['cmd']:
    dirc = filters['cmd'].partition('-F ')[2][0]
    direction.append(dirc)
  else:
    direction = DIRECTION

  return direction


def get_driver_cmds(filters, grafana_req=None):
  """Return driver cmds from req"""
  driver_cmds = []
  if filters is None:
    driver_cmds = grafana_req[1].split(";")
  else:
    if ';' in filters['cmd']:
      driver_cmds = filters['cmd'].split(";")
    else:
      driver_cmds.append(filters['cmd'])

  if driver_cmds[-1] == '':
    driver_cmds.pop()
  LOGGER.info('driver_cmds: %s', driver_cmds)

  return driver_cmds
