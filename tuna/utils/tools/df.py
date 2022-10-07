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
""" utilities to work with and process dataframes """

from collections import OrderedDict

import numpy as np
import pandas as pd
# from sklearn.model_selection import train_test_split as sklearn_train_test_split

from tuna.utils import logging
from tuna.utils.ANSI_formatting import ANSIFormats
from tuna.utils.helpers import get_map, get_categorial_vectors, pretty_list


# pylint: disable-next=invalid-name
def to_pickle(df, filename):
  """ save dataframe as a pickled file """
  df.to_pickle(filename)


def from_pickle(filename):
  """ read dataframe from a pickle """
  return pd.read_pickle(filename)


# pylint: disable-next=invalid-name
def to_csv(df, filename):
  """ save dataframe as a csv file """
  df.to_csv(filename, index=False)


def read_csv(filename, **kwargs):
  """ read dataframe from a csv file """
  return pd.read_csv(filename, **kwargs)


def read_noheader_csv(filename, **kwargs):
  """ read dataframe from a csv file with no header (i.e., no column names) """
  kwargs['header'] = None
  return read_csv(filename, **kwargs)


def read_csv_as_float32(filename, **kwargs):
  """ read a csv file into a dataframe of float32 values """
  kwargs['dtype'] = np.float32
  return read_csv(filename, **kwargs)


def read_noheader_csv_as_float32(filename, **kwargs):
  """ read a csv file with no header line into a dataframe of float32 values """
  kwargs['header'] = None
  return read_csv_as_float32(filename, **kwargs)


def to_dict(series):
  """ convert a pandas series object to a dictionary """
  return series.to_dict(OrderedDict)


# pylint: disable-next=invalid-name
def is_col_unique(df, col_name):
  """ checks if column in unique """
  if col_name not in df.columns:
    raise KeyError(f'{col_name} is not a column in the given dataframe')
  if len(df) == 0:
    return True

  first_entry = df[col_name].iloc[0]
  return not (df[col_name] != first_entry).any()


# pylint: disable-next=invalid-name, unused-argument
def select_multiple(df, col_val_map, strict=False):
  """ select all rows where the entries in the given columns equal given values """
  if len(col_val_map) == 0:
    return df

  for i, (colname, value) in enumerate(col_val_map.items()):
    if i == 0:
      query = df[colname] == value
    else:
      query = query & (df[colname] == value)
  return df[query]


# pylint: disable-next=invalid-name
def select(df, colname, value, strict=False):
  """ select all rows in the dataframe where the entry in the given column equals given value """
  sub_df = df[df[colname] == value]
  if len(sub_df) == 0:
    msg = f'{value} not present in {colname}. {colname} only contains {{' +\
        pretty_list( df[colname].unique(), max_items=10 ) + '}'
    if strict:
      raise ValueError(msg)

    logging.error(msg)

  return sub_df


# pylint: disable-next=invalid-name
def split(df, columns):
  """ split dataframe into two dataframes: one with the given columns in it, the other without """
  if isinstance(columns, list):
    mask = df.columns.isin(columns)
  else:
    mask = df.columns == columns

  df1 = df.iloc[:, ~mask]
  df2 = df.iloc[:, mask]

  return df1, df2


# pylint: disable-next=invalid-name, unused-argument
def train_test_split(df, train_ratio, random=False, seed=None):
  """ split dataframe into two dataframes determined by the train_ratio """
  if not random:
    train_size = int(len(df) * train_ratio)
    train = df.iloc[:train_size, :]
    test = df.iloc[train_size:, :]

  else:
    # train, test = sklearn_train_test_split(df,
    #                                        train_size=train_ratio,
    #                                        random_state=seed)
    raise NotImplementedError(
        'sklearn-based implementation has been commented out' +
        'to avoid another dependency')

  return train, test


def combine(*dfs):
  """ combine dataframes along columns """
  return pd.concat(dfs, axis=1)


def extend(*dfs):
  """ combine dataframes along rows """
  return pd.concat(dfs, axis=0)


# pylint: disable-next=invalid-name
def insert_col(df, loc, col, inplace=False):
  """ insert a column into a dataframe at the given location """
  if inplace:
    df.insert(loc, col.name, col)
    return None

  df_new = df.copy(deep=True)
  insert_col(df_new, loc, col, inplace=True)
  return df_new


# pylint: disable-next=invalid-name
def insert_cols(df, loc, cols, inplace=False):
  """ insert columns into a dataframe starting at the given location """
  if inplace:
    for i, colname in enumerate(cols):
      insert_col(df, loc + i, cols[colname], inplace=True)
    return None

  df_new = df.copy(deep=True)
  insert_cols(df_new, loc, cols, inplace=True)
  return df_new


# pylint: disable-next=invalid-name
def fill_col(df, col_loc, col_name, fill_value, inplace=False):
  """ insert a col filled with a constant value into a dataframe at the given location """
  if inplace:
    df.insert(col_loc, col_name, np.full(len(df), fill_value))
    return None

  df_new = df.copy(deep=True)
  fill_col(df_new, col_loc, col_name, fill_value, inplace=True)
  return df_new


# pylint: disable-next=invalid-name
def drop_col(df, col_name, inplace=False):
  """ drop out the given column from the dataframe """
  if inplace:
    df.pop(col_name)
    return None

  return df.drop([col_name], axis=1, inplace=False)


# pylint: disable-next=invalid-name
def drop_cols(df, cols, inplace=False):
  """ drop the given columns from the dataframe """
  if inplace:
    for col in cols:
      drop_col(df, col, inplace=True)
    return None

  for col in cols:
    df = drop_col(df, col, inplace=False)
  return df


# pylint: disable-next=invalid-name
def renumber_cols(df, start=0):
  """ if the column names are numbers, this will renumber the names in order """
  first_duplicate_index = len(df.columns)
  for i, col in enumerate(df.columns):
    if col in df.columns[0:i]:
      first_duplicate_index = i
      break

  dfA = df.iloc[:, :first_duplicate_index]  # pylint: disable=invalid-name

  end = start + len(dfA.columns)
  dfA = dfA.rename(columns=dict(zip(df, range(start, end))))  # pylint: disable=invalid-name

  if first_duplicate_index == len(df.columns):
    return dfA

  # pylint: disable-next=invalid-name
  dfB = renumber_cols(df.iloc[:, first_duplicate_index:],
                      start=len(dfA.columns))
  return pd.concat([dfA, dfB], axis=1)


# pylint: disable-next=invalid-name
def delete_redundant_cols(df,
                          masked_cols=None,
                          min_num_unique_entries=2,
                          inplace=False):
  """ remove columns with too many duplicate entries -- i.e, low information content """
  if masked_cols is None:
    masked_cols = []

  dropped_cols = []
  for _, col in enumerate(df):
    unique_entries = df[col].unique()
    if len(unique_entries) < min_num_unique_entries:
      if col in masked_cols:
        continue
      if inplace:
        drop_col(df, col, inplace=True)
        dropped_cols.append(col)
        # pylint: disable=consider-using-f-string; clearer
        logging.warning(
            'column %s dropped from dataframe: it had just %d unique entr%s' %
            (col, len(unique_entries),
             'y' if min_num_unique_entries == 2 else 'ies'))
        # pylint: enable=consider-using-f-string
      else:
        df = drop_col(df, col, inplace=False)
        dropped_cols.append(col)

  if inplace:
    return dropped_cols

  return df, dropped_cols


# pylint: disable-next=invalid-name
def encode_col(df, col, encoding=None, inplace=False):
  """ encode a column using the given encoding scheme """
  return encode_series(df[col], encoding, inplace)


def encode_series(series, encoding=None, inplace=False):
  """ encode a pandas series using the given encoding scheme """
  if encoding is None:
    unique_values = series.unique()
    encoding = get_map(unique_values)

  if inplace:
    series.replace(encoding, inplace=True)
    return encoding

  return series.replace(encoding), encoding


def map_series(series, mapping):
  """ map a pandas series using the given mapping """
  if isinstance(mapping, dict):
    return map_series(series, lambda x: mapping[x])

  return series.apply(mapping)


# pylint: disable-next=invalid-name
def unique(df, columns=None):
  """ figure out the unique entries in the given column/s of a dataframe """
  if columns is None:
    columns = df.columns
  unique_vals = []
  for col in columns:
    for val in df[col].unique():
      if val not in unique_vals:
        unique_vals.append(val)
  return unique_vals


# pylint: disable-next=invalid-name
def unique_combinations(df, columns=None):
  """ gives the unique combinations in the given column/s of a dataframe """

  def strip_off_index(iterrows):
    for _, row in iterrows:
      yield row

  if columns is None:
    columns = df.columns
  result = df[columns].drop_duplicates()
  result.reset_index(inplace=True, drop=True)
  return strip_off_index(result.iterrows())


# pylint: disable-next=invalid-name
def one_hot_encode(df, extra_tokens=None, my_map=None):
  """ one-hot encode a dataframe """
  if extra_tokens is None:
    extra_tokens = []

  if len(df.shape) > 2:
    raise NotImplementedError(
        'Can only one-hot encode 2D dataframes at the moment')

  if my_map is None:
    unique_vals = extra_tokens + unique(df)
    categorial_vectors = get_categorial_vectors(unique_vals)
  else:
    categorial_vectors = my_map

  # pylint: disable-next=invalid-name
  m, n, p = df.shape[0], df.shape[1], len(categorial_vectors.values()[0])
  one_hot_array = np.zeros((m, n, p))
  for j, col in enumerate(df):
    for i, item in enumerate(df[col]):
      one_hot_array[i, j, :] = categorial_vectors[item]

  return one_hot_array, categorial_vectors


# pylint: disable-next=invalid-name
def numericalize(df, extra_tokens=None, my_map=None):
  """ one-hot encode a dataframe as numeric values instead of vectors """
  if extra_tokens is None:
    extra_tokens = []

  if len(df.shape) > 2:
    raise NotImplementedError(
        'Can only numericalize 2D dataframes at the moment')

  if my_map is None:
    unique_vals = extra_tokens + unique(df)
    numeric_map = get_map(unique_vals)
  else:
    numeric_map = my_map

  numeric_array = np.zeros((df.shape[0], df.shape[1]))
  for j, col in enumerate(df):
    for i, item in enumerate(df[col]):
      numeric_array[i, j] = numeric_map[item]

  return numeric_array, numeric_map


# pylint: disable-next=invalid-name
def filter_duplicates(df, by, key_col, filename=None):
  """ remove rows where the entries in columns <by> have been repeated """
  by_cols = df.columns[by]
  new_df = df.sort_values(key_col, ascending=True)
  new_df.drop_duplicates(subset=by_cols, keep='first', inplace=True)

  if len(new_df) != len(df):
    n = str(len(df) - len(new_df))  # pylint: disable=invalid-name
    # pylint: disable-next=consider-using-f-string; clearer this way
    logging.info('%s duplicate entries filtered out%s' %
                 (n, f' from {filename}' if filename is not None else ''))
    logging.warning(
        ANSIFormats.bold(
            f"{len(n)*':'} duplicates were filtered "
            "out using an unstable algorithm. The order of the entries "
            "has likely changed."))
    return new_df

  return df


# pylint: disable-next=invalid-name
def to_0_1(df, axis=0):
  """ normalize a dataframe to have values in [0,1] """
  df_min = df.min(axis=axis)
  df_max = df.max(axis=axis)
  return (df - df_min) / (df_max - df_min)


# pylint: disable-next=invalid-name
def mean_var_normalize(df, axis=0):
  """ normalize a dataframe to have a mean of 0 and a std of 1 """
  df_mean = df.mean(axis=axis)
  df_std = df.std(axis=axis)
  return (df - df_mean) / df_std


# pylint: disable-next=invalid-name, unused-argument
def squeeze(df, axis=None):
  """ squeeze out redundant dimensions from a dataframe """
  if axis is not None:
    raise NotImplementedError('Only axis==None supported for now')
  return df.squeeze()


# pylint: disable-next=invalid-name
def as_long(df):
  """ cast a dataframe to long type values """
  return df.astype('int64')
