#!/bin/bash 
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
previous_file="./utils/coverage_files/coverage_percentage.txt"
old_var=$(cat "$previous_file")
python3 -m coverage run -m pytest #runs coverage reports
python3 -m coverage json #exports coverage reports into a JSON file 
mv coverage.json ./utils/coverage_files #move file into covscripts/buffer folder
python3 tests/covscripts/coverage_parse_attributes.py #parse coverage from JSON file and saves it into buffer file
file="./utils/coverage_files/coverage_percentage.txt" #picks up the file with the coverage percentage
new_var=$(cat "$file")        #assigns the output from the file
echo "Total Coverage Percentage is:" $new_var" %"   #testing that the variable is correct

echo "----------------------------------------------------------";
echo "Coverage Status:";
echo "[Prior Repo Coverage Stats] --: $old_var%";
echo "[New coverage Committed Coverage Stats] --: % $new_var%";
