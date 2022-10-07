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
""" test the helpers functions/classes in utils """
import pdb
from tuna.utils.helpers import connect_callables
from tuna.utils.helpers import insert_in_sorted_list
from tuna.utils.helpers import nest
from tuna.utils.helpers import ParallelIterable
from tuna.utils.helpers import dict_to_csv_table
from tuna.utils.helpers import Deprecated

print(">> insert in sorted list test")
l = sorted([2, 12, 15, 20, 25, 33, 34, 38, 45, 49, 50], reverse=True)
print(l)
print(insert_in_sorted_list(l, 20))

print(">> connect_callables test")


def square(x):
  print(f'square({x}) called')
  return x**2


def cube(x):
  print(f'cube({x}) called')
  return x**3


def half(x):
  print(f'half({x}) called')
  return x / 2


#c_square, c_cube, c_half = connect_callables(square, cube, half)
#print( c_half(10) )

c_square, c_cube = connect_callables(square, cube)
c_square_dash, c_cube_dash, c_half = connect_callables(c_square, c_cube, half)

print('c_square')
print(c_square(10))
print('c_cube')
print(c_cube(10))
print('c_square_dash')
print(c_square_dash(10))
print('c_cube_dash')
print(c_cube_dash(10))
print('c_half')
print(c_half(10))

print(">> nesting test")
A = [2, 4, 6, 8]
B = [16, 36, 48, 64]
C = [128, 256, 512, 1025]
for a, b, c in nest(A, B, C):
  print(a, b, c)

print(">> PARALLEL ITERABLES TEST")
d = {'a': [1, 2, 3], 'b': 5, 'c': (-11, -13, -17, -18)}
p = ParallelIterable(d.values())

for e in p:
  print(e)

for e in p:
  print(e)

print(">> DICT TO CSV TABLE")
print(dict_to_csv_table(d))


class X(metaclass=Deprecated):
  pass


temp = False
if temp:
  X.v = 3
else:
  print('else')
