#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Feb 21 10:43:39 2018

@author: mints
Tool to prepare files for UniDAM.
UniDAM takes as an input a FITS file of a pre-defined structure.
This tool helps to prepare such files from user data.
Photometry is created automatically by cross-matching
with 2MASS and AllWISE. Gaia DR2 cross-match is also done
(this should be optional...).
If provided in config, galactic coordinates are taken from
input file, otherwise they are calculated.

An example of config file:
# List of column names to be kept in the output file
keep='GES', 'RAJ2000', 'DEJ2000', 'Teff', 'logg', '__Fe_H_'
[mapping]
# output column = input column or "!constant"
id=GES
T=Teff
logg=logg
feh=__Fe_H_
dT=!100
dlogg=!0.1
dfeh=!0.1
[galactic]
longitude=l
lattitude=b
"""
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
from future import standard_library
standard_library.install_aliases()
import os
import argparse
import numpy as np
from astropy import units as u
from astropy.table import Table, Column
from astropy.table import join as astropy_join
from astropy.coordinates import SkyCoord
from astropy.utils.exceptions import AstropyWarning
from astroquery.xmatch import XMatch
from configobj import ConfigObj
import healpy as hp
import warnings

warnings.filterwarnings('ignore', category=AstropyWarning)
warnings.filterwarnings('ignore', category=UserWarning)

parser = argparse.ArgumentParser(description="""
Tool to prepare files for UniDAM.
""", formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('-i', '--input', type=str, required=True,
                    help='Input filename')
parser.add_argument('-o', '--output', type=str, required=True,
                    help='Output filename')
parser.add_argument('-c', '--config', type=str, default='default.conf',
                    help='Config filename')
parser.add_argument('--ra', type=str, default=None,
                    help='RA column name')
parser.add_argument('--dec', type=str, default=None,
                    help='DEC column name')
parser.add_argument('-f', '--force', action="store_true",
                    default=False,
                    help='Overwrite output file if exists')
args = parser.parse_args()


data = Table.read(args.input)
config = ConfigObj(args.config)
if 'keep' in config:
    keep = config['keep'].split(',')
else:
    keep = []

if args.ra is None:
    ra = config['mapping']['ra']
else:
    ra = args.ra
if args.dec is None:
    dec = config['mapping']['dec']
else:
    dec = args.dec

for key, value in list(config['mapping'].items()):
    if '!' in value:
        colname, systematics = value.split('!')
        coldata = np.ones(len(data)) * float(systematics)
        if len(colname) > 0:
            coldata = np.sqrt(coldata**2 + data[colname]**2)
        data.add_column(Column(name=key,
                               data=coldata))
    elif value in data.colnames:
        if value != key:
            data.rename_column(value, key)
    else:
        raise ValueError('%s not in table' % value)
    print(f'Produced {key} from {value}')
    keep.append(key)
if 'galactic' in config:
    #import ipdb; ipdb.set_trace()
    data.rename_column(config['galactic']['longitude'], 'l')
    data.rename_column(config['galactic']['lattitude'], 'b')
else:
    data[args.ra].unit = u.degree
    data[args.dec].unit = u.degree
    c = SkyCoord(ra=data[ra], dec=data[dec], frame='icrs')
    data['l'] = c.galactic.l.degree
    data['b'] = c.galactic.b.degree
keep.extend(['l', 'b'])

print(keep)
data.keep_columns(set(keep))

def clean(table):
    for column in ['RAJ2000_2', 'DEJ2000_2', 'l_2', 'b_2']:
        if column in table.colnames:
            table.remove_column(column)

print('Adding extinction data')
data.add_column(Column(name='pix',
                       data=hp.ang2pix(512,
                                       data['l'], data['b'], lonlat=True)))
extinction_data = Table.read('/home/mints/data/extinction/lambda_sfd_ebv_Ak.fits')

data = astropy_join(data, extinction_data, keys=('pix'), join_type='left')

print('XMatching with 2MASS')
data = XMatch.query(cat1=data,
                    cat2='vizier:II/246/out',
                    max_distance=3 * u.arcsec,
                    colRA1=ra, colDec1=dec,
                    responseformat='votable',
                    selection='best')
data.remove_columns(['angDist',
                     'errHalfMaj', 'errHalfMin', 'errPosAng',
                     'X', 'MeasureJD'])
clean(data)
print('XMatching with AllWISE')
data = XMatch.query(cat1=data,
                    cat2='vizier:II/328/allwise',
                    max_distance=3 * u.arcsec,
                    colRA1=ra, colDec1=dec,
                    responseformat='votable',
                    selection='best')
bad_col = ['%smag_2' % b for b in 'JHK'] + ['e_%smag_2' % b for b in 'JHK']
clean(data)
data.remove_columns(['angDist',
                     'eeMaj', 'eeMin', 'eePA',
                     'W3mag', 'W4mag',
                     'e_W3mag', 'e_W4mag',
                     'pmRA', 'e_pmRA', 'pmDE', 'e_pmDE', 'ID', 'd2M'] +
                    bad_col)
# TODO: make this an option.
print('XMatching with Gaia')
data = XMatch.query(cat1=data,
                    cat2='vizier:I/345/gaia2',
                    max_distance=3 * u.arcsec,
                    colRA1=args.ra, colDec1=args.dec,
                    responseformat='votable',
                    selection='best')
data.remove_columns(['ra_ep2000', 'dec_ep2000',
                     'errHalfMaj', 'errHalfMin', 'errPosAng',
                     'ra', 'dec', 'source_id', 'ref_epoch',
                     'ra_error', 'dec_error',
                     'pmra', 'pmra_error', 'pmdec', 'pmdec_error',
                     'ra_dec_corr', 'duplicated_source',
                     'phot_variable_flag'])
clean(data)
data['parallax'] *= 1e-3
data['parallax_error'] *= 1e-3
if args.force and os.path.exists(args.output):
    os.remove(args.output)
data.write(args.output)
