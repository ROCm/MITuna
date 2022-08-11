class ANSIColors:
  # inpired from https://stackoverflow.com/a/287944/5046433
  BLUE = '\033[94m'
  CYAN = '\033[96m'
  GREEN = '\033[92m'
  YELLOW = '\033[93m'
  RED = '\033[91m'
  MAGENTA = '\u001b[35m'
  GREY = '\u001b[38;5;8m'
  END_COLOR = '\033[0m'

  @staticmethod
  def blue(string):
    return "{}{}{}".format(ANSIColors.BLUE, string, ANSIColors.END_COLOR)

  @staticmethod
  def cyan(string):
    return "{}{}{}".format(ANSIColors.CYAN, string, ANSIColors.END_COLOR)

  @staticmethod
  def green(string):
    return "{}{}{}".format(ANSIColors.GREEN, string, ANSIColors.END_COLOR)

  @staticmethod
  def yellow(string):
    return "{}{}{}".format(ANSIColors.YELLOW, string, ANSIColors.END_COLOR)

  @staticmethod
  def red(string):
    return "{}{}{}".format(ANSIColors.RED, string, ANSIColors.END_COLOR)

  @staticmethod
  def magenta(string):
    return "{}{}{}".format(ANSIColors.MAGENTA, string, ANSIColors.END_COLOR)

  @staticmethod
  def grey(string):
    return "{}{}{}".format(ANSIColors.GREY, string, ANSIColors.END_COLOR)


class ANSIFormats:
  #  inpired from https://stackoverflow.com/a/287944/5046433
  HEADER = '\033[95m'
  BOLD = '\033[1m'
  UNDERLINE = '\033[4m'
  REVERSED = '\u001b[7m'
  END_FORMAT = '\033[0m'

  @staticmethod
  def header(string):
    return "{}{}{}".format(ANSIFormats.HEADER, string, ANSIFormats.END_FORMAT)

  @staticmethod
  def bold(string):
    return "{}{}{}".format(ANSIFormats.BOLD, string, ANSIFormats.END_FORMAT)

  @staticmethod
  def underline(string):
    return "{}{}{}".format(ANSIFormats.UNDERLINE, string,
                           ANSIFormats.END_FORMAT)

  @staticmethod
  def reversed(string):
    return "{}{}{}".format(ANSIFormats.REVERSED, string, ANSIFormats.END_FORMAT)


class ANSITools:
  CLEAR_LINE = "\033[K"
  CARRAGE_RETURN = "\r"

  @staticmethod
  def reset_line():
    return "{}{}".format(ANSITools.CLEAR_LINE, ANSITools.CARRAGE_RETURN)
