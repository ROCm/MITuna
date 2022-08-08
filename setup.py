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

from setuptools import setup, find_packages
import os
thelibFolder = os.path.dirname(os.path.realpath(__file__))
requirementPath = thelibFolder + '/requirements.txt'
readmePath = thelibFolder + '/README.md'
install_requires = []  # Examples: ["gunicorn", "docutils>=0.3", "lxml==0.5a7"]

if os.path.isfile(readmePath):
  with open(readmePath) as f:
    readme = f.read()

if os.path.isfile(requirementPath):
  with open(requirementPath) as f:
    install_requires = f.read().splitlines()
setup(
    #this will be the package name you will see, e.g. the output of 'conda list' in anaconda prompt
    name='MITuna',
    python_requires='>=3.9',
    #some version number you may wish to add - increment this after every update
    version='0.1',
    description="Tuna is a distributed tuning infrastructure that provides pre-compiled kernels "\
                "for MIOpen customers through automated Jenkins pipelines and SLURM scalable "\
                "architecture.",
    long_description=readme,
    license='MIT',
    url='https://github.com/ROCmSoftwarePlatform/MITuna.git',
    install_requires=install_requires,

    # Use one of the below approach to define package and/or module names:

    #if there are only handful of modules placed in root directory, and no packages/directories exist then can use below syntax
    #     packages=[''], #have to import modules directly in code after installing this wheel, like import mod2 (respective file name in this case is mod2.py) - no direct use of distribution name while importing

    #can list down each package names - no need to keep __init__.py under packages / directories
    #     packages=['<list of name of packages>'], #importing is like: from package1 import mod2, or import package1.mod2 as m2

    #this approach automatically finds out all directories (packages) - those must contain a file named __init__.py (can be empty)
    packages=find_packages(
    ),  #include/exclude arguments take * as wildcard, . for any sub-package names
)
