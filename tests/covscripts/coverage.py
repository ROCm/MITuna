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
  """run and compare coverage for develop branch"""
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
  curcov_percentage_ftdt = curcov(file_path_curcov_json)

  with open(coverage_file_name_txt, 'r') as f:
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


def main():
  root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

  parser = argparse.ArgumentParser(
      description=
      'decide whether to extract coverage for develop or a peripheral branch')
  parser.add_argument('function',
                      choices=['develop', 'branch'],
                      help='choose develop or branch')
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

  if args.function == 'develop':
    develop(root_dir, args.coverage_file_name_txt, args.coverage_file_name_json)
  elif args.function == 'branch':
    branch(root_dir, args.coverage_file_name_txt, args.coverage_file_name_json)


if __name__ == '__main__':
  main()
