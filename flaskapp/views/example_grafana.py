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
"""Module for Grafana plugin"""
import json
from flask import Blueprint, jsonify, request
from tuna.flask_example import get_table_example

grafana = Blueprint('example_grafana', __name__, template_folder='templates')


@grafana.route('/search', methods=['POST', 'GET'])
def search():
  """Entrypoint needed for Grafana plugin"""
  req = request.get_json()
  return jsonify([], [])


@grafana.route('/query', methods=['POST', 'GET'])
def query():
  """Entrypoint needed for Grafana plugin"""
  req = request.get_json()
  grafana_req = req['targets'][0]['target'].split(',')
  data = []
  if grafana_req[0] == 'table-example':
    get_table_example(grafana_req, data)
  else:
    raise ValueError('Unsupported Grafana request: {}'.format(grafana_req[1]))

  return jsonify(data)


@grafana.route('/annotations', methods=['POST', 'GET'])
def annotations():
  """Entrypoint needed for Grafana plugin"""
  req = request.get_json()
  data = []
  return jsonify(data)


@grafana.route('/tag-keys', methods=['POST', 'GET'])
def tag_keys():
  """Entrypoint needed for Grafana plugin"""
  req = request.get_json()
  data = []
  return jsonify(data)


@grafana.route('/tag-values', methods=['POST', 'GET'])
def tag_values():
  """Entrypoint needed for Grafana plugin"""
  req = request.get_json()
  data = []
  return jsonify(data)


class Object():
  pass
