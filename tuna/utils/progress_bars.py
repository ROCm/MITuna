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
""" utils to construct progress bars """

import sys
import time


class ProgressBar():  # pylint: disable=too-few-public-methods
  """ progress bar to track progress

  inspired from stackoverflow.com/a/13685020/5046433 """

  def __init__(self,
               end_val,
               title='Progress',
               bar_length=10,
               char_at_end='\n'):
    self.title = title
    self.end_val = end_val
    self.bar_length = bar_length
    self.char_at_end = char_at_end

  def display(self, progress=0):
    """ display progress bar filled to the ratio of progress:end_val """
    percent = float(progress) / self.end_val
    hashes = '#' * int(round(percent * self.bar_length))
    spaces = ' ' * (self.bar_length - len(hashes))
    # pylint: disable-next=consider-using-f-string; it's clearer this way
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
  """ progress bar that completes when the set cooldown_time has run out """
  if cooldown_time != 0:
    if title is None:
      title = f'{cooldown_time}s Cooldown'

    progressbar = ProgressBar(end_val=cooldown_time,
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
