import os
import types
import numbers
import unittest
import datetime
import warnings

import numpy as np
import pandas as pd

from six.moves import zip

from span.tdt.tank import (TdtTankBase, PandasTank, _python_read_tev_raw,
                           _create_ns_datetime_index, _reshape_spikes,
                           _raw_reader)
from span.tdt import SpikeDataFrame
from span.testing import slow, create_stsq
from span.utils import OrderedDict


class TestReadTev(object):
    def setUp(self):
        span_data_path = os.environ['SPAN_DATA_PATH']
        assert os.path.isdir(span_data_path)
        self.filename = os.path.join(span_data_path,
                                     'Spont_Spikes_091210_p17rat_s4_657umV')

        self.tank = PandasTank(self.filename)
        self.names = 'Spik', 'LFPs'

    def tearDown(self):
        del self.names, self.tank, self.filename

    def _reader_builder(self, reader):
        for name in self.names:
            tsq, _ = self.tank.tsq(name)

            with warnings.catch_warnings():
                warnings.simplefilter('ignore', FutureWarning)
                tsq.reset_index(drop=True, inplace=True)

            fp_locs = tsq.fp_loc

            assert np.dtype(np.int64) == fp_locs.dtype

            chunk_size = tsq.size.unique().max()

            spikes = np.empty((tsq.shape[0], chunk_size), np.float32)

            reader(self.filename + os.extsep + 'tev', fp_locs, chunk_size,
                   spikes)

            # mean should be at least on the order of millivolts if not less
            mag = np.log10(np.abs(spikes).mean())
            assert mag <= -3.0

    def test_read_tev(self):
        for reader in {_python_read_tev_raw, _raw_reader}:
            yield self._reader_builder, reader


def test_create_ns_datetime_index():
    start, fs, nsamples = datetime.datetime.now().date(), 103.342, 10
    index = _create_ns_datetime_index(start, fs, nsamples)
    assert isinstance(index, pd.DatetimeIndex)
    assert int(1e9 / fs) == index.freq.n
    assert index.size == nsamples


def test_reshape_spikes():
    meta = create_stsq(size=64, samples_per_channel=17)
    nblocks, block_size = meta.shape[0], meta.size[0]
    df = pd.DataFrame(np.empty((nblocks, block_size)))
    items = df.groupby(meta.channel.values).indices.items()
    items.sort()
    group_inds = np.column_stack(OrderedDict(items).itervalues())
    nchannels = group_inds.shape[1]
    nsamples = nblocks * block_size // nchannels
    reshaped = _reshape_spikes(df.values, group_inds)

    a, b = reshaped.shape, (nsamples, nchannels)
    print 'reshaped.shape == {0}'.format(a)
    print '(nsamples, nchannels) == {0}'.format(b)
    assert a == b


class TestTdtTankBase(unittest.TestCase):
    def test_init(self):
        self.assertRaises(TypeError, TdtTankBase, pd.util.testing.rands(10))


class TestPandasTank(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tankname = os.path.join(os.environ['SPAN_DATA_PATH'],
                                'Spont_Spikes_091210_p17rat_s4_657umV')
        cls.tank = PandasTank(tankname)

    @classmethod
    def tearDownClass(cls):
        del cls.tank

    def test_properties(self):
        names = ('fs', 'name', 'age', 'site', 'date', 'time', 'datetime',
                 'duration')
        typs = ((numbers.Real, np.floating), basestring,
                (numbers.Integral, np.integer),
                (numbers.Integral, np.integer), datetime.date, datetime.time,
                pd.datetime, np.timedelta64)

        for name, typ in zip(names, typs):
            self.assert_(hasattr(self.tank, name))
            self.assertIsInstance(getattr(self.tank, name),
                                  (types.NoneType, typ))

    def setUp(self):
        self.names = 'Spik', 'LFPs'

    def tearDown(self):
        del self.names

    def test_repr(self):
        r = repr(self.tank)
        self.assert_(r)

    @slow
    def test_read_tev(self):
        for name in self.names:
            tev = self.tank._read_tev(name)()
            self.assertIsNotNone(tev)
            self.assertIsInstance(tev, SpikeDataFrame)

    def test_read_tsq(self):
        for name in self.names:
            tsq, _ = self.tank._read_tsq(name)()
            self.assertIsNotNone(tsq)
            self.assertIsInstance(tsq, pd.DataFrame)

    def test_tsq(self):
        for name in self.names:
            self.assertIsNotNone(self.tank.tsq(name))

    def test_stsq(self):
        self.assertIsNotNone(self.tank.stsq)

    def test_ltsq(self):
        self.assertIsNotNone(self.tank.ltsq)

    @slow
    def test_tev(self):
        for name in self.names:
            self.assertIsNotNone(self.tank.tev(name))

    @slow
    def test_spikes(self):
        self.assertIsNotNone(self.tank.spikes)

    @slow
    def test_lfps(self):
        self.assertIsNotNone(self.tank.lfps)
