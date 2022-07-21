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
"""Module to compose driver cmd"""
import argparse
from tuna.parsing import parse_pdb_key, build_driver_cmd


def parse_args():
  """Parsing arguments"""
  parser = argparse.ArgumentParser(
      description='Replace token string with driver command')
  parser.add_argument('-i',
                      '--infile',
                      type=str,
                      dest='infile',
                      default=None,
                      required=True,
                      help='File to pull tokens from')
  parser.add_argument('-o',
                      '--outfile',
                      type=str,
                      dest='outfile',
                      default=None,
                      required=True,
                      help='Write results to this file')

  args = parser.parse_args()
  return args


def main():
  """Main module function"""
  args = parse_args()
  fin = open(args.infile, 'r')
  fout = open(args.outfile, 'w')

  for line in fin:
    if '=' in line:
      elem = line.split('=')
      fds, vals, precision, direction, _ = parse_pdb_key(elem[0])
      cmd = build_driver_cmd(fds, vals, precision, direction)
      outstr = '"{}",{}'.format(cmd, elem[1])
    else:
      outstr = line
    fout.write(outstr)

  fin.close()
  fout.close()


if __name__ == '__main__':
  main()
