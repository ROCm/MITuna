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
"""! @brief YAML library specific input parsing for tuning steps"""

import tempfile
import yaml
from tuna.parse_args import TunaArgs

MIOPEN_TUNING_STEPS = [
    'init_session', 'add_tables', 'import_configs', 'load_job',
    'update_applicability', 'update_solvers', 'list_solvers', 'fin_steps'
    'export_db', 'import_db', 'check_status', 'execute_cmd'
]


def parse_miopen_yaml(yaml_dict):
  yaml_files = []
  common_args = [enum.value for enum in TunaArgs]
  common_yaml_part = {}
  #print('common args: {}'.format(common_args))

  #extract common TunaArgs
  for key in yaml_dict:
    if key in common_args:
      common_yaml_part[key] = yaml_dict[key]
  #print('common_yaml_part: {}'.format(common_yaml_part))

  for key in yaml_dict:
    if key in MIOPEN_TUNING_STEPS:
      new_yaml = common_yaml_part.copy()
      new_yaml[key] = yaml_dict[key]
      _, local_file = tempfile.mkstemp()
      with open(local_file, 'w') as outfile:
        yaml.dump(new_yaml, outfile, default_flow_style=False)
      yaml_files.append(local_file)

  print('YAML files: {}'.format(yaml_files))

  return yaml_files
