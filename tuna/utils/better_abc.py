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
""" copied from krassowski's answer at stackoverflow.com/a/50381071 """

from abc import ABCMeta as NativeABCMeta


# pylint: disable-next=too-few-public-methods
class DummyAttribute:
  """ dummy class to handle making None type attributes abstract """


def abstract_attribute(obj=None):
  """ makes provided attribute abstract by setting __is_abstract_attribute__ flag """
  if obj is None:
    obj = DummyAttribute()
  # pylint: disable-next=attribute-defined-outside-init
  obj.__is_abstract_attribute__ = True
  return obj


class ABCMeta(NativeABCMeta):
  """ better ABCMeta """

  def __call__(cls, *args, **kwargs):
    instance = NativeABCMeta.__call__(cls, *args, **kwargs)
    abstract_attributes = {
        name for name in dir(instance)
        if getattr(getattr(instance, name), '__is_abstract_attribute__', False)
    }
    if abstract_attributes:
      raise NotImplementedError(
          f"Can't instantiate abstract class {cls.__name__} with"
          f" abstract attributes: {', '.join(abstract_attributes)}")
    return instance
