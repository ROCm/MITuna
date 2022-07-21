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
""" This file contains mappings relevant to Grafana dashboard responses """

PRCT_CHANGE = {
    "title": "Performance Comparison",
    "type": "table",
    "columns": [{
        "text": "arch",
        "type": "string"
    }, {
        "text": "direction",
        "type": "string"
    }, {
        "text": "avg",
        "type": "float"
    }],
    "refId": "performance-comparison",
    "rows": []
}

CMD_PRCT_CHANGE = {
    "title": "Performance Comparison",
    "type": "table",
    "columns": [{
        "text": "cmd",
        "type": "string"
    }, {
        "text": "arch",
        "type": "string"
    }, {
        "text": "direction",
        "type": "string"
    }, {
        "text": "avg",
        "type": "float"
    }],
    "refId": "performance-comparison",
    "rows": []
}

EXAMPLE_TABLE = {
    "title": "My Table Example",
    "type": "table",
    "columns": [{
        "text": "column1",
        "type": "string"
    }, {
        "text": "column2",
        "type": "string"
    }, {
        "text": "column3",
        "type": "int"
    }, {
        "text": "column4",
        "type": "float"
    }],
    "refId": "table-example",
    "rows": []
}
