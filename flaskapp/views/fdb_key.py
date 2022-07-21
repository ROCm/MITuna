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
"""Module to take in MIOpenDriver cmd and return fdb keys in json format"""
from flask import request, render_template
from flask import Blueprint, jsonify
from tuna.query_db import main_impl
from tuna.parsing import parse_driver_line
from tuna.import_configs import config_set_defaults, tag_config_v1

fdb_key = Blueprint('fdb_key', __name__, template_folder='templates')


@fdb_key.route('/fdb_key')
def get_fdb_keys():
  """Takes MIOpenDriver cmd"""
  return render_template('input-form.html')


#parse JSON object from Grafana
@fdb_key.route('/fdb_key', methods=['POST'])
def post_fdb_keys():
  """POST that takes MIOpenDriver cmd and returns json"""
  cmd = None
  if 'cmd' in request.form:
    cmd = request.form['cmd']
  elif request.is_json:
    json_dict = request.get_json(force=True)
    cmd = json_dict['cmd']
  else:
    raise ValueError('Unsuported operation.')

  return_dict = {}
  return_dict['cmd'] = cmd
  fds, precision = get_fds_from_cmd(cmd)
  config_set_defaults(fds)
  fdb_keys = {}
  fdb_keys['F'] = get_pdb_key(fds, precision, 'F')
  fdb_keys['B'] = get_pdb_key(fds, precision, 'B')
  fdb_keys['W'] = get_pdb_key(fds, precision, 'W')
  return_dict['fdb_keys'] = fdb_keys

  if request.is_json:
    return jsonify(return_dict['fdb_keys'])

  return render_template('display_keys.html',
                         result=return_dict,
                         driver=cmd,
                         config_id=res[0][0])
