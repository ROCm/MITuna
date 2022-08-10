import os
#import seaborn as sns
import matplotlib.pyplot as plt

from tuna.utils import logging
from tuna.utils.tools.io import safe_save


def histogram(data, x, filename=None):
  raise NotImplemented('implementation commented out to avoid seaborn as yet another dependency')
#  if isinstance(data, pd.DataFrame):
#    sns.set_style('white')
#    sns.displot(data=data, x=x, kind='hist')
#    save_or_show(plt, filename)

def save(plot, filename):
  plot.tight_layout()
  plot.savefig(filename, bbox_inches='tight')

def save_or_show(plot, filename, log=True):
  if filename is None:
    plot.show()
  else:
    safe_save(plot, filename, save, log_to_console=log)
    plot.close()
