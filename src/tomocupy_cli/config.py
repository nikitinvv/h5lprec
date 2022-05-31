import os
import sys
import shutil
from copy import copy
from pathlib import Path
import argparse
import configparser
from collections import OrderedDict
import contextlib
import logging
import warnings
import inspect

import h5py
import numpy as np

from tomocupy_cli import utils
from tomocupy_cli import __version__


log = logging.getLogger(__name__)


def default_parameter(func, param):
    """Get the default value for a function parameter.
    
    For a given function *func*, introspect the function and return
    the default value for the function parameter named *param*.
    
    Return
    ======
    default_val
      The default value for the parameter.
    
    Raises
    ======
    RuntimeError
      Raised if the function *func* has no default value for the
      requested parameter *param*.
    
    """
    # Retrieve the function parameter by introspection
    try:
        sig = inspect.signature(func)
        _param = sig.parameters[param]
    except TypeError as e:
        warnings.warn(str(e))
        log.warning(str(e))
        return None
    # Check if a default value exists
    if _param.default is _param.empty:
        # No default is listed in the function, so throw an exception
        msg = ("No default value given for parameter *{}* of callable {}."
               "".format(param, func))
        raise RuntimeError(msg)
    else:
        # Retrieve and return the parameter's default value
        return _param.default


LOGS_HOME = Path.home()/'logs'
CONFIG_FILE_NAME = Path.home()/'tomocupyon.conf'

SECTIONS = OrderedDict()


SECTIONS['general'] = {
    'config': {
        'default': CONFIG_FILE_NAME,
        'type': str,
        'help': "File name of configuration file",
        'metavar': 'FILE'},
    'logs-home': {
        'default': LOGS_HOME,
        'type': str,
        'help': "Log file directory",
        'metavar': 'FILE'},
    'verbose': {
        'default': False,
        'help': 'Verbose output',
        'action': 'store_true'},
    'config-update': {
        'default': False,
        'help': 'When set, the content of the config file is updated using the current params values',
        'action': 'store_true'},
        }

SECTIONS['file-reading'] = {
    'file-name': {
        'default': '.',
        'type': Path,
        'help': "Name of the last used hdf file or directory containing multiple hdf files",
        'metavar': 'PATH'},
    'out-path-name': {
        'default': None,
        'type': Path,
        'help': "Path for output files",
        'metavar': 'PATH'},
    'file-type': {
        'default': 'standard',
        'type': str,
        'help': "Input file type",
        'choices': ['standard', 'double_fov']},        
    'binning': {
        'type': utils.positive_int,
        'default': 0,
        'help': "Reconstruction binning factor as power(2, choice)",
        'choices': [0, 1, 2, 3]},
    'blocked-views': {
        'default': False,
        'help': 'When set, the blocked-views options are used',
        'action': 'store_true'},    
    }


SECTIONS['blocked-views'] = {
    'blocked-views-start': {
        'type': float,
        'default': 0,
        'help': "Angle of the first blocked view"},
    'blocked-views-end': {
        'type': float,
        'default': 1,
        'help': "Angle of the last blocked view"},
        }
        
SECTIONS['remove-stripe'] = {
    'remove-stripe-method': {
        'default': 'none',
        'type': str,
        'help': "Remove stripe method: none, fourier-wavelet",
        'choices': ['none', 'fw']},
        }


SECTIONS['fw'] = {
    'fw-sigma': {
        'default': 1,
        'type': float,
        'help': "Fourier-Wavelet remove stripe damping parameter"},
    'fw-filter': {
        'default': 'sym16',
        'type': str,
        'help': "Fourier-Wavelet remove stripe filter",
        'choices': ['haar', 'db5', 'sym5', 'sym16']},
    'fw-level': {
        'type': utils.positive_int,
        'default': 7,
        'help': "Fourier-Wavelet remove stripe level parameter"},
    'fw-pad': {
        'default': True,
        'help': "When set, Fourier-Wavelet remove stripe extend the size of the sinogram by padding with zeros",
        'action': 'store_true'},
    }

SECTIONS['retrieve-phase'] = {
    'retrieve-phase-method': {
        'default': 'none',
        'type': str,
        'help': "Phase retrieval correction method",
        'choices': ['none', 'paganin']},
    'energy': {
        'default': 20,
        'type': float,
        'help': "X-ray energy [keV]"},
    'propagation-distance': {
        'default': 60,
        'type': float,
        'help': "Sample detector distance [mm]"},
    'pixel-size': {
        'default': 1.17,
        'type': float,
        'help': "Pixel size [microns]"},
    'retrieve-phase-alpha': {
        'default': 0.001,
        'type': float,
        'help': "Regularization parameter"},
    'retrieve-phase-pad': {
        'type': utils.positive_int,
        'default': 8,
        'help': "Padding with extra slices in z for phase-retrieval filtering"},
        }


SECTIONS['reconstruction'] = {
    'reconstruction-type': {
        'default': 'try',
        'type': str,
        'help': "Reconstruct full data set. ",
        'choices': ['full','try','check']},
    'reconstruction-algorithm': {
        'default': 'fourierrec',
        'type': str,
        'help': "Reconstruction algorithm",
        'choices': ['fourierrec', 'lprec']},    
    'rotation-axis': {
        'default': -1.0,
        'type': float,
        'help': "Location of rotation axis"},
    'center-search-width': {
        'type': float,
        'default': 10.0,
        'help': "+/- center search width (pixel). "},
    'center-search-step': {
        'type': float,
        'default': 0.5,
        'help': "+/- center search step (pixel). "},
    'nsino': {
        'default': 0.5,
        'type': float,
        'help': 'Location of the sinogram used for slice reconstruction and find axis (0 top, 1 bottom)'},
    'nsino-per-chunk': {     
        'type': int,
        'default': 8,
        'help': "Number of sinograms per chunk. Use larger numbers with computers with larger memory. ",},    
    'nproj-per-chunk': {     
        'type': int,
        'default': 8,
        'help': "Number of projections per chunk. Use larger numbers with computers with larger memory.  ",},    
    'start-row': {
        'type': int,
        'default': 0,
        'help': "Start slice"},
    'end-row': {
        'type': int,
        'default': -1,
        'help': "End slice"},
    'start-proj': {
        'type': int,
        'default': 0,
        'help': "Start projection"},
    'end-proj': {
        'type': int,
        'default': -1,
        'help': "End projection"},
    'nproj-per-chunk': {     
        'type': int,
        'default': 8,
        'help': "Number of sinograms per chunk. Use larger numbers with computers with larger memory.  Value <= 0 defaults to # of cpus.",},            
    'rotation-axis-auto': {
        'default': 'read_auto',
        'type': str,
        'help': "How to get rotation axis auto calculate ('auto'), or manually ('manual')",
        'choices': ['manual', 'auto',]},
    'rotation-axis-pairs': {
        'default': '[0,1499]',
        'type': str,
        'help': "Projection pairs to find rotation axis. Each second projection in a pair will be flipped and used to find shifts from the first element in a pair. The shifts are used to calculate the center.  Example [0,1499] for a 180 deg scan, or [0,1499,749,2249] for 360, etc.",},        
    'rotation-axis-sift-threshold': {
        'default': '0.5',
        'type': float,
        'help': "SIFT threshold for rotation search.",},        
    'dtype': {
        'default': 'float32',
        'type': str,
        'choices': ['float32', 'float16'],    
        'help': "Data type used for reconstruction. Note float16 works with power of 2 sizes.",},        
    'save-format': {
        'default': 'tiff',
        'type': str,
        'help': "Output format",
        'choices': ['tiff', 'h5']},     
    'gridrec-filter': {
        'default': 'parzen',
        'type': str,
        'help': "Filter for FBP reconstruction",
        'choices': ['shepp', 'parzen']},   
    'crop': {
        'type': int,
        'default': 0,
        'help': "Crop from each side of the slice"},
    'dezinger': {
        'type': int,
        'default': 0,
        'help': "Radius for removing outliers"},
    }


RECON_PARAMS = ('file-reading', 'remove-stripe',  'reconstruction', 'blocked-views', 'fw')
RECON_STEPS_PARAMS = ('file-reading', 'remove-stripe',  'reconstruction', 'blocked-views', 'retrieve-phase', 'fw')

NICE_NAMES = ('General', 'File reading', 'Remove stripe', 'Remove stripe FW', 'Retrieve phase', 'Blocked views', 'Reconstruction')

def get_config_name():
    """Get the command line --config option."""
    name = CONFIG_FILE_NAME
    for i, arg in enumerate(sys.argv):
        if arg.startswith('--config'):
            if arg == '--config':
                return sys.argv[i + 1]
            else:
                name = sys.argv[i].split('--config')[1]
                if name[0] == '=':
                    name = name[1:]
                return name

    return name


def parse_known_args(parser, subparser=False):
    """
    Parse arguments from file and then override by the ones specified on the
    command line. Use *parser* for parsing and is *subparser* is True take into
    account that there is a value on the command line specifying the subparser.
    """
    if len(sys.argv) > 1:
        subparser_value = [sys.argv[1]] if subparser else []
        config_values = config_to_list(config_name=get_config_name())
        values = subparser_value + config_values + sys.argv[1:]
    else:
        values = ""

    return parser.parse_known_args(values)[0]


def config_to_list(config_name=CONFIG_FILE_NAME):
    """
    Read arguments from config file and convert them to a list of keys and
    values as sys.argv does when they are specified on the command line.
    *config_name* is the file name of the config file.
    """
    result = []
    config = configparser.ConfigParser()

    if not config.read([config_name]):
        return []

    for section in SECTIONS:
        for name, opts in ((n, o) for n, o in SECTIONS[section].items() if config.has_option(section, n)):
            value = config.get(section, name)

            if value != '' and value != 'None':
                action = opts.get('action', None)

                if action == 'store_true' and value == 'True':
                    # Only the key is on the command line for this action
                    result.append('--{}'.format(name))

                if not action == 'store_true':
                    if opts.get('nargs', None) == '+':
                        result.append('--{}'.format(name))
                        result.extend((v.strip() for v in value.split(',')))
                    else:
                        result.append('--{}={}'.format(name, value))

    return result
   

class Params(object):
    def __init__(self, sections=()):
        self.sections = sections + ('general', )

    def add_parser_args(self, parser):
        for section in self.sections:
            for name in sorted(SECTIONS[section]):
                opts = SECTIONS[section][name]
                parser.add_argument('--{}'.format(name), **opts)

    def add_arguments(self, parser):
        self.add_parser_args(parser)
        return parser

    def get_defaults(self):
        parser = argparse.ArgumentParser()
        self.add_arguments(parser)

        return parser.parse_args('')

def write(config_file, args=None, sections=None):
    """
    Write *config_file* with values from *args* if they are specified,
    otherwise use the defaults. If *sections* are specified, write values from
    *args* only to those sections, use the defaults on the remaining ones.
    """
    config = configparser.ConfigParser()

    for section in SECTIONS:
        config.add_section(section)
        for name, opts in SECTIONS[section].items():
            if args and sections and section in sections and hasattr(args, name.replace('-', '_')):
                value = getattr(args, name.replace('-', '_'))

                if isinstance(value, list):
                    value = ', '.join(value)
            else:
                value = opts['default'] if opts['default'] is not None else ''

            prefix = '# ' if value == '' else ''

            if name != 'config':
                config.set(section, prefix + name, str(value))

    with open(config_file, 'w') as f:
        config.write(f)

def show_config(args):
    """Log all values set in the args namespace.
    Arguments are grouped according to their section and logged alphabetically
    using the DEBUG log level thus --verbose is required.
    """
    args = args.__dict__

    log.warning('tomocupy status start')
    for section, name in zip(SECTIONS, NICE_NAMES):
        entries = sorted((k for k in args.keys() if k.replace('_', '-') in SECTIONS[section]))
        if entries:
            for entry in entries:
                value = args[entry] if args[entry] != None else "-"
                log.info("  {:<16} {}".format(entry, value))

    log.warning('tomocupy status end')

def log_values(args):
    """Log all values set in the args namespace.
    Arguments are grouped according to their section and logged alphabetically
    using the DEBUG log level thus --verbose is required.
    """
    args = args.__dict__

    log.warning('tomocupyon status start')
    for section, name in zip(SECTIONS, NICE_NAMES):
        entries = sorted((k for k in args.keys() if k.replace('_', '-') in SECTIONS[section]))

        # print('log_values', section, name, entries)
        if entries:
            log.info(name)

            for entry in entries:
                value = args[entry] if args[entry] is not None else "-"
                if (value == 'none'):
                    log.warning("  {:<16} {}".format(entry, value))
                elif (value is not False):
                    log.info("  {:<16} {}".format(entry, value))
                elif (value is False):
                    log.warning("  {:<16} {}".format(entry, value))

    log.warning('tomocupyon status end')

def update_hdf_process(fname, args=None, sections=None):
    """
    Write in the hdf raw data file the content of *config_file* with values from *args* 
    if they are specified, otherwise use the defaults. If *sections* are specified, 
    write values from *args* only to those sections, use the defaults on the remaining ones.
    """
    if (args == None):
        log.warning("  *** Not saving log data to the HDF file.")

    else:
        with h5py.File(fname,'r+') as hdf_file:
            #If the group we will write to already exists, remove it
            if hdf_file.get('/process/tomocupy-cli-' + __version__):
                del(hdf_file['/process/tomocupy-cli-' + __version__])
            #dt = h5py.string_dtype(encoding='ascii')
            log.info("  *** tomopy.conf parameter written to /process%s in file %s " % (__version__, fname))
            config = configparser.ConfigParser()
            for section in SECTIONS:
                config.add_section(section)
                for name, opts in SECTIONS[section].items():
                    if args and sections and section in sections and hasattr(args, name.replace('-', '_')):
                        value = getattr(args, name.replace('-', '_'))
                        if isinstance(value, list):
                            # print(type(value), value)
                            value = ', '.join(value)
                    else:
                        value = opts['default'] if opts['default'] is not None else ''

                    prefix = '# ' if value == '' else ''

                    if name != 'config':
                        dataset = '/process' + '/tomocupy-cli-' + __version__ + '/' + section + '/'+ name
                        dset_length = len(str(value)) * 2 if len(str(value)) > 5 else 10
                        dt = 'S{0:d}'.format(dset_length)
                        hdf_file.require_dataset(dataset, shape=(1,), dtype=dt)
                        log.info(name + ': ' + str(value))
                        try:
                            hdf_file[dataset][0] = np.string_(str(value))
                        except TypeError:
                            log.error("Could not convert value {}".format(value))
                            raise