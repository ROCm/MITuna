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
""" outlier detection methods """

import numpy as np


def is_outlier_v0(points, thresh=3.5):
  """ defines outliers based on the z-score """
  if len(points.shape) == 1:
    points = points[:, None]
  median = np.median(points, axis=0)
  diff = np.sum((points - median)**2, axis=-1)
  diff = np.sqrt(diff)
  med_abs_deviation = np.median(diff)

  modified_z_score = 0.6745 * diff / med_abs_deviation

  return modified_z_score > thresh


def is_outlier_v1(array, threshold=4, hard_limit=True):
  """ improvement on is_outlier_v2 with iterative outlier detection """
  array = array.copy()
  no_outliers = np.array([False for i in range(len(array))])
  all_outliers = no_outliers
  iter_outliers = [-1]
  while sum(iter_outliers) != 0:
    mean, std = array.mean(), array.std()
    iter_outliers = (array - mean) > threshold * std
    all_outliers = all_outliers | iter_outliers
    array[iter_outliers] = mean

  if hard_limit and (sum(all_outliers) > 1 / 10 * len(array)):
    # if the outliers make up more than 10% of the data, consider
    # them part of the data and not outliers
    return no_outliers

  return all_outliers


def is_outlier_v2(array, threshold=0.04, hard_limit=True):
  """ defines outliers as points <threshold> standard devs away from the mean """
  no_outliers = np.array([False for i in range(len(array))])
  potential_outliers = (array - array.mean()) > threshold * array.std()
  if hard_limit and (sum(potential_outliers) > 1 / 10 * len(array)):
    return no_outliers

  return potential_outliers


def is_outlier_v3(array, threshold=0.04, hard_limit=True):
  """ is_outlier_v2 with an improved hard_limit implementation """
  potential_outliers = (array - array.mean()) > threshold * array.std()
  if hard_limit and (sum(potential_outliers) > 1 / 10 * len(array)):
    return is_outlier_v3(array, threshold + 0.01, hard_limit)

  return potential_outliers


def is_outlier_v4(org_array, threshold=3, hard_limit=True):
  """ is_outlier_v1 with hard_limit implemented in the style of is_outlier_v3 """
  array = org_array.copy()
  no_outliers = np.array([False for i in range(len(array))])
  all_outliers = no_outliers
  iter_outliers = [-1]
  while sum(iter_outliers) != 0:
    mean, std = array.mean(), array.std()
    iter_outliers = (array - mean) > threshold * std
    all_outliers = all_outliers | iter_outliers
    array[iter_outliers] = mean

  if hard_limit and (sum(all_outliers) > 1 / 10 * len(array)):
    return is_outlier_v4(org_array, threshold + 0.01, hard_limit)

  return all_outliers
