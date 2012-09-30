from utils import (
    cast, detrend_linear, detrend_mean, detrend_none, dirsize, distance_map,
    electrode_distance, fractional, get_fft_funcs, group_indices, hascomplex,
    iscomplex, isvector, name2num, nans, ndlinspace, ndtuples, nextpow2,
    num2name, pad_larger, pad_larger2, remove_legend, cartesian, compose,
    composemap, trimmean)
from decorate import thunkify, cached_property
from span.utils._clear_refrac import clear_refrac
from span.utils._bin_data import bin_data
from span.utils.trimmean import trimmean
