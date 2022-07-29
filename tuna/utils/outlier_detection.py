import numpy as np
from statistics import mean

def is_outlier_v0(points, thresh=3.5):
    if len(points.shape) == 1:
        points = points[:,None]
    median = np.median(points, axis=0)
    diff = np.sum((points - median)**2, axis=-1)
    diff = np.sqrt(diff)
    med_abs_deviation = np.median(diff)

    modified_z_score = 0.6745 * diff / med_abs_deviation

    return modified_z_score > thresh


def is_outlier_v1(array, threshold=4, hard_limit=True):
    array = array.copy()
    no_outliers = np.array([False for i in range(len(array))])
    all_outliers = no_outliers
    iter_outliers = [-1]
    while sum(iter_outliers) != 0:
        mean, std = array.mean(), array.std()
        iter_outliers = (array - mean) > threshold * std
        all_outliers = all_outliers | iter_outliers
        array[iter_outliers] = mean

    if hard_limit and (sum(all_outliers) > 1/10 * len(array)):
        # if the outliers make up more than 10% of the data, consider
        # them part of the data and not outliers
        return no_outliers
    else:
        return all_outliers


def is_outlier_v2(array, threshold=0.04, hard_limit=True):
    no_outliers = np.array([False for i in range(len(array))])
    potential_outliers = (array - array.mean()) > threshold * array.std()
    if hard_limit and (sum(potential_outliers) > 1/10 * len(array)):
        return no_outliers
    else:
        return potential_outliers


def is_outlier_v3(array, threshold=0.04, hard_limit=True):
    no_outliers = np.array([False for i in range(len(array))])
    potential_outliers = (array - array.mean()) > threshold * array.std()
    if hard_limit and (sum(potential_outliers) > 1/10 * len(array)):
        return is_outlier_v3(array, threshold+0.01, hard_limit)
    else:
        return potential_outliers


def is_outlier_v4(org_array, threshold=3, hard_limit=True):
    array = org_array.copy()
    no_outliers = np.array([False for i in range(len(array))])
    all_outliers = no_outliers
    iter_outliers = [-1]
    while sum(iter_outliers) != 0:
        mean, std = array.mean(), array.std()
        iter_outliers = (array - mean) > threshold * std
        all_outliers = all_outliers | iter_outliers
        array[iter_outliers] = mean

    if hard_limit and (sum(all_outliers) > 1/10 * len(array)):
        return is_outlier_v4(org_array, threshold+0.01, hard_limit)
    else:
        return all_outliers

