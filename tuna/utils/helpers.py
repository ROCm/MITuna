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
""" some helpful utils/tools """

import re
import sys
import copy
from enum import Enum
from math import floor
from collections import OrderedDict
from collections.abc import Iterator, Iterable

import numpy as np


def pretty_iterator(iterator: Iterator, sep=', ', max_items=None):
  """ convert iterator to a pretty-print string """
  list_like = list(iterator)

  if len(list_like) == 0 or max_items == 0:
    return ""

  if max_items is None or max_items >= len(list_like):
    return sep.join([str(item) for item in list_like])

  left_substr = pretty_iterator(list_like[:max_items - 1],
                                sep=sep,
                                max_items=None)
  return f"{left_substr}{sep}...{sep}{list_like[-1]}"


def print_dict_as_table(d, printer=print):  # pylint: disable=invalid-name
  """ print dictionary as a table w/ keys as the leftmost column """
  if len(d) == 0:
    printer('')
  else:
    COLUMN_SPACING = 5  # pylint: disable=invalid-name
    longest_key_length = max(len(key) for key in d)
    m = len(str(len(d))) + COLUMN_SPACING  # pylint: disable=invalid-name
    n = longest_key_length + COLUMN_SPACING  # pylint: disable=invalid-name
    for i, (key, val) in enumerate(d.items()):
      printer(f'{i+1}.'.ljust(m) + f'{key}'.ljust(n) + f'{val}')


def as_title(title: str, overline_char='+', underline_char='+'):
  """ convert string to a title string """
  underline = underline_char * len(str(title))
  overline = overline_char * len(str(title))
  return f'\n{overline}\n{title}\n{underline}'


def as_heading(heading: str, underline_char='-'):
  """ convert string to a heading string """
  underline = underline_char * len(str(heading))
  return f'\n{heading}\n{underline}'


def print_title(title, printer=print, **kwargs):
  """ print string as a title """
  printer(as_title(title, **kwargs))


def print_heading(heading, printer=print, **kwargs):
  """ print string as a heading """
  printer(as_heading(heading, **kwargs))


def sort_dict(d, by_value=True):  # pylint: disable=invalid-name
  """ sort dictionary """
  if by_value:
    key = lambda tup: tup[1]  # pylint: disable=unnecessary-lambda-assignment
  else:
    key = lambda tup: tup[0]  # pylint: disable=unnecessary-lambda-assignment

  sorted_d = OrderedDict()
  for k, v in sorted(d.items(), key=key):  # pylint: disable=invalid-name
    sorted_d[k] = v

  return sorted_d


# pylint: disable-next=invalid-name
def invert_dict(d):
  """ return the inverse map of d """
  return {val: key for key, val in d.items()}


# pylint: disable-next=invalid-name
def wierd_ratio(a, b, max_val=sys.maxsize / 4):
  """ wierd ratio that handles a/0=max_val, 0/0=0 """
  if b != 0:
    return a / b
  if a != 0:
    return max_val
  return 0


# pylint: disable-next=invalid-name
def proper_dict_of_dicts_to_csv(d, filename=None, sep=',', encoding=None):
  """  convert a proper dict_of_dicts to a string of comma-seperated vals

  a dict_of_dicts is proper if each of the inner dicts have the same keys
  """
  csv = ""
  if len(d) > 0:
    col_keys = list(d.values())[0].keys()
    col_keys = sep.join(sorted(col_keys))
    csv += f" {sep}{col_keys}\n"
    for row_key, row_dict in d.items():
      line = f"{row_key}"
      for _, col_val in sorted(row_dict.items(), key=lambda item: item[0]):
        line += f"{sep}{col_val}"
      csv += f"{line}\n"

  if filename is None:
    return csv
  with open(filename, 'w', encoding=encoding) as file:
    file.write(csv)
  return None


class ParallelIterable(Iterable):
  """allows one to iterate over multiple iterables in parallel

  use case: see dict_to_csv_table()
  """

  def __init__(self, iterable_of_iterables, excluded_iterables=None):
    self.iterable_of_iterables = iterable_of_iterables
    if excluded_iterables is None:
      self.excluded_iterables = []
    else:
      self.excluded_iterables = excluded_iterables

  def __reset_iterators__(self):
    """ rests the iterators """
    self.iterators = []  # pylint: disable=attribute-defined-outside-init
    for iterable in self.iterable_of_iterables:
      if not isinstance(iterable, Iterable):
        self.iterators.append([iterable].__iter__())
      elif not iterable in self.excluded_iterables:
        self.iterators.append(iterable.__iter__())
    self.is_exausted = False  # pylint: disable=attribute-defined-outside-init

  def __iter__(self):
    self.__reset_iterators__()
    return self

  def __next__(self):
    if self.is_exausted:
      raise StopIteration

    nexts, n_exausted_iterators = [], 0
    for iterator in self.iterators:
      try:
        nexts.append(next(iterator))
      except StopIteration:
        nexts.append(None)
        n_exausted_iterators += 1

    if n_exausted_iterators == len(self.iterators):
      self.is_exausted = True  # pylint: disable=attribute-defined-outside-init
      raise StopIteration

    return tuple(nexts)


def dict_to_csv_table(d, filename=None, sep=',', encoding=None):  # pylint: disable=invalid-name
  """writes a dict to csv as a table with the keys as 1st row

  example:

  ballistic_trajectory = {'x': [0, 1, 2, 3, 4],
                  'z': [0, -1, -4, -9, -16]}
  dict_to_csv_table( ballistic_trajectory, 'position.csv' )

  contents of position.csv
  x, z
  0, 0
  1, -1
  2, -4
  3, -9
  4, -16
  """
  csv = sep.join((str(key) for key in d.keys()))  # header
  for vals in ParallelIterable(d.values()):
    csv += "\n" + sep.join((str(val) for val in vals))

  if filename is None:
    return csv
  with open(filename, 'w', encoding=encoding) as file:
    file.write(csv)
  return None


def dict_to_csv(d, filename=None, sep=',', encoding=None):  # pylint: disable=invalid-name
  """ writes out a dict as a csv of key, val pairs """
  csv = ""
  for key, val in d.items():
    line = f"{key}"
    if isinstance(val, dict):
      for key0, val0 in val.items():
        line += f"{sep}{key0}{sep}{val0}"
    elif isinstance(val, Iterable) and not isinstance(val, str):
      for item in val:
        line += f"{sep}{item}"
    else:
      line += f"{sep}{val}"

    csv += f"{line}\n"

  if filename is None:
    return csv
  with open(filename, 'w', encoding=encoding) as file:
    file.write(csv)
  return None


def is_substr(key, string):
  """ check if key is a substring of the given string """
  return string.find(key) != -1


def map_list(lst, _map):
  """ map one list to another using the given map """
  if isinstance(_map, dict):
    return [_map[x] for x in lst]
  return [_map(x) for x in lst]


def filter_list(lst, _filter):
  """ keep only filtered elements """
  return [x for x in lst if _filter(x)]


def filter_out(lst, _filter):
  """ remove elements that pass the filter """
  return [x for x in lst if not _filter(x)]


def merge_two_dicts(superior_dict, inferior_dict):
  """ merges dicts. breaks ties by preferring the superior_dict """
  merged_dict = copy.deepcopy(inferior_dict)
  for key, val in superior_dict.items():
    merged_dict[key] = val
  return merged_dict


def merge_dicts(*dicts):
  """ merge dicts into a single dict, keeping the given order of dicts """
  # pylint: disable-next=invalid-name
  d = OrderedDict(list(dicts[0].items()) + list(dicts[1].items()))
  if len(dicts) == 2:
    return d
  return merge_dicts(d, *dicts[2:])


def has_duplicates(lst):
  """ check if list has duplicate items """
  return len(lst) != len(set(lst))


def get_map(lst):
  """ convert dict to a dict mapping items to indices """
  return {item: ind for ind, item in enumerate(lst)}


def get_reverse_map(lst):
  """ convert dict to a dict mapping indicies to items """
  return dict(enumerate(lst))


def list_replace(lst, replacee, replacer):
  """ replace the given item in a list """
  new_lst = copy.deepcopy(lst)
  try:
    i = new_lst.index(replacee)
    new_lst[i] = replacer
    return new_lst
  except ValueError:
    return new_lst


def constant_list(size, constant):
  """ return a list filled with some given constant """
  if isinstance(size, int):
    return [constant for i in range(size)]
  if len(size) == 1:
    return [constant for i in range(size[0])]
  return [constant_list(size[1:], constant) for i in range(size[0])]


def unique_list(lst):
  """ return the unique elements in a list """
  return list(set(lst))


def get_categorial_vectors(lst, zeros_creator=np.zeros):
  """ maps items in list to one-hot encoded vectors """
  if has_duplicates(lst):
    unique_lst = set(lst)
  else:
    unique_lst = lst

  vectors = {}
  for i, item in enumerate(unique_lst):
    vector = zeros_creator(len(unique_lst))
    vector[i] = 1
    vectors[item] = vector

  return vectors


def product(lst):
  """ returns the product of a list's elements """
  prod = lst[0]
  for val in lst[1:]:
    prod *= val
  return prod


def compose(*fns):
  """ compose(f, g) = g o f """
  if len(fns) == 1:
    return fns[0]
  f = fns[0]  # pylint: disable=invalid-name
  g = compose(*fns[1:])  # pylint: disable=invalid-name
  return lambda x: g(f(x))


def var_name_to_words(var_name, delimiter='_'):
  """convert variable names (eg __cube_root__) to words (eg Cube Root)"""
  words = ""
  for i, curr_char in enumerate(var_name):
    if i == 0:
      prev_char = None
    else:
      prev_char = var_name[i - 1]

    if curr_char == delimiter:
      char_to_write = ' '
    elif prev_char is None or prev_char == delimiter:
      char_to_write = curr_char.upper()
    else:
      char_to_write = curr_char

    words += char_to_write

  words = re.sub(r'\s\s+', ' ', words.strip())
  return words


def typename(instance):
  """ return the typename of an object """
  return instance.__class__.__name__


class SIZE_UNITS(Enum):  # pylint: disable=invalid-name; naming enums w/ all-caps
  """ defines the different binary size units """
  BYTE = 2**0
  KB = 2**10
  MB = 2**20
  GB = 2**30


# pylint: disable=invalid-name; it's a callable
class connected_callable:
  """ create a callable connected to other callables """

  def __init__(self, index, callables):
    """ connect list of callables to the callable at given index """
    self.__ind__ = index
    self.__callables__ = callables
    self.__is_connected__ = True

  def __call__(self, *args, **kwargs):
    assert self.__is_connected__, "error: this callable's connection has been terminated"
    for i, c in enumerate(self.__callables__):  # pylint: disable=invalid-name
      if i == self.__ind__:
        out = c(*args, **kwargs)
      else:
        c(*args, **kwargs)
    return out

  def isolate_callable(self):
    """ returns the callable as isolated from the other callables """
    return self.__callables__[self.__ind__]

  def terminate_connection(self):
    """ terminates the connected callable's connection """
    self.__is_connected__ = False
    return self.__callables__[self.__ind__]


def connect_callables(*callables, recursive=False):
  """given a sequence of callables <a_1, ..., a_n>, this subroutine returns
  a sequence of callables <b_1, ..., b_n> such that the call b_i(x) evalautes
  to a_i(x), however, it implicitly entails an update to the state of all
  the callables a_1, ..., a_n with input x.

  Objects in computer programming behave very similarly to objects in Classical
  Mechanics -- each object has its own state. This model becomes limiting in
  quantum mechanics, where things seem "connected".

  A good-for-nothing use case (see how I connected train and test histories for
  an actual use case):

  def square(x):
    print(f'square({x}) called')
    return x**2
  def cube(x):
    print(f'cube({x}) called')
    return x**3
  c_square, c_cube = connect_callables(square, cube)
  y = c_square(4)   # square(4) called
            # cube(4) called
  print(y)      # 16

  """
  mycallables = []
  for i, c in enumerate(callables):  # pylint: disable=invalid-name
    if isinstance(c, connected_callable) and not recursive:
      mycallables.append(c.isolate_callable())
    else:
      mycallables.append(c)

  connected_callables = []
  for i, c in enumerate(callables):  # pylint: disable=invalid-name
    connected_callables.append(
        connected_callable(index=i, callables=mycallables))

  return tuple(connected_callables)


def is_comparable(obj):
  """ does an object implement the relational/equiality comparision interaface """
  return  hasattr(obj, '__eq__') and \
      (hasattr(obj, '__lt__') or hasattr(obj, '__le__') or \
       hasattr(obj, '__gt__') or hasattr(obj, '__ge__'))


def are_comparable(obj1, obj2):
  """ can two objects be (equality, relationally) compared? """
  try:
    # pylint: disable=pointless-statement
    obj1 == obj2
    obj1 < obj2
    return True
  except TypeError:
    return False


def insert_in_sorted_list(lst, val, ascending=None):
  """ insert values into a sorted list while mainting the sorted order using binary insertion """

  def _insert_in_sorted_list_1(p, q):  # pylint: disable=invalid-name
    """ ascending case """
    if p == q:
      return lst[:p] + [val] + lst[p:]
    mid = floor((p + q) / 2)
    if val < lst[mid]:
      return _insert_in_sorted_list_1(p, mid)
    if val > lst[mid]:
      return _insert_in_sorted_list_1(mid + 1, q)
    return lst[:mid] + [val] + lst[mid:]

  def _insert_in_sorted_list_2(p, q):  # pylint: disable=invalid-name
    """ decending case """
    if p == q:
      return lst[:p] + [val] + lst[p:]
    mid = floor((p + q) / 2)
    if val > lst[mid]:
      return _insert_in_sorted_list_2(p, mid)
    if val < lst[mid]:
      return _insert_in_sorted_list_2(mid + 1, q)
    return lst[:mid] + [val] + lst[mid:]

  if ascending is None:
    if len(lst) < 2:
      ascending = True
    else:
      i = 0
      while len(lst) - i - 2 > 0 and lst[-2 - i] == lst[-1 - i]:
        i += 1
      ascending = lst[-2 - i] < lst[-1 - i]

    ascending = len(lst) < 2 or lst[-2] < lst[-1]

  if ascending:
    return _insert_in_sorted_list_1(0, len(lst))
  return _insert_in_sorted_list_2(0, len(lst))


def nest(*iterators):
  """ nested iterators

  use case: get rid of ugly-looking nested for loops:

  for a in A:
    for b in B:
      for c in C:
        // do smtg

  is equivalent to:

  for a, b, c in nest(A, B, C):
    // do smtg
  """
  if len(iterators) == 1:
    for item in iterators[0]:
      yield (item,)
  else:
    for outer_item in iterators[0]:
      for inner_items in nest(*iterators[1:]):
        yield (outer_item,) + inner_items


class Deprecated(type):
  """ Deprecates a class

  To declare a class X as depracated, set its metaclass to
  Deprecated, and take its implementation out

  class X(metaclass=Deprecated):
    pass

  attempts to use a Deprecated class will fail at runtime:
  a = X()                      # instatntiation
  X.v              # class member access
  X.v=3            # defining class members
  class Y(X): pass             # subclassing

  Note (in C++ lingo):
  Deprecating a class is different from removing the class
  definition. If a class is not defined, and your code refers to
  that class, it'd be a compile-time error. But if a class is
  declared as Deprecated, it'd only result in an error at runtime
  when the user's actions lead the execution to a point where the
  deprecated class is made use of.
  """

  # pylint: disable-next=unused-argument, super-init-not-called
  def __init__(cls, *a, **kw):
    cls.__new__ = Deprecated.__deprecated__

  # pylint: disable-next=function-redefined
  def __new__(cls, name, bases, clsdict):
    for base in bases:
      if isinstance(base, Deprecated):
        raise Exception('Support removed for deprecated entity')
    return type.__new__(cls, name, bases, dict(clsdict))

  def __getattribute__(cls, name):
    raise Exception('Support removed for deprecated entity')

  def __hasattr__(cls, name):
    raise Exception('Support removed for deprecated entity')

  def __getattr__(cls, name):
    raise Exception('Support removed for deprecated entity')

  def __setattr__(cls, name, value):
    if name == '__new__' and value == Deprecated.__deprecated__:
      super().__setattr__(name, value)
    else:
      raise Exception('Support removed for deprecated entity')

  @classmethod
  def __deprecated__(cls):
    raise Exception('Support removed for deprecated entity')


# FOR BACKWARDS COMPATIBILITY
pretty_list = pretty_iterator
dict_to_file = dict_to_csv
