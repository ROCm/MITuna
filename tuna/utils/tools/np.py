import numpy as np

from tuna.utils import logging

def warn_if(condition, warning='', any=True):
  if (any and not condition.any()) or (not any and not condition.all()):
    logging.warning(warning)
    return False

  return True

def err_if(condition, error='', any=True, strict=False):
  if (any and not condition.any()) or (not any and not condition.all()):
    if strict:
      raise AssertionError(error)
    else:
      logging.error(error)
      return False

  return True
