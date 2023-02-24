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
import json
import os

root_dir = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
file_path_json = os.path.join(root_dir, "./coverage.json")
file_path_prev = os.path.join(root_dir, "./develop_percent_coverage.txt")

coverage_file = open(file_path_json)
coverage_data = json.load(coverage_file)
percent_covered = coverage_data['totals']['percent_covered']
percent_covered = '{:.2f}'.format(percent_covered)
percent_covered = float(percent_covered)

with open(file_path_prev, 'r') as f:
  prev_coverage = f.readline().strip()
  prev_coverage_int = float(prev_coverage)

print(f"Current Testing Coverage for current branch is: {percent_covered}%")
print(f"Current Testing Coverage for develop branch is: {prev_coverage_int}%")
if percent_covered < prev_coverage_int:
  raise ValueError('Code Coverage Decreased')
