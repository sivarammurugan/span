"""Module for meta data about the recording."""

from future_builtins import map, zip

import numbers

from operator import attrgetter

from numpy import asanyarray, sign, repeat, arange, ones
from pandas import Series, DataFrame,  MultiIndex

from span.utils import ndtuples
from scipy.spatial.distance import squareform, pdist


def distance_map(nshanks, electrodes_per_shank, within_shank, between_shank,
                 metric='wminkowski', p=2.0):
    """Create an electrode distance map.

    Parameters
    ----------
    nshanks, electrodes_per_shank : int

    between_shank, within_shank : float

    metric : str, optional
        The distance measure to use to compute the distance between electrodes.

    p : number, optional
        See scipy.spatial.distance for more details here.

    Returns
    -------
    dists : DataFrame
        DataFrame of pairwise distances between electrodes.
    """
    assert nshanks >= 1, 'must have at least one shank'
    assert isinstance(nshanks, numbers.Integral), 'nshanks must be an integer'
    assert electrodes_per_shank >= 1, \
        'must have at least one electrode per shank'
    assert isinstance(electrodes_per_shank, numbers.Integral), \
        '"electrodes_per_shank" must be an integer'

    locs = ndtuples(electrodes_per_shank, nshanks)
    w = asanyarray((between_shank, within_shank), dtype=float)

    return squareform(pdist(locs, metric=metric, p=p, w=w))


class ElectrodeMap(DataFrame):
    """Encapsulate the geometry of the electrode map used in a recording.

    Parameters
    ----------
    map_ : array_like
        The electrode configuration.

    order : None or str, optional
        If there is a topography to the are that was recorded from, indicate here
        by "lm". Defaults to None.

    base_index : int, optional
        The number to start the channel indexing from. Defaults to 0 for ease of
        use in Python.

    Attributes
    ----------
    nshanks : int
        Number of shanks.

    nchans : int
        Total number of channels.
    """
    def __init__(self, map_, order=None, base_index=0):
        map_ = asanyarray(map_).squeeze()
        mm = map_.min()

        v = sign(base_index - mm)

        if v:
            while mm != base_index:
                map_ += v
                mm = map_.min()

        try:
            m, n = map_.shape
            s = repeat(arange(n), m)
        except ValueError:
            m, = map_.shape
            s = ones(m, dtype=int)

        data = {'channel': map_.ravel(), 'shank': s}

        if order is not None:
            assert map_.ndim == 2, 'map_ must be 2D if there is a shank order'
            tup = list(order)
            tup[0] += 'at'
            tup[1] += 'ed'
            data['side'] = repeat(tup, map_.size / len(order))

        df = DataFrame(data).sort('channel').reset_index(drop=True)
        df.index = df.pop('channel')

        super(ElectrodeMap, self).__init__(df.sort())

    @property
    def nshanks(self): return self.shank.nunique()

    @property
    def nchans(self): return self.index.unique().size

    def distance_map(self, within, between, metric='wminkowski', p=2.0):
        """Create a distance map from the current electrode configuration.

        Parameters
        ----------
        within, between : number
            `between_shank` is the distance between shanks and `within_shank` is
            the distance between electrodes on any given shank.

        metric : str, optional
            Metric to use to calculate the distance between electrodes/shanks.

        p : number, optional
            The $p$ of the norm to use. Defaults to 2 for weighted Euclidean
            distance.

        Returns
        -------
        df : DataFrame
            A dataframe with pairwise distances between electrodes, indexed by
            channel, shank, and side (if ordered).
        """
        assert isinstance(within, numbers.Real) and within > 0, \
            '"within" must be a positive real number'
        assert isinstance(between, numbers.Real) and between > 0, \
            '"between" must be a positive real number'
        assert isinstance(metric, basestring) or callable(metric), \
            '"metric" must be a callable object or a string'
        assert isinstance(p, numbers.Real) and p > 0, \
            'p must be a real number greater than 0'

        dm = distance_map(self.nshanks, self.shank.nunique(), within, between,
                          metric=metric, p=p)
        s = self.sort()
        cols = s.index, s.shank

        if hasattr(self, 'side'):
            cols += s.side,

        values_getter = attrgetter('values')
        cols = tuple(map(values_getter, cols))
        names = 'channel', 'shank', 'side'

        def _label_maker(i):
            return MultiIndex.from_arrays(cols,
                                          names=tuple(map(lambda x: x + ' %s' % i,
                                                          names)))

        index = _label_maker('i')
        columns = _label_maker('j')
        df = DataFrame(dm, index=index, columns=columns)

        nnames = len(names)
        ninds = 2
        nlevels = nnames * ninds

        reordering = tuple(reduce(lambda x, y: x + y, zip(xrange(nnames),
                                                     xrange(nnames, nlevels))))

        s = df.stack(0)

        for _ in xrange(nnames - 1):
            s = s.stack(0)

        s.name = r'$d\left(i, j\right)$'

        return s.reorder_levels(reordering)

    @property
    def flat(self):
        return

    @property
    def one_based(self):
        """Return an electrode configuration with 1 based indexing.

        This could be used for plotting.
        """
        values = self.values.copy().T
        index = Series(self.index.values + 1, name='channel')

        is_ordered = values.ndim == 2 and values.shape[0] == 2

        names = 'shank',

        if is_ordered:
            values[0] += 1
            names += 'side',
        else:
            values += 1

        return DataFrame(dict(zip(names, values)), index=index)
