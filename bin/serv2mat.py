#!/usr/bin/env python

"""
"""

import os

try:
    from argparse import ArgumentParser
except ImportError:
    from optparse import OptionParser as ArgumentParser

import scipy.io
import span


def serv2mat(raw, output_filename, name='data'):
    """Wrapper for `scipy.io.savemat`.

    Parameters
    ----------
    raw : array_like
    output_filename : str
    name : str, optional
        Name of the array when loaded into MATLAB.
    """
    scipy.io.savemat(output_filename, {name: raw}, oned_as='row')


def parse_args():
    """Parse command line arguments."""
    parser = ArgumentParser(description='convert TDT to MATLAB')
    try:
        parser.add_argument('dirname', metavar='DIRNAME', type=str,
                            help='a directory name from the server')
    except AttributeError:
        pass

    try:
        _, args = parser.parse_args()
        args = args[0]
    except ValueError:
        args = parser.parse_args()
    return args

    
def main():
    # parse the arguments
    dn = parse_args()
    dnbn = os.path.basename(dn)
    mat_filename = os.path.join(dn, dnbn + os.extsep + 'mat')
    print '\nConverting TDT Tank to MATLAB: {0}'.format(mat_filename)
    
    # save to the current directory
    serv2mat(span.tdt.PandasTank(dn).spikes.raw, mat_filename)
    print 'Done!'


if __name__ == '__main__':
    main()     
