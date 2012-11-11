import unittest
import itertools

import numpy as np
from numpy.random import randn, randint, rand
from numpy.testing import assert_allclose, assert_array_equal

from span.utils.math import *

from span.utils.test.test_utils import rand_int_tuple


class TestTrimmean(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.alphas = np.r_[:100]
        cls.includes = tuple(itertools.product((True, False), (True, False)))
        cls.axes = None, 0

    def test_number(self):
        x = float(randn())
        axes = self.axes
        arg_sets = itertools.product(self.alphas, self.includes, axes)
        for arg_set in arg_sets:
            alpha, include, axis = arg_set
            m = trimmean(x, alpha, include, axis)
            self.assertIsInstance(m, float)
            self.assertEqual(x, m)

    def test_0d_array(self):
        x = np.asanyarray(randn())
        axes = self.axes
        arg_sets = itertools.product(self.alphas, self.includes, axes)
        for arg_set in arg_sets:
            alpha, include, axis = arg_set
            m = trimmean(x, alpha, include, axis)
            self.assertIsInstance(m, float)
            self.assertEqual(x, m)

    def test_1d_array(self):
        x = randn(58)
        axes = self.axes
        arg_sets = itertools.product(self.alphas, self.includes, axes)
        for arg_set in arg_sets:
            alpha, include, axis = arg_set
            m = trimmean(x, alpha, include, axis)
            self.assertIsInstance(m, float)
            if isinstance(m, np.ndarray):
                self.assertEqual(m.dtype, float)

    def test_2d_array(self):
        x = randn(50, 13)
        axes = self.axes + (1,)
        arg_sets = itertools.product(self.alphas, self.includes, axes)
        for arg_set in arg_sets:
            alpha, include, axis = arg_set
            m = trimmean(x, alpha, include, axis)
            if axis is not None:
                self.assertEqual(m.ndim, x.ndim - 1)
            else:
                self.assertIsInstance(m, float)

    def test_3d_array(self):
        x = randn(10, 6, 4)
        axes = self.axes + (1, 2)
        arg_sets = itertools.product(self.alphas, self.includes, axes)
        for arg_set in arg_sets:
            alpha, include, axis = arg_set
            if axis is not None:
                self.assertRaises(Exception, trimmean, x, alpha, include, axis)
            else:
                m = trimmean(x, alpha, include, axis)
                self.assertIsInstance(m, float)

    def test_series(self):
        x = Series(randn(18))
        axes = self.axes
        arg_sets = itertools.product(self.alphas, self.includes, axes)
        for arg_set in arg_sets:
            alpha, include, axis = arg_set
            print alpha, include, axis
            if axis == 1:
                self.assertRaises(TypeError, trimmean, x, alpha, include, axis)

    def test_dataframe(self):
        x = DataFrame(randn(51, 17))
        axes = self.axes + (1,)
        arg_sets = itertools.product(self.alphas, self.includes, axes)
        for arg_set in arg_sets:
            alpha, include, axis = arg_set
            m = trimmean(x, alpha, include, axis)
            if axis is not None:
                self.assertEqual(m.ndim, x.ndim - 1)
            else:
                self.assertIsInstance(m, float)


class TestSem(unittest.TestCase):
    pass


def test_ndtuples():
    t = rand_int_tuple()
    k = ndtuples(*t)
    uk = np.unique(k.ravel())
    uk.sort()
    assert_array_equal(uk, np.arange(max(t)))


class TestDetrend(unittest.TestCase):
    def test_detrend_none(self):
        x = np.random.randn(10, 11)
        dtx = detrend_none(x)
        assert_array_equal(x, dtx)

    def test_detrend_mean(self):
        x = np.random.randn(10, 9)
        dtx = detrend_mean(x)
        expect = x - x.mean()
        self.assertEqual(expect.dtype, dtx.dtype)
        assert_array_equal(dtx, expect)
        assert_allclose(dtx.mean(), 0.0, atol=np.finfo(dtx.dtype).eps)

    def test_detrend_mean_dataframe(self):
        x = DataFrame(np.random.randn(10, 13))
        dtx = detrend_mean(x)
        m = dtx.mean()
        eps = np.finfo(float).eps
        assert_allclose(m.values.squeeze(), np.zeros(m.shape),
                        atol=eps)
        print m.values.squeeze().size

    def test_detrend_linear(self):
        n = 100
        x = np.random.randn(n)
        dtx = detrend_linear(x)
        eps = np.finfo(dtx.dtype).eps
        ord_mag = int(np.floor(np.log10(n)))
        rtol = 10.0 ** (1 - ord_mag) + (ord_mag - 1)
        assert_allclose(dtx.mean(), 0.0, rtol=rtol, atol=eps)
        assert_allclose(dtx.std(), 1.0, rtol=rtol, atol=eps)

    def test_detrend_linear_series(self):
        n = 100
        x = Series(np.random.randn(n))
        dtx = detrend_linear(x)
        m = dtx.mean()
        s = dtx.std()
        ord_mag = int(np.floor(np.log10(n)))
        rtol = 10.0 ** (1 - ord_mag) + (ord_mag - 1)
        eps = np.finfo(float).eps
        assert_allclose(m, 0.0, rtol=rtol, atol=eps)
        assert_allclose(s, 1.0, rtol=rtol, atol=eps)


class TestCartesian(unittest.TestCase):
    def test_cartesian(self):
        ncols = randint(2, 6)
        sizes = [randint(5, 10) for _ in xrange(ncols)]
        prod_arrays = map(randn, sizes)
        c = cartesian(prod_arrays)
        self.assertEqual(c.size, np.prod(sizes) * ncols)


def test_nextpow2():
    int_max = 100
    n = randint(int_max)
    np2 = nextpow2(n)
    tp2 = 2 ** np2
    assert tp2 >= n, '{0} < {1}'.format(tp2, n)
    assert_allclose(np2, np.log2(tp2))


def test_fractional():
    m, n = 100, 1
    x = randn(n)
    xi = randint(m)
    assert fractional(x)
    assert fractional(rand())
    assert not fractional(xi)
    assert not fractional(randint(1, np.iinfo(int).max))


def test_fs2ms():
    assert False


class TestCompose2(unittest.TestCase):
    def test_compose2(self):
        # fail if not both callables
        f, g = 1, 2
        self.assertRaises(TypeError, compose2, f, g)

        f, g = 1, np.exp
        self.assertRaises(TypeError, compose2, f, g)

        f, g = np.log, 2
        self.assertRaises(TypeError, compose2, f, g)

        # don't fail if both callables
        f, g = np.log, np.exp
        h = compose2(f, g)
        x = randn(10, 20)
        assert_allclose(x, h(x))


class TestCompose(unittest.TestCase):
    def test_compose(self):
        # fail if not both callables
        f, g, h, q = 1, 2, np.log, np.exp
        self.assertRaises(TypeError, compose, f, g, h, q)

        f, g, h, q = 1, np.exp, 1.0, 'sd'
        self.assertRaises(TypeError, compose, f, g, h, q)

        f, g, h, q = np.log, 2, object(), []
        self.assertRaises(TypeError, compose, f, g, h, q)

        # don't fail if all callables
        f, g, h, q = np.log, np.exp, np.log, np.exp
        h = compose(f, g, h, q)
        x = randn(10, 20)
        assert_allclose(x, h(x))


def test_composemap():
    f, g = np.log, np.exp
    x, y = randn(11), randn(10)
    xnew, ynew = composemap(f, g)((x, y))
    assert_allclose(x, xnew)
    assert_allclose(y, ynew)


class TestNdlinspace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ranges = randn(randint(5, 10), randint(10, 20)).tolist()

    def test_1elem(self):
        sizes = randint(5, 10)
        x = ndlinspace(self.ranges, sizes)

    def test_2elem(self):
        sizes = randint(5, 10, size=2)
        x = ndlinspace(self.ranges, *sizes.tolist())

    def test_3elem(self):
        sizes = randint(5, 10, size=3)
        x = ndlinspace(self.ranges, *sizes.tolist())