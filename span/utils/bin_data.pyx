"""
"""

import numpy as np
cimport numpy as np
cimport cython
# from cython.parallel cimport parallel, prange

ctypedef np.uint8_t uint8


@cython.wraparound(False)
@cython.boundscheck(False)
cdef void _bin_data(np.ndarray[uint8, ndim=2, cast=True] a,
                    np.ndarray[long, ndim=1] bins,
                    np.ndarray[long, ndim=2] out):
    """Sum the counts of spikes in `a` in each of the bins.

    Parameters
    ----------
    a : array_like
    bins : array_like
    out : array_like
    """
    cdef:
        long i, j, k
        long nbins = bins.shape[0], n = out.shape[1]
        long* out_data = <long*> out.data
        long* bin_data = <long*> bins.data
        uint8* a_data = <uint8*> a.data

    for k in xrange(n):
        for i in xrange(nbins - 1):
            for j in xrange(bin_data[i], bin_data[i + 1]):
                out_data[i * n + k] += a_data[j * n + k]


@cython.wraparound(False)
@cython.boundscheck(False)
def bin_data(np.ndarray[uint8, ndim=2, cast=True] a not None,
             np.ndarray[long, ndim=1] bins not None):
    """Wrapper around bin_data._bin_data.

    Parameters
    ----------
    a, bins : array_like
        The array whose values to count up in the bins given by bins.
    out : array, optional
        An optional output array. If given then it is destructively updated and
        also returned.

    Returns
    -------
    out : array_like
        The binned data from `a`.
    """
    cdef np.ndarray[long, ndim=2] out = np.zeros((bins.shape[0] - 1, a.shape[1]),
                                                 dtype=np.long)
    _bin_data(a, bins, out)
    return out
