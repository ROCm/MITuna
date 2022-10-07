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
""" test the History class """
from tuna.utils.History import History

h1 = History('x', 'y', 'string', 'z', title='Test', track_stats='auto')
h1.add_event(3, 5, 'A', 6)
h1.add_event(5, 2, 'B', 7)
h1.add_event(-1, 6, 'C', 2)
print(h1)
h1.print_overview(verbose=True)
h1.plot(filename='/home/saud/for_experimentation/__delete_this_temp_fig.png')

h2 = History('x', 'y', 'string', 'z', title='Test2', track_stats='auto')
h2.add_event(15, 18, 'C', 2)
h2.add_event(13, 12, 'B', 7)
h2.add_event(11, 28, '1', 8)

print(h2)
h2.print_overview()

h = h1 + h2
print(h)
h.print_overview(verbose=True)

print(h.to_list())

print(h.get_stat(stat_name='avg'))
print(h.get_stats())

print(len(h))
