"""
Module for cross-/auto- correlation.
"""

from itertools import imap as map

import numpy as np
import pandas as pd

try:
    from pylab import detrend_none
except RuntimeError:
    detrend_none = lambda x: x

from span.utils import nextpow2, pad_larger, get_fft_funcs


def acorr(x, n):
    """Compute the autocorrelation of `x`

    Parameters
    ----------
    x : array_like
        Input array
    n : int
        Number of fft points

    Returns
    -------
    r : array_like
        The autocorrelation of `x`.
    """
    x = np.asanyarray(x)
    ifft, fft = get_fft_funcs(x)
    return ifft(np.absolute(fft(x, n)) ** 2.0, n)


def correlate(x, y, n):
    """Compute the cross correlation of `x` and `y`

    Parameters
    ----------
    x, y : array_like
    n : int

    Returns
    -------
    c : array_like
        Cross correlation of `x` and `y`
    """
    x, y = map(np.asanyarray, (x, y))
    ifft, fft = get_fft_funcs(x, y)
    return ifft(fft(x, n) * fft(y, n).conj(), n)


def matrixcorrelate(x):
    """Cross-correlation of the columns in a matrix
    
    Parameters
    ----------
    x : array_like
        The matrix from which to compute the cross correlations of each column
        with the others

    Returns
    -------
    c : array_like
        The 2 * maxlags - 1 by x.shape[1] ** 2 matrix of cross-correlations
    """
    raise NotImplementedError


def xcorr(x, y=None, maxlags=None, detrend=detrend_none, normalize=False,gs
          unbiased=False):
    """Compute the cross correlation of `x` and `y`.

    This function computes the cross correlation of `x` and `y`. It uses the
    equivalence of the cross correlation with the negative convolution computed
    using a FFT to achieve must faster cross correlation than is possible with
    the signal processing definition.

    By default it computes the raw cross-/autocorrelation.

    Note that it is not necessary for `x` and `y` to be the same size.

    Parameters
    ----------
    x : array_like
    y : array_like, optional
        If not given or is equal to `x`, the autocorrelation is computed.
    maxlags : int, optional
        The highest lag at which to compute the cross correlation.
    detrend : callable, optional
        A callable to detrend the data.
    normalize : bool, optional
    unbiased : bool, optional

    Returns
    -------
    c : pd.Series
    """
    x = detrend(np.asanyarray(x))
    
    if y is None or np.array_equal(x, y) or x is y:
        lsize = x.size
        corr_func = acorr
        ctmp = acorr(x, int(2 ** nextpow2(2 * lsize - 1)))
    else:
        x, y, lsize = pad_larger(x, detrend(np.asanyarray(y)))
        ctmp = correlate(x, y, int(2 ** nextpow2(2 * lsize - 1)))

    # no lags are given so use the entire xcorr
    if maxlags is None:
        maxlags = lsize

    # create the lags vector
    lags = np.r_[1 - maxlags:maxlags]

    # make sure the full xcorr is given (acorr is symmetric around 0)
    c = ctmp[lags]

    # normalize by the number of observations seen at each lag
    mlags = (lsize - np.absolute(lags)) if unbiased else 1.0

    # normalize by the product of the standard deviation of x and y
    stds = np.sqrt(x.dot(x) * y.dot(y)) if normalize else 1.0

    c /= stds * mlags
    return pd.Series(c, index=lags)
