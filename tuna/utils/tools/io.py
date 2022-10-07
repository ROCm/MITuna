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
""" utils/tools to support file I/O """

import os
import re

from tuna.utils import logging


def safe_save(obj,
              filename,
              save_proc,
              overwrite=True,
              create_dir=True,
              log_to_console=True,
              strict=False):
  """ safely save the given obj using the given save_procedure

  the safty checks involve overwriting check, directory-non-existent check, etc. """

  if log_to_console:
    logging.log(f"saving {filename}...", end_char='\r')

  file_already_exists = os.path.isfile(filename)

  if file_already_exists and not overwrite:
    logging.reset_line()
    if strict:
      raise FileExistsError(f'{filename} already exists!')

    logging.error(f'{filename} already exists!')
    return False

  dirpath = os.path.dirname(filename)
  if not os.path.isdir(dirpath):
    if not create_dir:
      logging.reset_line()
      if strict:
        raise NotADirectoryError(f'{dirpath} does not exist')

      logging.error(f'{dirpath} does not exist!')
      return False

    os.makedirs(dirpath)

  save_proc(obj, filename)

  if log_to_console:
    logging.reset_line()
    if file_already_exists:
      logging.success(f'updated {filename}    ')
    else:
      logging.success(f'created {filename}    ')

  return True


def safe_load(obj, filename, load_proc, log_to_console=True, strict=False):
  """ safely load the given obj using the given load_procedure

  the safty checks involve overwriting check, directory-non-existent check, etc. """
  if log_to_console:
    logging.log(f"loading {filename}...", end_char='\r')

  if not os.path.isfile(filename):
    logging.reset_line()
    if strict:
      raise FileNotFoundError(f"Unable to load from {filename}")

    logging.error(f"Unable to load from {filename}")
    return False

  if obj is not None:
    load_proc(obj, filename)

    if log_to_console:
      logging.reset_line()
      logging.success(f'loaded {filename}    ')

    return True

  obj_returned = load_proc(filename)

  if log_to_console:
    logging.success(f'loaded {filename}    ')

  return obj_returned


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
