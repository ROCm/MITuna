import json

coverage_file = open('../MITunaX/tests/covscripts/buffer/coverage.json')
coverage_data = json.load(coverage_file)

percent_covered = coverage_data['totals']['percent_covered']
percent_covered = '{:.2f}'.format(percent_covered)

file = open("../MITunaX/tests/covscripts/buffer/coverage_percentage.txt", "w")
file.write(percent_covered)

file.close()