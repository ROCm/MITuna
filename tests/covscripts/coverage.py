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

import json
import os
import argparse

root_dir = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
file_path_curcov_json = os.path.join(root_dir, "./coverage.json")
file_path_prevcov_txt = os.path.join(root_dir, "./develop_percent_coverage.txt")


def check_export(filename):
  """check if the path was successfully exported"""
  status = os.path.exists(filename)
  return status


def curcov():
  """extract current coverage from a json file"""
  curcov_json = open(file_path_curcov_json)
  curcov_data = json.load(curcov_json)
  curcov_percentage = curcov_data['totals']['percent_covered']
  curcov_percentage_formated = '{:.2f}'.format(curcov_percentage)
  curcov_percentage_ftdt = float(curcov_percentage_formated)
  return curcov_percentage_ftdt


def develop():
  """run and compare coverage for develop branch"""

  curcov_percentage_ftdt = curcov()

  print(
      f"Current Testing Coverage for develop branch is: {curcov_percentage_ftdt}%"
  )

  with open('develop_percent_coverage.txt', 'w') as f:
    f.write(str(curcov_percentage_ftdt))

  check_txt_export = check_export('develop_percent_coverage.txt')

  if check_txt_export is True:
    print(f"Coverage artifact file is exported successfully")
  else:
    raise ValueError('Failed to save coverage artifacts')


def branch():
  """run and compare coverage for the non-develop, peripheral branches"""

  curcov_percentage_ftdt = curcov()

  with open('develop_percent_coverage.txt', 'r') as f:
    prevcov_file = f.readline().strip()
    prevcov_percentage_ftdt = float(prevcov_file)

  print(
      f"Current Testing Coverage for current branch is: {curcov_percentage_ftdt}%"
  )
  print(
      f"Current Testing Coverage for develop branch is: {prevcov_percentage_ftdt}%"
  )
  if curcov_percentage_ftdt < prevcov_percentage_ftdt:
    raise ValueError('Code Coverage Decreased')


parser = argparse.ArgumentParser(
    description=
    'decide whether to extract coverage for develop or a peripheral branch')
parser.add_argument('function',
                    choices=['develop', 'branch'],
                    help='choose develop or branch')
args = parser.parse_args()

if args.function == 'develop':
  develop()
elif args.function == 'branch':
  branch()
