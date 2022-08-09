import math
import numpy as np
import matplotlib.pyplot as plt
from collections import OrderedDict
from collections.abc import Sequence

from tuna.utils import logging
import tuna.utils.tools.io as io_tools
from tuna.utils.function import Function
import tuna.utils.tools.file as file_tools
import tuna.utils.tools.plot as plot_tools
from tuna.utils.ANSI_formatting import ANSIFormats, ANSIColors
from tuna.utils.helpers import var_name_to_words, dict_to_csv, dict_to_csv_table, \
               as_heading, pretty_iterator


plt.set_loglevel('ERROR')


class History(Sequence):
  """
    To track history of variables x, y and z, instantiate
    a History object:
    >> history = History('x', 'y', 'z')
    Then, for example, to add x=15, y=21, and z=19 to history, do
    >> history.add(15, 21, 19)
    You can also use keyword arguments
    >> history.add(15, y=21, z=19)
    To get the complete history of x, do
    >> history.x
    To get the state of x, y, and z at step 'k', do
    >> history[k]
  """
  NAMES_OF_STATS = Function.NAMES_OF_STATS

  def __init__(self, *names, title=None, track_stats = 'auto'):
    for name in names:
      if hasattr( self, name ):
        raise ValueError(f'cannot add the name {name} to history: change the name')

    self.function_names = names
    self.title = title
    self.track_stats = track_stats
    
    self.__functions__ = OrderedDict()
    for name in names:
      function = Function(name,  track_stats=track_stats) 
      self.__functions__[name] = function
      setattr( self, name, function )

    self.len = 0

    # for backwards compat
    self.add = self.add_event

  def to_str(self, max_length=None):
    s = pretty_iterator( self, sep='\n', max_items=max_length )
    if self.title is not None:
      return f"{as_heading(self.title)}\n{s}"
    else:
      return s
    
  def add_event(self, *args, **kwargs):
    for i, val in enumerate(args):
      ith_function = getattr( self, self.function_names[i] )
      ith_function.define( x=self.len, y=val ) 
    for name, val in kwargs.items():
      function = getattr( self, name )
      function.define( x=self.len, y=val )

    self.len += 1

  def extend(self, other_history):
    if self.function_names != other_history.function_names:
      raise ValueError('Cannot combine: the two histories appear to be tracking different data')

    for event in other_history:
      self.add_event(**event)

  def join(self, other_history):
    return self.__add__(other_history, as_events=False)

  def to_dict(self, min_unique_entries=-1):
    d = {}
    for name, function in self.__functions__.items():
      if len(function) > min_unique_entries:
        d[name] = function
    return d

  def to_list(self, min_unique_entries=-1):
    lst = []
    for name, function in self.__functions__.items():
      if len(function) > min_unique_entries:
        lst.append( function )
    return lst

  def to_csv(self, filename=None, min_unique_entries=-1):
    d = OrderedDict()
    for name, function in self.__functions__.items():
      if len(function) > min_unique_entries:
        d[name] = list( function.get_y() )

    if filename is not None:
      io_tools.safe_save( d, filename, dict_to_csv_table )
    else:
      return dict_to_csv_table(d)

  def dump_to_file(self, filename=None):
    io_tools.safe_save( self, filename, file_tools.dump_obj )

  def plot(self, filename=None, title=None, min_unique_entries=-1):
    functions_to_plot = []
    for name, function in self.__functions__.items():
      if len(function) > min_unique_entries:
        functions_to_plot.append( function )

    if len(functions_to_plot) == 0:
      fig, ax = plt.subplots()
    elif len(functions_to_plot) == 1:
      fig, ax = plt.subplots()
      function = functions_to_plot[0]
      function.plot( ax, title=var_name_to_words(function.name) )
    else:
      M = math.ceil( len(functions_to_plot) / 2 )
      N = math.ceil( len(functions_to_plot) / M )
      grid = (M, N)

      fig, axs = plt.subplots(*grid)
      if len(axs.shape) == 1:
        for i in range( len(functions_to_plot) ):
          function = functions_to_plot[i]
          function.plot( axs[i], title=var_name_to_words(function.name) )
      else:
        for i in range( len(functions_to_plot) ):
          m = math.floor(i / grid[1])
          n = i % grid[1]
          function = functions_to_plot[i]
          function.plot( axs[m, n], title=var_name_to_words(function.name) )

    if title:
      fig.suptitle(title, fontsize=16)

    fig.subplots_adjust(hspace=0.3)
    fig.tight_layout()
    plot_tools.save_or_show(plt, filename)

  def get_stat(self, stat_name):
    if stat_name not in History.NAMES_OF_STATS:
      raise ValueError(f'Invalid Stat Name: valid stat names are {History.NAMES_OF_STATS}')

    d = {}
    for name, function in self.__functions__.items():
      if len(function) > 0 and function.track_stats:
        d[name] = getattr( function, stat_name )
      else:
        d[name] = None
    return d

  def get_stats(self):
    d = {}
    for stat_name in History.NAMES_OF_STATS:
      d[stat_name] = self.get_stat( stat_name )
    return d

  def print_overview(self, delimiter=' | ', verbose=False, log=False):
    if not self.track_stats:
      logging.error('overview not available: stats tracking was disabled for this history object ')
      return

    string = ""
    for name, function in  self.__functions__.items():
      if function.track_stats is True:
        avg_str = 'AVG %.4f' % function.avg
        if verbose:
          min_str = 'MIN %.4f' % function.min
          max_str = 'MAX %.4f' % function.max
          std_str = 'STD %.4f' % function.std
          string += f"{name}: {avg_str} {std_str} {min_str} {max_str}{delimiter}"
        else:
          string += f"{name}: {avg_str}{delimiter}"

    if log:
      logging.log(string[:-len(delimiter)])
    else:
      print(string[:-len(delimiter)])

  def __repr__(self):
    return self.to_str(max_length=20)

  def __getitem__(self, i):
    if i >= len(self):
      raise IndexError('Index out of bounds')

    item = {}
    for name, function in self.__functions__.items():
      item[name] = function(i)
    return item

  def __len__(self):
    return self.len 

  def __add__(self, other, as_events=True):
    if self.track_stats is True and other.track_stats is True:
      track_stats = True
    elif self.track_stats is False and other.track_stats is False:
      track_stats = False
    else:
      track_stats = 'auto'

    title = f"{self.title}+{other.title}"

    if as_events:
      if self.function_names != other.function_names:
        raise ValueError('Cannot add: the two histories appear to be tracking different data')
      new_history = History( *self.function_names, title=title, track_stats=track_stats )
      for event in self:
        new_history.add_event( **event )
      for event in other:
        new_history.add_event( **event )
    else:
      combined_function_names = self.function_names + other.function_names
      new_history = History( *combined_function_names, title=title, track_stats=track_stats )
      for event_in_self, event_in_other in zip( self, other ):
        new_history.add_event( **event_in_self, **event_in_other )

    return new_history
