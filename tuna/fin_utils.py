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
"""Utility functions to support fin commands
"""

from tuna.metadata import NCHW_LAYOUT, NHWC_LAYOUT, NCDHW_LAYOUT, NDHWC_LAYOUT
from tuna.metadata import PREC_TO_CMD, INVERS_DIR_MAP
from tuna.utils.logger import setup_logger
from tuna.utils.utility import arch2targetid
from tuna.config_type import ConfigType

LOGGER = setup_logger('fin_utils')


def fin_job(steps, dynamic_only, job, config, dbt):
  """Construct a fin job dict from a config and a job
  """
  return_dict = {
      "steps": steps,
      "arch": arch2targetid(dbt.session.arch),
      "num_cu": dbt.session.num_cu,
      "config_tuna_id": config.id,
      "direction": int(INVERS_DIR_MAP[config.direction]),
      "dynamic_only": dynamic_only,
      "config": compose_config_obj(config)
  }
  if job.solver:
    return_dict["solvers"] = [job.solver]

  return return_dict


def compose_config_obj(config, config_type=ConfigType.convolution):
  """Helper function to compose non-conv config obj"""
  return_config = {}
  input_t_dict = None
  in_layout = None
  weight_t_dict = None
  wei_layout = None

  if 'input_t' in config.__dict__.keys():
    input_t_dict = {'input_t': config.input_t.to_dict()}
    cmd = PREC_TO_CMD[config_type][input_t_dict['input_t']['data_type']]
    in_layout = input_t_dict['input_t']['layout']
  if 'weight_t' in config.__dict__.keys():
    weight_t_dict = {'weight_t': config.weight_t.to_dict()}
    cmd = PREC_TO_CMD[config_type][weight_t_dict['weight_t']['data_type']]
    wei_layout = weight_t_dict['weight_t']['layout']

  return_config = config.to_dict()
  if in_layout and wei_layout:
    if in_layout != wei_layout != return_config['out_layout']:
      LOGGER.error('Layouts must match. in_layout = %s, wei_layout=%s',
                   in_layout, wei_layout)
      return None
  if in_layout:
    return_config.pop('input_t')
  if wei_layout:
    return_config.pop('weight_t')

  if input_t_dict:
    return_config.update(get_tensor('in_layout', input_t_dict['input_t']))
  if weight_t_dict:
    return_config.update(get_tensor('wei_layout', weight_t_dict['weight_t']))

  #For now this hold, but might change in the future
  return_config['cmd'] = cmd

  return return_config


def get_tensor(tensor_type, tensor_dict):
  """Converts tensor dict to MIOpenDriver input"""
  ret_dict = {}
  layout = {}
  if tensor_dict['layout'] == 'NCHW':
    layout = NCHW_LAYOUT[tensor_type]
  elif tensor_dict['layout'] == 'NHWC':
    layout = NHWC_LAYOUT[tensor_type]
  elif tensor_dict['layout'] == 'NCDHW':
    layout = NCDHW_LAYOUT[tensor_type]
  elif tensor_dict['layout'] == 'NDHWC':
    layout = NDHWC_LAYOUT[tensor_type]
  else:
    LOGGER.error('unsupported layout: %s', tensor_dict['layout'])
  for key, value in tensor_dict.items():
    if key in layout.keys():
      ret_dict[layout[key]] = value
    ret_dict[tensor_type] = tensor_dict['layout']

  return ret_dict
