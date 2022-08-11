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

  if log_to_console:
    logging.log("saving %s..." % filename, end_char='\r')

  file_already_exists = os.path.isfile(filename)

  if file_already_exists and not overwrite:
    logging.reset_line()
    if strict:
      raise FileExistsError('%s already exists!' % filename)
    else:
      logging.error('%s already exists!' % filename)
      return False

  dirpath = os.path.dirname(filename)
  if not os.path.isdir(dirpath):
    if not create_dir:
      logging.reset_line()
      if strict:
        raise NotADirectoryError('%s does not exist' % dirpath)
      else:
        logging.error('%s does not exist!' % dirpath)
        return False
    else:
      os.makedirs(dirpath)

  save_proc(obj, filename)

  if log_to_console:
    logging.reset_line()
    if file_already_exists:
      logging.success('updated %s    ' % filename)
    else:
      logging.success('created %s    ' % filename)

  return True


def safe_load(obj, filename, load_proc, log_to_console=True, strict=False):

  if log_to_console:
    logging.log("loading %s..." % filename, end_char='\r')

  if not os.path.isfile(filename):
    logging.reset_line()
    if strict:
      raise FileNotFoundError("Unable to load from {}".format(filename))
    else:
      logging.error("Unable to load from {}".format(filename))
      return False

  if obj is not None:
    load_proc(obj, filename)

    if log_to_console:
      logging.reset_line()
      logging.success('loaded %s    ' % filename)

    return True

  else:
    obj_returned = load_proc(filename)

    if log_to_console:
      logging.success('loaded %s    ' % filename)

    return obj_returned


def var_name_to_words(var_name, delimiter='_'):
  """convert variable names (eg __cube_root__) to words (eg Cube Root)"""
  words = ""
  for i in range(len(var_name)):
    curr_char = var_name[i]
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
