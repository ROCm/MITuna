import sys
import time


class ProgressBar():
  # inspired from stackoverflow.com/a/13685020/5046433
  def __init__(self, end_val, title='Progress', bar_length=10,
               char_at_end='\n'):
    self.title = title
    self.end_val = end_val
    self.bar_length = bar_length
    self.char_at_end = char_at_end

  def display(self, progress=0):
    percent = float(progress) / self.end_val
    hashes = '#' * int(round(percent * self.bar_length))
    spaces = ' ' * (self.bar_length - len(hashes))
    sys.stdout.write("\r{0}: [{1}] {2}%".format(self.title, hashes + spaces,
                                                int(round(percent * 100))))
    sys.stdout.flush()

    if progress == self.end_val:
      if self.char_at_end:
        sys.stdout.write(self.char_at_end)
        sys.stdout.flush()


def cooldown_timer(cooldown_time,
                   title=None,
                   bar_length=10,
                   char_at_end='\r\033[K',
                   update_rate=1):
  if cooldown_time != 0:
    if title is None:
      title = '%ds Cooldown' % cooldown_time

    progressbar = ProgressBar(
        end_val=cooldown_time,
        title=title,
        bar_length=bar_length,
        char_at_end=char_at_end)
    seconds_passed = 0
    progressbar.display(progress=seconds_passed)
    while seconds_passed < cooldown_time:
      diff = cooldown_time - seconds_passed
      sleep_time = update_rate if diff >= update_rate else diff

      time.sleep(sleep_time)
      seconds_passed += sleep_time
      progressbar.display(progress=seconds_passed)
