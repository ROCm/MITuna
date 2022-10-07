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
""" utils for working with and processing files """

import os
import dill

from tuna.utils.helpers import SIZE_UNITS


def get_extension(filepath):
  """ get a file's extension """
  return os.path.splitext(filepath)[1]


def get_files(directory, extension=None, full_file_path=True):
  """ get the names of files in a directory """
  files = []
  for item in os.listdir(directory):
    item_path = os.path.join(directory, item)
    if os.path.isfile(item_path):
      if full_file_path:
        files.append(item_path)
      else:
        files.append(item)

  if extension is None:
    return files

  return [file for file in files if get_extension(file) == extension]


def get_txt_files(directory, full_file_path=True):
  """ get the names of txt files in a directory """
  return get_files(directory, extension='.txt', full_file_path=full_file_path)


def save(data, path, mode='w'):
  """ save string data to the given path under the given mode """
  with open(path, mode) as file:  # pylint: disable=unspecified-encoding
    file.write(data)


def write(data, path):
  """ (over)write string data at the given path """
  save(data, path, mode='w')


def append(data, path):
  """ append string data to the given filepath """
  save(data, path, mode='a')


def dump_obj(obj, path):
  """ dump obj as a pickle """
  with open(path, 'wb') as file:
    dill.dump(obj, file)


def load_obj(path):
  """ load obj from a pickle """
  with open(path, 'rb') as file:
    obj = dill.load(file)
    return obj


def get_size(path, units: SIZE_UNITS = SIZE_UNITS.BYTE):
  """ get the size of a file """
  size_in_bytes = os.path.getsize(path)
  return size_in_bytes / units.value
