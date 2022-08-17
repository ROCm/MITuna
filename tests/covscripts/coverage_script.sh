#!/bin/bash 

python3 -m coverage run -m pytest #runs coverage reports 
python3 -m coverage json #exports coverage reports into a JSON file 
mv coverage.json ../MITunaX/tests/covscripts/buffer #move file into covscripts/buffer folder
python3 tests/covscripts/parse_attributes.py #parse coverage from JSON file and saves it into buffer file 
file="../MITunaX/tests/covscripts/buffer/coverage_percentage.txt" #picks up the file with the coverage percentage
name=$(cat "$file")        #assigns the output from the file 
echo "Total Coverage Percentage is:" $name" %"   #testing that the variable is correct