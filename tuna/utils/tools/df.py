import re
import numpy as np
import pandas as pd
from collections import OrderedDict
# from sklearn.model_selection import train_test_split as sklearn_train_test_split

from tuna.utils import logging
from tuna.utils.ANSI_formatting import ANSIFormats
from tuna.utils.helpers import get_map, get_categorial_vectors, pretty_list


def to_pickle(df, filename):
  df.to_pickle(filename)


def from_pickle(filename):
  return pd.read_pickle(filename)


def to_csv(df, filename):
  df.to_csv(filename, index=False)


def read_csv(filename, **kwargs):
  return pd.read_csv(filename, **kwargs)


def read_noheader_csv(filename, **kwargs):
  kwargs['header'] = None
  return read_csv(filename, **kwargs)


def read_csv_as_float32(filename, **kwargs):
  kwargs['dtype'] = np.float32
  return read_csv(filename, **kwargs)


def read_noheader_csv_as_float32(filename, **kwargs):
  kwargs['header'] = None
  return read_csv_as_float32(filename, **kwargs)


def to_dict(series):
  return series.to_dict(OrderedDict)


def is_col_unique(df, col_name):
  if col_name not in df.columns:
    raise KeyError(f'{col_name} is not a column in the given dataframe')
  elif len(df) == 0:
    return True
  else:
    first_entry = df[col_name].iloc[0]
    return not (df[col_name] != first_entry).any()


def select_multiple(df, col_val_map, strict=False):
  if len(col_val_map) == 0:
    return df

  for i, (colname, value) in enumerate(col_val_map.items()):
    if i == 0:
      query = df[colname] == value
    else:
      query = query & (df[colname] == value)
  return df[query]


def select(df, colname, value, strict=False):
  sub_df = df[df[colname] == value]
  if len(sub_df) == 0:
    msg = f'{value} not present in {colname}. {colname} only contains {{' +\
        pretty_list( df[colname].unique(), max_items=10 ) + '}'
    if strict:
      raise ValueError(msg)
    else:
      logging.error(msg)

  return sub_df


def split(df, columns):
  if isinstance(columns, list):
    mask = df.columns.isin(columns)
  else:
    mask = df.columns == columns

  df1 = df.iloc[:, ~mask]
  df2 = df.iloc[:, mask]

  return df1, df2


def train_test_split(df, train_ratio, random=False, seed=None):
  if not random:
    train_size = int(len(df) * train_ratio)
    train = df.iloc[:train_size, :]
    test = df.iloc[train_size:, :]

  else:
    # train, test = sklearn_train_test_split(df,
    #                                        train_size=train_ratio,
    #                                        random_state=seed)
    raise NotImplemented('sklearn-based implementation has been commented out' +
                         'to avoid another dependency')

  return train, test


def combine(*dfs):
  return pd.concat(dfs, axis=1)


def extend(*dfs):
  return pd.concat(dfs, axis=0)


def insert_col(df, loc, col, inplace=False):
  if inplace:
    df.insert(loc, col.name, col)
  else:
    df_new = df.copy(deep=True)
    insert_col(df_new, loc, col, inplace=True)
    return df_new


def insert_cols(df, loc, cols, inplace=False):
  if inplace:
    for i, colname in enumerate(cols):
      insert_col(df, loc + i, cols[colname], inplace=True)
  else:
    df_new = df.copy(deep=True)
    insert_cols(df_new, loc, cols, inplace=True)
    return df_new


def fill_col(df, col_loc, col_name, fill_value, inplace=False):
  if inplace:
    df.insert(col_loc, col_name, np.full(len(df), fill_value))
  else:
    df_new = df.copy(deep=True)
    fill_col(df_new, col_loc, col_name, fill_value, inplace=True)
    return df_new


def drop_col(df, col_name, inplace=False):
  if inplace:
    df.pop(col_name)
  else:
    return df.drop([col_name], axis=1, inplace=False)


def drop_cols(df, cols, inplace=False):
  if inplace:
    for col in cols:
      drop_col(df, col, inplace=True)
  else:
    for col in cols:
      df = drop_col(df, col, inplace=False)
    return df


def renumber_cols(df, start=0):
  first_duplicate_index = len(df.columns)
  for i, col in enumerate(df.columns):
    if col in df.columns[0:i]:
      first_duplicate_index = i
      break

  dfA = df.iloc[:, :first_duplicate_index]

  end = start + len(dfA.columns)
  dfA = dfA.rename(
      columns={
          old_col_num: new_col_num
          for old_col_num, new_col_num in zip(df, range(start, end))
      })

  if first_duplicate_index == len(df.columns):
    return dfA
  else:
    dfB = renumber_cols(
        df.iloc[:, first_duplicate_index:], start=len(dfA.columns))
    return pd.concat([dfA, dfB], axis=1)


def delete_redundant_cols(df,
                          masked_cols=[],
                          min_num_unique_entries=2,
                          inplace=False):
  dropped_cols = []
  for i, col in enumerate(df):
    unique_entries = df[col].unique()
    if len(unique_entries) < min_num_unique_entries:
      if col in masked_cols:
        continue
      if inplace:
        drop_col(df, col, inplace=True)
        dropped_cols.append(col)
        logging.warning(
            'column %s dropped from dataframe: it had just %d unique entr%s' %
            (col, len(unique_entries), 'y'
             if min_num_unique_entries == 2 else 'ies'))
      else:
        df = drop_col(df, col, inplace=False)
        dropped_cols.append(col)

  if inplace:
    return dropped_cols
  else:
    return df, dropped_cols


def encode_col(df, col, encoding=None, inplace=False):
  return encode_series(df[col], encoding, inplace)


def encode_series(series, encoding=None, inplace=False):
  if encoding is None:
    unique_values = series.unique()
    encoding = get_map(unique_values)

  if inplace:
    series.replace(encoding, inplace=True)
    return encoding
  else:
    return series.replace(encoding), encoding


def map_series(series, mapping):
  if isinstance(mapping, dict):
    return map_series(series, lambda x: mapping[x])
  else:
    return series.apply(mapping)


def unique(df, columns=None):
  if columns is None:
    columns = df.columns
  unique_vals = []
  for col in columns:
    for val in df[col].unique():
      if val not in unique_vals:
        unique_vals.append(val)
  return unique_vals


def unique_combinations(df, columns=None):

  def strip_off_index(iterrows):
    for index, row in iterrows:
      yield row

  if columns is None:
    columns = df.columns
  result = df[columns].drop_duplicates()
  result.reset_index(inplace=True, drop=True)
  return strip_off_index(result.iterrows())


def one_hot_encode(df, extra_tokens=[], my_map=None):
  if len(df.shape) > 2:
    raise NotImplemented('Can only one-hot encode 2D dataframes at the moment')

  if my_map is None:
    unique_vals = extra_tokens + unique(df)
    categorial_vectors = get_categorial_vectors(unique_vals)
  else:
    categorial_vectors = my_map

  m, n, p = df.shape[0], df.shape[1], len(categorial_vectors.values()[0])
  one_hot_array = np.zeros((m, n, p))
  for j, col in enumerate(df):
    for i, item in enumerate(df[col]):
      one_hot_array[i, j, :] = categorial_vectors[item]

  return one_hot_array, categorial_vectors


def numericalize(df, extra_tokens=[], my_map=None):
  if len(df.shape) > 2:
    raise NotImplemented('Can only numericalize 2D dataframes at the moment')

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


def filter_duplicates(df, by, key_col, filename=None):
  by_cols = df.columns[by]
  new_df = df.sort_values(key_col, ascending=True)
  new_df.drop_duplicates(subset=by_cols, keep='first', inplace=True)

  if len(new_df) != len(df):
    n = str(len(df) - len(new_df))
    logging.info('%s duplicate entries filtered out%s' %
                 (n, f' from {filename}' if filename is not None else ''))
    logging.warning(ANSIFormats.bold("%s duplicates were filtered out using an unstable algorithm. "
                    % (len(n)*':') +\
                    "The order of the entries has likely changed."))
    return new_df

  else:
    return df


def to_0_1(df, axis=0):
  df_min = df.min(axis=axis)
  df_max = df.max(axis=axis)
  return (df - df_min) / (df_max - df_min)


def mean_var_normalize(df, axis=0):
  df_mean = df.mean(axis=axis)
  df_std = df.std(axis=axis)
  return (df - df_mean) / df_std


def squeeze(df, axis=None):
  return df.squeeze()


def as_long(df):
  return df.astype('int64')
