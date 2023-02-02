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

import os
import sys
import yaml
sys.path.append("../tuna")
sys.path.append("tuna")

this_path = os.path.dirname(__file__)

from tuna.yaml_parser import parse_yaml
from tuna.example.example_lib import Example
from tuna.miopen.miopen_lib import MIOpen
from tuna.libraries import Library


def test_yaml_parser():
  miopen_yaml = "{0}/../tuna/miopen/sample.yaml".format(this_path)
  example_yaml = "{0}/../tuna/example/sample.yaml".format(this_path)

  parse_miopen_yaml(miopen_yaml, Library('miopen'))
  parse_example_yaml(example_yaml, Library('example'))


def parse_miopen_yaml(miopen_yaml, miopen):
  yaml_files = parse_yaml(miopen_yaml, miopen)
  assert len(yaml_files) == 2

  yaml_dicts = []
  #reading in initial yaml file split in 2 yaml files
  for yfile in yaml_files:
    with open(yfile, encoding="utf8") as stream:
      yaml_dict = yaml.safe_load(stream)
      yaml_dicts.append(yaml_dict)

  dict1 = {
      'arch': 'gfx908',
      'config_type': 'convolution',
      'docker_name': 'my_docker_name',
      'label': 'Example',
      'num_cu': 120,
      'remote_machine': False,
      'restart_machine': False,
      'session_id': 1,
      'update_applicability': True
  }
  dict2 = {
      'all_configs': True,
      'arch': 'gfx908',
      'config_type': 'convolution',
      'docker_name': 'my_docker_name',
      'fin_steps': 'miopen_find_compile, miopen_find_eval',
      'label': 'Example',
      'num_cu': 120,
      'remote_machine': False,
      'restart_machine': False,
      'session_id': 1
  }

  assert (yaml_dicts[0] == dict1)
  assert (yaml_dicts[1] == dict2)


def parse_example_yaml(example_yaml, example):
  yaml_files = parse_yaml(example_yaml, example)
  assert len(yaml_files) == 2

  yaml_dicts = []
  #reading in initial yaml file split in 2 yaml files
  for yfile in yaml_files:
    with open(yfile, encoding="utf8") as stream:
      yaml_dict = yaml.safe_load(stream)
      yaml_dicts.append(yaml_dict)

  dict1 = {
      'arch': 'gfx908',
      'config_type': 'convolution',
      'docker_name': 'my_docker_name',
      'init_session': True,
      'label': 'Example',
      'num_cu': 120,
      'remote_machine': False,
      'restart_machine': False,
      'session_id': 1
  }
  dict2 = {
      'arch': 'gfx908',
      'config_type': 'convolution',
      'docker_name': 'my_docker_name',
      'execute': True,
      'label': 'Example',
      'num_cu': 120,
      'remote_machine': False,
      'restart_machine': False,
      'session_id': 1
  }

  assert (yaml_dicts[0] == dict1)
  assert (yaml_dicts[1] == dict2)
