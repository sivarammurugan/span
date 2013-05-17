#!/usr/bin/env python

import sys
import os
import argparse
import numbers
import subprocess
import collections
import glob
import tarfile

import numpy as np
from numpy.random import rand
import pandas as pd

from scipy.io import savemat
from scipy.constants import golden as golden_ratio

from IPython import embed

from bottleneck import nanmax

from clint.textui import puts
from clint.textui.colored import red

from lxml.builder import ElementMaker
from lxml import etree

CHAR_BIT = 8


def hsv_to_rgb(h, s, v):
    hi = int(h * 6)
    f = h * 6 - hi
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    m = {0: (v, t, p), 1: (q, v, p), 2: (p, v, t), 3: (p, q, v), 4: (t, p, v),
         5: (v, p, q)}
    return '#{0:0>2x}{1:0>2x}{2:0>2x}'.format(*np.int64(256 * np.array(m[hi])))


def randcolor(h, s, v):
    if h is None:
        h = rand()
    h += golden_ratio - 1
    h %= 1
    return hsv_to_rgb(h, s, v)


def randcolors(ncolors, hue=None, saturation=0.99, value=0.99):
    colors = np.empty(ncolors, dtype=object)
    for i in xrange(ncolors):
        colors[i] = randcolor(hue, saturation, value)
    return colors


def error(msg):
    errmsg = os.path.basename(__file__)
    errmsg += ': error: {0}'.format(msg)
    puts(red(errmsg))
    return sys.exit(2)


def _get_fn(id_num_or_filename, db_path=os.environ.get('SPAN_DB_PATH', None)):
    if db_path is None:
        error('SPAN_DB_PATH environment variable not set, please set via '
              '"export SPAN_DB_PATH=\'path_to_the_span_database\'"')
    db_path = os.path.abspath(db_path)
    db = pd.read_csv(db_path)

    if isinstance(id_num_or_filename, numbers.Integral):
        if id_num_or_filename not in db.index:
            error('{0} is not a valid id number'.format(id_num_or_filename))
    elif isinstance(id_num_or_filename, basestring):
        if id_num_or_filename not in db.filename.values:
            error('{0} is not a valid filename'.format(id_num_or_filename))
        return id_num_or_filename
    return db.filename.ix[id_num_or_filename]


class SpanCommand(object):
    def _parse_filename_and_id(self, args):
        if args.filename is None and args.id is not None:
            self.filename = _get_fn(args.id)
        elif args.filename is not None and args.id is None:
            self.filename = _get_fn(args.filename)
        else:
            return error('Must pass a valid id number or filename')

        paths = glob.glob(self.filename + '*')
        common_prefix = os.path.commonprefix(paths)
        self.filename = common_prefix.strip(os.extsep)

        if not paths:
            return error('No paths match the expression '
                         '"{0}*"'.format(self.filename))

    def run(self, args):
        self._parse_filename_and_id(args)
        return self._run(args)

    def _run(self, args):
        raise NotImplementedError()

    def _load_data(self, return_tank=False):
        from span import TdtTank, NeuroNexusMap, ElectrodeMap
        em = ElectrodeMap(NeuroNexusMap.values, 50, 125)
        tank = TdtTank(os.path.normpath(self.filename), em)
        spikes = tank.spik

        if return_tank:
            return tank, spikes
        else:
            return spikes


class Analyzer(SpanCommand):
    pass


def _compute_xcorr(spikes, args):
    import span
    from span import spike_xcorr
    detrend = 'detrend_' + args.detrend
    thr = spikes.threshold(args.threshold)
    thr.clear_refrac(ms=args.refractory_period, inplace=True)
    binned = thr.bin(args.bin_size, how=args.bin_method)
    xc = spike_xcorr(binned, max_lags=args.max_lags,
                     scale_type=args.scale_type,
                     detrend=getattr(span, detrend), nan_auto=args.nan_auto)
    return xc


def _build_plot_filename(tank):
    raise NotImplementedError()


class CorrelationAnalyzer(Analyzer):
    def _run(self, args):
        tank, spikes = self._load_data(return_tank=True)
        xc = self._compute_xcorr(spikes, args)

        if args.display:
            plot_filename = _build_plot_filename(tank)
            self._display_xcorr(xc, plot_filename)

    def _display_xcorr(self, xc, plot_filename):
        pass


class IPythonAnalyzer(Analyzer):
    """Drop into an IPython shell given a filename or database id number"""
    def _run(self, args):
        tank, spikes = self._load_data(return_tank=True)
        embed()
        return 0


class BaseConverter(object):
    store_index = False

    def __init__(self, base_type, precision, date):
        self.base_type, self.precision = base_type, precision
        self.dtype = np.dtype(self.base_type + str(self.precision))
        self.date = date

    def split_data(self, raw):
        shank = raw.columns.get_level_values('shank').values
        channels = raw.columns.get_level_values('channel').values
        index = raw.index.values
        values = raw.values
        fs = raw.fs
        date = self.date
        elapsed = (raw.index.freq.n +
                   np.zeros(raw.nsamples)).cumsum().astype('m8[ns]')
        return locals()

    def convert(self, raw, outfile):
        if not self.store_index:
            raw.sortlevel('channel', axis=1, inplace=True)

        self._convert(raw, outfile)


class NeuroscopeConverter(BaseConverter):
    def _convert(self, raw, outfile):
        max_prec = float(2 ** (self.precision * CHAR_BIT - 1) - 1)
        const = max_prec / nanmax(np.abs(raw.values))
        xc = raw.values * const
        xc.astype(self.dtype).tofile(outfile)


class H5Converter(BaseConverter):
    store_index = True
    store_fs = True

    def _convert(self, raw, outfile):
        raw.to_hdf(outfile, 'raw')


class NumPyConverter(BaseConverter):
    store_index = True
    store_fs = True

    def _convert(self, raw, outfile):
        split = self.split_data(raw)
        values = split['values']

        if self.dtype != values.dtype:
            split['values'] = values.astype(self.dtype)

        np.savez(outfile, **split)


class MATLABConverter(BaseConverter):
    store_index = True
    store_fs = True

    def _convert(self, raw, outfile):
        savemat(outfile, self.split_data(raw))


_converters = {'neuroscope': NeuroscopeConverter, 'matlab': MATLABConverter,
               'h5': H5Converter, 'numpy': NumPyConverter}


class Converter(SpanCommand):
    def _run(self, args):
        spikes = self._load_data()
        converter = _converters[args.format](args.base_dtype, args.precision)
        converter.convert(spikes, args.outfile)


def _build_anatomical_description_element(index, E):
    anatomicalDescription = E.anatomicalDescription
    channelGroups = E.channelGroups
    group = E.group
    channel = E.channel
    groups = collections.defaultdict(list)
    for shank, channel in index:
        groups[shank].append(E.channel(str(channel)))
    items = groups.items()
    items.sort(key=lambda x: x[0])
    grouplist = []
    for gn, grp in items:
        grouplist.append(group(*grp))
    return anatomicalDescription(channelGroups(*grouplist))


def _build_spike_detection_element(index, E):
    spikeDetection = E.spikeDetection
    channelGroups = E.channelGroups
    group = E.group
    channel = E.channel
    groups = collections.defaultdict(list)
    for shank, channel in index:
        groups[shank].append(E.channel(str(channel), skip='0'))
    items = groups.items()
    items.sort(key=lambda x: x[0])
    grouplist = []
    for gn, grp in items:
        grouplist.append(group(*grp))
    return spikeDetection(channelGroups(*grouplist))


def _build_channels_element(index, E, colors):
    def _build_single_channel_color(channel, color):
        return E.channelColors(
            E.channel(channel),
            E.color(color),
            E.anatomyColor(color),
            E.spikeColor(color)
        )

    def _build_single_channel_offset(channel):
        return E.channelOffset(
            E.channel(channel),
            E.defaultOffset('0')
        )

    elements = []

    for shank, channel in index:
        c = str(channel)
        elements.append(_build_single_channel_color(c, colors[shank]))
        elements.append(_build_single_channel_offset(c))
    return E.channels(*elements)


def _make_neuroscope_xml(spikes, base, precision, voltage_range, amp, tarfile):
    E = ElementMaker()
    parameters = E.parameters
    acquisitionSystem = E.acquisitionSystem
    nBits = E.nBits
    nChannels = E.nChannels
    samplingRate = E.samplingRate
    voltageRange = E.voltageRange
    amplification = E.amplification
    offset = E.offset
    columns = spikes.columns
    colors = randcolors(columns.get_level_values('shank').unique().size)

    doc = parameters(
        acquisitionSystem(
            nBits(str(precision)),
            nChannels(str(spikes.nchannels)),
            samplingRate(str(int(spikes.fs))),
            voltageRange(str(voltage_range)),
            amplification(str(amp)),
            offset('0')
        ),

        E.fieldPotentials(
            E.lfpSamplingRate('1250')
        ),

        _build_anatomical_description_element(columns, E),
        _build_spike_detection_element(columns, E),

        E.neuroscope(
            E.miscellaneous(
                E.screenGain('0.2'),
                E.traceBackgroundImage()
            ),

            E.video(
                E.rotate('0'),
                E.flip('0'),
                E.videoImage(),
                E.positionsBackground('0')
            ),

            E.spikes(
                E.nsamples('72'),
                E.peakSampleIndex('36')
            ),

            _build_channels_element(columns, E, colors),
            version='1.3.3'
        ),
        creator='spanner.py',
        version='0.1'
    )

    filename = base + os.extsep + 'xml'

    with open(filename, 'w') as f:
        f.write(etree.tostring(doc, pretty_print=True))

    tarfile.add(filename)
    os.remove(filename)


def _make_neuroscope_nrs(spikes, base, start_time, window_size, tarfile):
    def _build_channel_positions():
        return (
            E.channelPosition(
                E.channel(
                    str(channel)
                ),
                E.gain('10'),
                E.offset('0')
            ) for channel in channels
        )
    E = ElementMaker()
    channels = spikes.columns.get_level_values('channel')

    doc = E.neuroscope(
        E.files(),
        E.displays(
            E.display(
                E.tabLabel('Field Potentials Display'),
                E.showLabels('0'),
                E.startTime(str(start_time)),
                E.duration(str(window_size)),
                E.multipleColumns('0'),
                E.greyScale('0'),
                E.positionView('0'),
                E.showEvents('0'),
                E.spikePresentation('0'),
                E.rasterHeight('33'),
                E.channelPositions(
                    *_build_channel_positions()
                ),
                E.channelsSelected(),
                E.channelsShown(
                    *(E.channel(str(channel)) for channel in channels)
                )
            )
        )
    )

    filename = base + os.extsep + 'nrs'

    with open(filename, 'w') as f:
        f.write(etree.tostring(doc, pretty_print=True))

    tarfile.add(filename)
    os.remove(filename)


def _build_neuroscope_package(spikes, converter, base, outfile, zipped_name,
                              args):
    tarfile_name = base + os.extsep + 'tar{0}{1}'.format(os.extsep,
                                                         args.format)
    with tarfile.open(tarfile_name, 'w:{0}'.format(args.format)) as f:
        converter.convert(spikes, outfile)
        f.add(outfile)
        os.remove(outfile)
        _make_neuroscope_xml(spikes, base, args.precision, args.voltage_range,
                             args.amplification, f)
        _make_neuroscope_nrs(spikes, base, args.start_time, args.window_size,
                             f)


def _get_dat_from_tarfile(tarfile):
    members = tarfile.getmembers()
    names = [member.name for member in members]
    for name, member in zip(names, members):
        if name.endswith('.dat'):
            return member
    else:
        return error('no DAT file found in neuroscope package. files found '
                     'were {1}'.format(names))


def _run_neuroscope(tarfile):
    member = _get_dat_from_tarfile(tarfile)
    tarfile.extractall()
    try:
        return subprocess.check_call(['neuroscope', os.path.join(os.curdir,
                                                                 member.name)])
    except OSError:
        return error('could not find neuroscope on the system path, it is '
                     'probably not '
                     'installed\n\nPATH={0}'.format(os.environ.get('PATH')))
    except subprocess.CalledProcessError as e:
        return error(e.msg)


# get the filename/id, convert to neuroscope with int16 precision, zip into
# package, unzip and show in neuroscope
class Viewer(SpanCommand):
    def _run(self, args):
        tank, spikes = self._load_data(return_tank=True)
        base, _ = os.path.splitext(self.filename)
        base = os.path.join(os.curdir, os.path.basename(base))
        outfile = '{base}{extsep}dat'.format(base=base, extsep=os.extsep)
        converter = _converters['neuroscope']('int', 16, tank.datetime)
        args.precision = converter.precision
        zipped_name = '{0}{1}tar{1}{2}'.format(base, os.extsep, args.format)
        _build_neuroscope_package(spikes, converter, base, outfile,
                                  zipped_name, args)
        with tarfile.open(zipped_name,
                          mode='r:{0}'.format(args.format)) as r_package:
            _run_neuroscope(r_package)


class Db(SpanCommand):
    pass


class DbCreator(Db):
    def _run(self, args):
        pass


class DbReader(Db):
    def _run(self, args):
        pass


class DbUpdater(Db):
    def _run(self, args):
        pass


class DbDeleter(Db):
    def _run(self, args):
        pass


def build_analyze_parser(subparsers):
    def build_correlation_parser(subparsers):
        parser = subparsers.add_parser('correlation', help='perform cross '
                                       'correlation analysis on a recording')
        add_filename_and_id_to_parser(parser)
        parser.add_argument('-c', '--remove-first-pc', action='store_true')
        parser.add_argument('-d', '--display', action='store_true')
        parser.add_argument('-t', '--threshold', type=float)
        parser.add_argument('-r', '--refractory-period', type=int, default=2)
        parser.add_argument('-b', '--bin-size', type=int)
        parser.add_argument('-p', '--bin-method', default='sum')
        parser.add_argument('-s', '--scale-type', choices=('normalize', 'none',
                                                           'biased',
                                                           'unbiased'),
                            default='normalize')
        parser.add_argument('-m', '--detrend', choices=('mean', 'linear',
                                                        'none'),
                            default='mean')
        parser.add_argument('-l', '--max-lags', type=int, default=1)
        parser.add_argument('-n', '--nan-auto', action='store_true',
                            default=True)
        parser.set_defaults(run=CorrelationAnalyzer().run)

    def build_ipython_parser(subparsers):
        parser = subparsers.add_parser('ipython', help='drop into an ipython '
                                       'shell')
        add_filename_and_id_to_parser(parser)
        parser.add_argument('-c', '--remove-first-pc', action='store_true')
        parser.set_defaults(run=IPythonAnalyzer().run)

    parser = subparsers.add_parser('analyze', help='perform an analysis on a '
                                   'TDT tank file')
    subparsers = parser.add_subparsers()
    build_correlation_parser(subparsers)
    build_ipython_parser(subparsers)


def build_convert_parser(subparsers):
    parser = subparsers.add_parser('convert', help='convert a TDT tank file '
                                   'into a different format')
    add_filename_and_id_to_parser(parser)
    parser.add_argument('-t', '--type',
                        help='the type of conversion you want to '
                        'perform', choices=('neuroscope', 'matlab', 'numpy',
                                            'h5'), required=True)
    parser.add_argument('-d', '--base-type',
                        help='the base numeric type to convert to',
                        default='float', choices=('float', 'int', 'uint', 'f',
                                                  'i', 'ui'), required=True)
    parser.add_argument('-p', '--precision', help='the number of bits '
                        'to use for conversion', type=int, default=64,
                        choices=(8, 16, 32, 64), required=True)
    parser.set_defaults(run=Converter().run)


def build_view_parser(subparsers):
    parser = subparsers.add_parser('view', help='display the raw traces of a '
                                   'TDT tank file in Neuroscope')
    add_filename_and_id_to_parser(parser)
    parser.add_argument('-s', '--start-time', type=int,
                        help='where to place you in the recording when showing'
                        ' the data')
    parser.add_argument('-w', '--window-size', type=int,
                        help='the number of milliseconds to show in the full '
                        'window')
    parser.add_argument('-r', '--voltage-range', type=int, default=10,
                        help='a magical parameter needed by neuroscope')
    parser.add_argument('-a', '--amplification', type=int, default=1000,
                        help='another magical parameter needed by neuroscope')
    parser.add_argument('-t', '--format', default='gz', help='the type of '
                        'archive in which to output a neuroscope-ready data '
                        'set')
    parser.set_defaults(run=Viewer().run)


def build_db_parser(subparsers):
    def _add_args_to_parser(parser):
        parser.add_argument('-a', '--age', type=int, help='the age of the '
                            'animal')
        parser.add_argument('-c', '--condition', help='the experimental '
                            'condition, if any')
        parser.add_argument('-w', '--weight', type=float, help='the weight '
                            'of the animal')
        parser.add_argument('-b', '--bad', action='store_true', help='Mark '
                            'a recording as "good"')

    def build_db_create_parser(subparsers):
        parser = subparsers.add_parser('create', help='put a new recording in '
                                       'the database')
        add_filename_and_id_to_parser(parser)
        _add_args_to_parser(parser)
        parser.set_defaults(run=DbCreator().run)

    def build_db_read_parser(subparsers):
        parser = subparsers.add_parser('read', help='query the properties of a'
                                       ' recording')
        add_filename_and_id_to_parser(parser)
        _add_args_to_parser(parser)
        parser.set_defaults(run=DbReader().run)

    def build_db_update_parser(subparsers):
        parser = subparsers.add_parser('update', help='update the properties '
                                       'of an existing recording')
        add_filename_and_id_to_parser(parser)
        _add_args_to_parser(parser)
        parser.set_defaults(run=DbUpdater().run)

    def build_db_delete_parser(subparsers):
        parser = subparsers.add_parser('delete', help='delete a recording or '
                                       'recordings matching certain '
                                       'conditions')
        add_filename_and_id_to_parser(parser)
        _add_args_to_parser(parser)
        parser.set_defaults(run=DbDeleter().run)

    parent_parser = subparsers.add_parser('db', help='Operate on the database '
                                          'of recordings', add_help=False)
    subparsers = parent_parser.add_subparsers(description='use the following '
                                              'subcomands to perform specific '
                                              'operations on the database of '
                                              'recordings')
    build_db_create_parser(subparsers)
    build_db_read_parser(subparsers)
    build_db_update_parser(subparsers)
    build_db_delete_parser(subparsers)


def add_filename_and_id_to_parser(parser):
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-f', '--filename',
                       help='The name of the file to read from')
    group.add_argument('-i', '--id', type=int, help='alternatively you can use'
                       ' a database id number of a recording if you know it '
                       '(you can query for these using spanner db read '
                       'args...')


def main():
    parser = argparse.ArgumentParser(description='Analyze TDT tank files')
    subparsers = parser.add_subparsers(help='Subcommands for analying TDT '
                                       'tank files')
    build_analyze_parser(subparsers)
    build_convert_parser(subparsers)
    build_view_parser(subparsers)
    build_db_parser(subparsers)
    args = parser.parse_args()
    return args.run(args)


if __name__ == '__main__':
    sys.exit(main())