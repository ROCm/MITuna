#!/usr/bin/env python3
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
"""! @brief YAML parser to support multiple tuning steps """

import os
import tempfile
import yaml
from tuna.libraries import Library
from tuna.parse_args import TunaArgs
from tuna.miopen.metadata import MIOPEN_TUNING_STEPS, MIOPEN_SINGLE_OP
from tuna.example.metadata import EXAMPLE_TUNING_STEPS, EXAMPLE_SINGLE_OP


def parse_yaml(filename, lib):
  """Parses input yaml file and returns 1 or multiple yaml files(when library support
     for multiple yaml files is provided).
     Multiple yaml files are returned when more that 1 step per initial yaml file
     are specified."""
  yaml_dict = None
  yaml_files = []
  with open(os.path.expanduser(filename), encoding="utf8") as stream:
    try:
      yaml_dict = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
      print(exc)

  #if Library not specified here, no custom parsing function will be used
  if lib == Library.MIOPEN or lib.value == 'miopen':
    yaml_files = get_yaml_files(yaml_dict, MIOPEN_TUNING_STEPS,
                                MIOPEN_SINGLE_OP)
  elif lib == Library.EXAMPLE or lib.value == 'example':
    yaml_files = get_yaml_files(yaml_dict, EXAMPLE_TUNING_STEPS,
                                EXAMPLE_SINGLE_OP)
  else:
    #return current yaml file without custom parsing
    return filename

  return yaml_files


def get_common_yaml(yaml_dict):
  """Set TunaArgs common yaml fields"""
  common_args = [enum.value for enum in TunaArgs]
  common_yaml_part = {}

  #extract common TunaArgs
  for key in yaml_dict:
    if key in common_args:
      common_yaml_part[key] = yaml_dict[key]

  return common_yaml_part


def dump_yaml(new_yaml):
  """Dump yaml file to /tmp"""
  _, local_file = tempfile.mkstemp()
  with open(local_file, 'w', encoding="utf8") as outfile:
    yaml.dump(new_yaml, outfile, default_flow_style=False)

  return local_file


def get_yaml_files(original_yaml_dict, tuning_steps, single_op):
  """Split initial YAML file to multiple files and return list of files"""
  yaml_files = []
  yaml_dict = original_yaml_dict.copy()
  common_yaml_part = get_common_yaml(yaml_dict)

  for key in yaml_dict:
    #only look at enabled items
    if key in tuning_steps and yaml_dict.get(key).get('enabled'):
      #append common args
      new_yaml = common_yaml_part.copy()
      yaml_dict[key].pop('enabled', None)

      #append nested dicts
      for key2, value2 in yaml_dict.get(key).items():
        new_yaml[key2] = value2

      if key in single_op:
        new_yaml[key] = True
      yaml_files.append(dump_yaml(new_yaml))

  return yaml_files
