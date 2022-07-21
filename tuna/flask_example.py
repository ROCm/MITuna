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
from tuna.utils.utility import get_env_vars
from tuna.grafana_dict import EXAMPLE_TABLE
from tuna.find_db import ConvolutionFindDB

LOGGER = setup_logger('flask')
ENV_VARS = get_env_vars()
ENGINE = create_engine("mysql+pymysql://{}:{}@{}:3306/{}".format(
    ENV_VARS['user_name'], ENV_VARS['user_password'], ENV_VARS['db_hostname'],
    ENV_VARS['db_name']))


def get_table_example(grafana_req, data):
  """example on how to populate a table for a Grafana dashboard"""

  LOGGER.info('Request: %s', grafana_req)
  #Populate the table with dummy data
  EXAMPLE_TABLE['rows'].append(['val1', 'ex1', '1', '1.05'])
  EXAMPLE_TABLE['rows'].append(['val2', 'ex2', '2', '1.06'])
  EXAMPLE_TABLE['rows'].append(['val3', 'ex3', '3', '1.06'])
  EXAMPLE_TABLE['rows'].append(['val4', 'ex4', '4', '1.08'])

  #To populate the table with data from your DB:
  with DbSession() as session:
    query = session.query(ConvolutionFindDB.rocm_v, ConvolutionFindDB.miopen_v,
                          ConvolutionFindDB.valid,
                          ConvolutionFindDB.kernel_time).limit(5).all()
    for res in query:
      EXAMPLE_TABLE['rows'].append([res[0], res[1], res[2], res[3]])

  #The data variable will contain both dummy and db data

  data.append(EXAMPLE_TABLE)
  return data
