#!/usr/bin/env python

# spikedataframe.py ---

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


"""
Examples
--------
>>> import span
>>> tank = span.tdt.PandasTank('some/tank/file/folder')
>>> sp = tank.spikes
>>> assert isinstance(sp, span.tdt.SpikeDataFrame)
"""

import numbers
import types
import functools as fntools

import numpy as np

from pandas import Series, DataFrame, MultiIndex

import span
from span.xcorr import xcorr
from span.utils import sem, samples_per_ms, clear_refrac, ndtuples


class SpikeDataFrameBase(DataFrame):
    """Base class implementing basic spike data set properties and methods.

    Parameters
    ----------
    data : array_like
        The raw spike data.

    meta : array_like
        The DataFrame of TSQ header file metadata.

    args : tuple
        Arguments to base class constructor.

    kwargs : dict
        Arguments to base class constructor.

    Attributes
    ----------
    fs (float) : Sampling rate
    nchannels (int) : Number of channels
    nsamples (int) : Number of samples per channel

    See Also
    --------
    span.tdt.spikedataframe.SpikeDataFrame
    """

    __slots__ = 'meta', 'date'

    def __init__(self, *args, **kwargs):
        super(SpikeDataFrameBase, self).__init__(*args, **kwargs)

    def sem(self, axis=0, ddof=1):
        r"""Return the standard error of the mean of array along `axis`.

        Parameters
        ----------
        axis : int, optional
            The axis along which to compute the standard error of the mean.

        ddof : int, optional
            Delta degrees of freedom. 0 computes the sem using the population
            standard deviation, 1 computes the sem using the sample standard
            deviation.

        Returns
        -------
        sem : Series
            The standard error of the mean of the object along `axis`.

        Notes
        -----
        The standard error of the mean is defined as:

        .. math::

           \operatorname{sem}\left(\mathbf{x}\right)=\sqrt{\frac{\frac{1}{n -
           \textrm{ddof}}\sum_{i=1}^{n}\left(x_{i} -
           \bar{\mathbf{x}}\right)^{2}}{n}}

        where :math:`n` is the number of elements along the axis `axis`.
        """
        return self.apply(sem, axis=axis, ddof=ddof)

    @property
    def nchannels(self):
        return self.shape[1]

    @property
    def nsamples(self):
        return self.shape[0]

    @property
    def fs(self):
        return 1e9 / self.index.freq.n

    def threshold(self, threshes):
        """Threshold spikes.

        Parameters
        ----------
        threshes : array_like

        Raises
        ------
        AssertionError
            * If `threshes` is not a scalar or a vector of length equal to the
              number of channels.

        Returns
        -------
        threshed : array_like
        """
        if np.isscalar(threshes):
            threshes = np.repeat(threshes, self.nchannels)

        assert threshes.size == 1 or threshes.size == self.nchannels, \
            'number of threshold values must be 1 (same for all channels) or '\
            '{0}, different threshold for each channel'.format(self.nchannels)

        is_neg = np.all(threshes < 0)
        cmpf = self.lt if is_neg else self.gt

        thr = threshes.item() if threshes.size == 1 else threshes
        threshes = Series(thr, index=self.columns)

        f = fntools.partial(cmpf, axis=1)

        return f(threshes)


class SpikeDataFrame(SpikeDataFrameBase):
    """Class encapsulting a Pandas DataFrame with extensions for analyzing
    spike train data.

    See the :class:`SpikeDataFrameBase` documentation for constructor details.
    """

    def __init__(self, *args, **kwargs):
        super(SpikeDataFrame, self).__init__(*args, **kwargs)

    @property
    def _constructor(self):
        return type(self)

    def clear_refrac(self, threshed, ms=2):
        """Remove spikes from the refractory period of all channels.

        Parameters
        ----------
        threshed : array_like
            Array of ones and zeros.

        ms : float, optional, default 2
            The length of the refractory period in milliseconds.

        Raises
        ------
        AssertionError
            * If `ms` is not an instance of the ADT ``numbers.Integral``.
            * If `ms` is less than 0 or is not ``None``.

        Returns
        -------
        r : SpikeDataFrame
            The thresholded and refractory-period-cleared array of booleans
            indicating the sample point at which a spike was above threshold.
        """
        assert isinstance(ms, (numbers.Integral, types.NoneType)), \
            '"ms" must be an integer or None'
        assert ms >= 0 or ms is None, \
            'refractory period must be a nonnegative integer or None'

        clr = threshed

        if ms:
            # copy so we don't write over the values of threshed
            clr = threshed.copy()

            # get the number of samples in ms milliseconds
            ms_fs = samples_per_ms(self.fs, ms)
            clear_refrac(clr.values, ms_fs)

        return clr

    def xcorr(self, binned, maxlags=None, detrend=span.utils.detrend_mean,
              scale_type='normalize', sortlevel='shank i', nan_auto=False,
              lag_name='lag'):
        """Compute the cross correlation of binned data.

        Parameters
        ----------
        binned : array_like
            Data of which to compute the cross-correlation.

        maxlags : int, optional
            Maximum number of lags to return from the cross correlation.
            Defaults to None and computes the full cross correlation.

        detrend : callable, optional
            Callable used to detrend. Defaults to
            :func:`span.utils.detrend_mean`.

        scale_type : str, optional
            Method of scaling. Defaults to ``'normalize'``.

        sortlevel : str, optional
            How to sort the index of the returned cross-correlation.
            Defaults to "shank i" so the the xcorrs are ordered by their
            physical ordering.

        nan_auto : bool, optional
            If ``True`` then the autocorrelation values will be ``NaN``.
            Defaults to ``False``.

        lag_name : str, optional
            Name to give to the lag index for plotting. Defaults to
            ``r'$\ell$'``.

        Raises
        ------
        AssertionError
           * If detrend is not a callable object
           * If scale_type is not a string or is not None

        ValueError
           * If sortlevel is not ``None`` and is not a string or a number in
             the list of level names or level indices.

        Returns
        -------
        xc : DataFrame or Series
            The cross correlation of all the columns of the data.

        See Also
        --------
        span.xcorr.xcorr
            General cross correlation function.

        SpikeDataFrame.bin
            Binning function.

        SpikeDataFrame.clear_refrac
            Clear the refractory period of a channel or array of channels.
        """
        assert callable(detrend), 'detrend must be a callable class or '\
            'function'
        assert isinstance(scale_type, basestring) or scale_type is None, \
            'scale_type must be a string or None'

        xc = xcorr(binned, maxlags=maxlags, detrend=detrend,
                   scale_type=scale_type)

        xc.columns = _create_xcorr_inds(binned)

        if nan_auto:
            # slight hack for channel names
            xc0 = xc.ix[0]
            names = xc0.index.names
            chi_ind = names.index('channel i')
            chj_ind = names.index('channel j')

            select_func = lambda x: x[chi_ind] == x[chj_ind]
            xc.ix[0, xc0.select(select_func).index] = np.nan

        if sortlevel is not None:
            fmt_str = 'sortlevel {0} not in {1}'
            cols = xc.columns

            try:
                sl = int(sortlevel)
                nlevels = cols.nlevels
                assert 0 <= sl < nlevels, fmt_str.format(sl, range(nlevels))
            except (ValueError, AssertionError):
                try:
                    sl = str(sortlevel)
                    names = cols.names
                    assert sl in names, fmt_str.format(sl, names)
                except (ValueError, AssertionError):
                    raise ValueError('sortlevel must be an int or a string')

            xc = xc.sortlevel(level=sl, axis=1)

        xc.index.name = lag_name

        return xc


# TODO: hack to make it so nans are allowed when creating indices
def _create_xcorr_inds(binned):
    from span.tdt.spikeglobals import Indexer

    raw_inds = span.utils.mi2df(binned.columns)

    channels = raw_inds.channel.values.ravel()
    channeli, channelj = span.utils.cartesian((channels, channels)).T

    ind = Indexer.sort('channel').reset_index(drop=True)
    indv = ind.values
    inds = np.hstack((indv.take(channeli, axis=0)[:, ::-1],
                      indv.take(channelj, axis=0)[:, ::-1]))

    names = 'shank i', 'channel i', 'shank j', 'channel j'
    return MultiIndex.from_arrays(inds.values.T, names=names)
