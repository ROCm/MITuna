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


def check_export(filename):
  """check if the file was successfully exported"""
  status = os.path.exists(filename)
  return status


def curcov(file_path_curcov_json):
  """extract current coverage from a json file"""
  with open(file_path_curcov_json) as curcov_json:
    curcov_data = json.load(curcov_json)
  curcov_percentage = curcov_data['totals']['percent_covered']
  curcov_percentage_ftdt = round(curcov_percentage, 2)
  return curcov_percentage_ftdt


def develop(root_dir, coverage_file_name_txt, coverage_file_name_json):
  """run and compare coverage for develop branch. Only runs when develop is ran"""
  file_path_curcov_json = os.path.join(root_dir, coverage_file_name_json)
  curcov_percentage_ftdt = curcov(file_path_curcov_json)

  print(
      f"Current Testing Coverage for develop branch is: {curcov_percentage_ftdt}%"
  )

  with open(coverage_file_name_txt, 'w') as f:
    f.write(str(curcov_percentage_ftdt))

  check_txt_export = check_export(coverage_file_name_txt)

  if check_txt_export:
    print(
        f'Coverage artifact file {coverage_file_name_txt} is exported successfully'
    )
  else:
    raise ValueError(
        f'Failed to save coverage {coverage_file_name_txt} for artifact exports'
    )


def branch(root_dir, coverage_file_name_txt, coverage_file_name_json):
  """run and compare coverage for the non-develop, peripheral branches"""
  file_path_curcov_json = os.path.join(root_dir, coverage_file_name_json)
  cur_cov = curcov(file_path_curcov_json)
  prev_cov = None

  with open(coverage_file_name_txt, 'r') as f:
    prevcov_file = f.readline().strip()
    prev_cov = float(prevcov_file)

  print(f"Current Testing Coverage for current branch is: {cur_cov}%")
  print(f"Current Testing Coverage for develop branch is: {prev_cov}%")
  prct_change = (prev_cov - cur_cov) / prev_cov * 100
  if prct_change > 0.5:
    raise ValueError(
        f"Code Coverage Decreased by more than 0.5%%. Prev:{prev_cov}, cur: {cur_cov}"
    )


def main():
  root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

  parser = argparse.ArgumentParser(
      description=
      'decide whether to extract coverage for develop or a peripheral branch')
  parser.add_argument(
      'function',
      help=
      'enter "develop" or any other string representing the peripheral branch')
  parser.add_argument(
      '--txt',
      dest='coverage_file_name_txt',
      default='develop_percent_coverage.txt',
      help='Name of the txt file to store the coverage percentage')
  parser.add_argument('--json',
                      dest='coverage_file_name_json',
                      default='coverage.json',
                      help='Name of the json file containing coverage data')
  args = parser.parse_args()

  if args.function.lower() == 'develop':
    develop(root_dir, args.coverage_file_name_txt, args.coverage_file_name_json)
  else:
    branch(root_dir, args.coverage_file_name_txt, args.coverage_file_name_json)


if __name__ == '__main__':
  main()
