#!/usr/bin/env python

# utils.py ---

# Copyright (C) 2012 Copyright (C) 2012 Phillip Cloud <cpcloud@gmail.com>

# Author: Phillip Cloud <cpcloud@gmail.com>

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


"""A collection of utility functions."""

from future_builtins import map, zip

import os
import operator
import itertools as itools
import functools
import numbers

import numpy as np
from numpy.fft import fft, ifft, rfft, irfft
import pandas as pd

from pandas import DataFrame, datetime, MultiIndex

try:
    import numba
    from numba import autojit, NumbaError, void
except ImportError:
    NumbaError = Exception

from span.utils._clear_refrac import _clear_refrac as _clear_refrac_cython


fromtimestamp = np.vectorize(datetime.fromtimestamp)


def cast(a, dtype, copy=False):
    """Cast `a` to dtype `dtype`.

    Attempt to cast `a` to a different dtype `dtype` without copying.

    Parameters
    ----------
    a : array_like
        The array to cast.

    dtype : numpy.dtype
        The dtype to cast the input array to.

    copy : bool, optional
        Whether to copy the data given the previous arguments.

    Raises
    ------
    AssertionError

    Returns
    -------
    r : array_like
        The array `a` casted to type dtype

    See Also
    --------
    numpy.ndarray.astype
    """
    assert hasattr(a, 'dtype'), ('argument "a" of type {0} has no "dtype" '
                                 'attribute'.format(a.__class__))
    assert hasattr(a, 'astype'), ('argument "a" of type {0} has no "astype" '
                                 'method'.format(a.__class__))

    if a.dtype == dtype:
        return a

    try:
        r = a.astype(dtype, casting='safe', subok=True, copy=copy)
    except TypeError:
        r = a.astype(dtype)
    return r


def ndtuples(*dims):
    """Create an array of arrays with `dims` dimensions.

    Return an array of the Cartesisan product of each of
    np.arange(dims[0]), ..., np.arange(dims[1]).

    Parameters
    ----------
    dims : tuple of int
        A tuple of dimensions to use to create the arange of each element.

    Raises
    ------
    AssertionError
        If no arguments are given

    Returns
    -------
    cur : array_like

    See Also
    --------
    span.utils.math.cartesian
        `ndtuples` is a special case of the Cartesian product
    """
    assert dims, 'no arguments given'
    assert all(map(lambda x: isinstance(x, (numbers.Integral)), dims)), \
        'all arguments must be integers'
    assert all(map(lambda x: x > 0, dims)), 'all arguments must be greater than 0'

    dims = list(dims)
    n = dims.pop()
    cur = np.arange(n)[:, np.newaxis]

    while dims:
        d = dims.pop()
        cur = np.kron(np.ones((d, 1), int), cur)
        front = np.arange(d).repeat(n)[:, np.newaxis]
        cur = np.hstack((front, cur))
        n *= d

    return cur.squeeze()


def nans(shape):
    """Create an array of NaNs.

    Parameters
    ----------
    shape : tuple
        The shape tuple of the array of NaNs to create.

    Returns
    -------
    a : array_like
    """
    a = np.empty(shape, dtype=float)
    a.fill(np.nan)
    return a


def nans_like(a):
    """Returns an array of nans in the shape of `x` while preserving `a`'s
    type.

    This function also attempts to preserve the index and columns of a
    DataFrame or Series.

    Parameters
    ----------
    a : array_like
        Array whose shape will be used to create an array of nans

    Returns
    -------
    r : array_like
        A view of an array `a` of shape `a.shape` with type `type(a)`.
    """
    ns = nans(a.shape)

    if isinstance(a, pd.Series):
        r = pd.Series(ns, index=a.index)
    elif isinstance(a, pd.DataFrame):
        r = pd.DataFrame(ns, index=a.index, columns=a.columns)
    elif isinstance(a, pd.Panel):
        r = pd.Panel(ns, items=a.items, major_axis=a.major_axis,
                     minor_axis=a.minor_axis)
    else:
        r = ns.view(type=type(a))
    return r


def name2num(name, base=256):
    """Convert an event name's string representation to a number.

    Parameters
    ----------
    name : str
        The name of the event.

    base : int, optional
        The base to use to compute the numerical representation of `name`.

    Returns
    -------
    ret : int
        The number corresponding to TDT's numerical representation of an event
        type string.
    """
    return (base ** np.r_[:len(name)]).dot(tuple(map(ord, name)))


def pad_larger2(x, y):
    """Pad the larger of two arrays and the return the arrays and the size of
    the larger array.

    Parameters
    ----------
    x, y : array_like

    Returns
    -------
    x, y : array_like
    lsize : int
        The size of the larger of `x` and `y`.
    """
    xsize, ysize = x.size, y.size
    lsize = max(xsize, ysize)
    if xsize != ysize:
        size_diff = lsize - min(xsize, ysize)

        def _pad_func(a):
            return np.pad(a, (0, size_diff), mode='constant',
                          constant_values=(0,))

        if xsize > ysize:
            y = _pad_func(y)
        else:
            x = _pad_func(x)

    return x, y, lsize


def pad_larger(*arrays):
    """Pad the smallest of `n` arrays.

    Parameters
    ----------
    arrays : tuple of array_like

    Raises
    ------
    AssertionError

    Returns
    -------
    ret : tuple
        Tuple of zero padded arrays.
    """
    assert all(map(isinstance, arrays, itools.repeat(np.ndarray))), \
        ("all arguments must be instances of ndarray or implement the ndarray"
         " interface")
    if len(arrays) == 2:
        return pad_larger2(*arrays)

    sizes = np.fromiter(map(operator.attrgetter('size'), arrays), int)
    lsize = sizes.max()

    ret = []

    for array, size in zip(arrays, sizes):
        size_diff = lsize - size
        ret.append(np.pad(array, (0, size_diff), 'constant',
                          constant_values=(0,)))
    ret.append(lsize)

    return ret


def iscomplex(x):
    """Test whether `x` is any type of complex array.

    Parameters
    ----------
    x : array_like

    Returns
    -------
    r : bool
        Whether x's dtype is a sub dtype or equal to complex.
    """
    try:
        return np.issubdtype(x.dtype, np.complexfloating)
    except AttributeError:
        cfloat = np.complexfloating
        return any(map(np.issubdtype, x.dtypes, itools.repeat(cfloat)))


def hascomplex(x):
    """Check whether an array has all complex entries.

    Parameters
    ----------
    x : array_like

    Returns
    -------
    r : bool
        Whether xs dtype is complex and not all of the elements are el + 0j
    """
    try:
        v = x.imag
    except AttributeError:
        v = x.values.imag

    return iscomplex(x) and not np.logical_not(v).all()


def get_fft_funcs(*arrays):
    """Get the correct fft functions for the input type.

    Parameters
    ----------
    arrays : tuple of array_like
        Arrays to be checked for complex dtype.

    Returns
    -------
    r : tuple of callables
        The fft and ifft appropriate for the dtype of input.
    """
    return ifft, fft if any(map(iscomplex, arrays)) else irfft, rfft


def isvector(x):
    """Test whether `x` is a vector, i.e., ...

    Parameters
    ----------
    x : array_like

    Raises
    ------
    AssertionError

    Returns
    -------
    b : bool
    """
    return functools.reduce(operator.mul, x.shape) == max(x.shape)


def mi2df(mi):
    """Return a pandas MultiIndex as DataFrame.

    Parameters
    ----------
    mi : MultiIndex

    Returns
    -------
    df : DataFrame
    """
    assert isinstance(mi, MultiIndex), ('conversion not implemented for '
                                        'simple indices')

    def _type_converter(x):
        if not isinstance(x, basestring):
            return type(x)

        return 'S%i' % len(x)

    v = mi.values
    n = mi.names

    t = list(map(_type_converter, v[0]))  # strings are empty without this call
    dt = np.dtype(list(zip(n, t)))
    r = v.astype(dt)

    return DataFrame(r)


def nonzero_existing_file(f):
    """Return whether a file exists and is not size 0.

    Parameters
    ----------
    f : str

    Returns
    -------
    nef : bool

    Notes
    -----
    This doesn't perform as expected for temporary files. It returns False
    on ``os.path.getsize(f) > 0`` even if the file has just been written to.
    """
    return os.path.exists(f) and os.path.isfile(f) and os.path.getsize(f) > 0


def assert_nonzero_existing_file(f):
    assert nonzero_existing_file(f), ("%s does not exist or has a size of 0 "
                                      "bytes" % f)

try:
    B, I = map(numba.template, ('B', 'I'))

    @autojit(void(B[:, :], I))
    def _clear_refrac_numba(a, window):
        nsamples, nchannels = a.shape

        for channel in xrange(nchannels):
            sample = 0

            while sample + window < nsamples:
                if a[sample, channel]:
                    for i in xrange(sample + 1, sample + 1 + window):
                        a[i, channel] = False

                    sample += window

                sample += 1
except NameError:
    pass


def clear_refrac(a, window):
    """Clear the refractory period of a boolean array.

    Parameters
    ----------
    a : array_like
    window : npy_intp

    Notes
    -----
    If ``a.dtype == np.bool_`` in Python then this function will not work
    unless ``a.view(uint8)`` is passed.

    Raises
    ------
    AssertionError
    If `window` is less than or equal to 0
    """
    assert a is not None
    assert window > 0, '"window" must be greater than 0'

    try:
        _clear_refrac_numba(a, window)
    except (NameError, NumbaError):
        _clear_refrac_cython(a.view(np.uint8), window)
