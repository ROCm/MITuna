import time
import os, sys

import tuna.utils.tools.io as io_tools
from tuna.utils.helpers import as_heading
import tuna.utils.tools.file as file_tools
from tuna.utils.ANSI_formatting import ANSIColors, ANSITools


class logging:
  RUNNING_LOG = ''

  @staticmethod
  def warning(string, end_char='\n', silent=False):
    logging.RUNNING_LOG += 'warning: %s\n' % string
    if sys.platform == 'win32':
      os.system('color')
    if not silent:
      sys.stdout.write("%s%s" % (ANSIColors.yellow(string), end_char))

  @staticmethod
  def info(string, end_char='\n', silent=False):
    logging.RUNNING_LOG += 'info: %s\n' % string
    if sys.platform == 'win32':
      os.system('color')
    if not silent:
      sys.stdout.write("%s%s" % (ANSIColors.blue(string), end_char))

  @staticmethod
  def error(string, end_char='\n', silent=False):
    logging.RUNNING_LOG += 'error: %s\n' % string
    if sys.platform == 'win32':
      os.system('color')
    if not silent:
      sys.stdout.write("%s%s" % (ANSIColors.red(string), end_char))

  @staticmethod
  def success(string, end_char='\n', silent=False):
    logging.RUNNING_LOG += 'success: %s\n' % string
    if sys.platform == 'win32':
      os.system('color')
    if not silent:
      sys.stdout.write("%s%s" % (ANSIColors.green(string), end_char))

  @staticmethod
  def log(string, formatting=None, end_char='\n', silent=False):
    logging.RUNNING_LOG += '%s\n' % string
    if not silent:
      if formatting is not None:
        sys.stdout.write("%s%s" % (formatting(string), end_char))
      else:
        sys.stdout.write("%s%s" % (string, end_char))

  @staticmethod
  def reset_line():
    sys.stdout.write(ANSITools.reset_line())

  @staticmethod
  def clean_slate():
    logging.RUNNING_LOG = ''

  @staticmethod
  def dump_logs(path=None, clean_slate_after_dump=True, append=False):
    str_to_dump = as_heading(
        time.strftime('%l:%M%p %Z on %b %d, %Y')) + '\n' + logging.RUNNING_LOG

    if path is None:
      print(str_to_dump)
    else:
      if append:
        io_tools.safe_save(str_to_dump, path, file_tools.append)
      else:
        io_tools.safe_save(str_to_dump, path, file_tools.write)

    if clean_slate_after_dump:
      logging.clean_slate()


# for backwards compatibility (and clean-ish interface)
warning = logging.warning
error = logging.error
success = logging.success
info = logging.info
log = logging.log
dump_logs = logging.dump_logs
reset_line = logging.reset_line
clean_slate = logging.clean_slate
