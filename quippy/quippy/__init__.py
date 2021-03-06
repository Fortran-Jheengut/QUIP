# HQ XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
# HQ X
# HQ X   quippy: Python interface to QUIP atomistic simulation library
# HQ X
# HQ X   Copyright James Kermode 2010
# HQ X
# HQ X   These portions of the source code are released under the GNU General
# HQ X   Public License, version 2, http://www.gnu.org/copyleft/gpl.html
# HQ X
# HQ X   If you would like to license the source code under different terms,
# HQ X   please contact James Kermode, james.kermode@gmail.com
# HQ X
# HQ X   When using this software, please cite the following reference:
# HQ X
# HQ X   http://www.jrkermode.co.uk/quippy
# HQ X
# HQ XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

"""quippy package

James Kermode <james.kermode@kcl.ac.uk>

Contains python bindings to the libAtoms/QUIP Fortran 95 codes
<http://www.libatoms.org>. """

import sys
assert sys.version_info >= (2,4,0)

import atexit, os, numpy, logging
from ConfigParser import ConfigParser

# Read ${HOME}/.quippyrc config file if it exists
cfg = ConfigParser()
quippyrc = os.path.join(os.environ['HOME'],'.quippyrc')
if os.path.exists(quippyrc):
    cfg.read(quippyrc)

# Read config file given in ${QUIPPY_CFG} if it exists
if 'QUIPPY_CFG' in os.environ and os.path.exists(os.environ['QUIPPY_CFG']):
    cfg.read(os.environ['QUIPPY_CFG'])

_fortran_indexing = True

def set_fortran_indexing(fortran_indexing):
    """
    Global setting for ``fortran_indexing``.

    Set to ``True`` to use 1-based indices on all arrays using the
    :class:`~quippy.farray.FortranArray` wrapper class or ``False`` to
    use conventional numpy 0-based array indexing. Default setting is
    ``True``, but can be overridden in the ``~/.quippprc`` config
    file.
    """
    global _fortran_indexing
    _fortran_indexing = fortran_indexing

def get_fortran_indexing():
    """
    Return the current ``fortran_indexing`` global setting.

    ``True`` for 1-based indexing; ``False`` for 0-based indexing.
    """
    global _fortran_indexing
    return _fortran_indexing

if 'general' in cfg.sections():
    if 'fortran_indexing' in cfg.options('general'):
        set_fortran_indexing(bool(cfg.get('general', 'fortran_indexing')))

if 'logging' in cfg.sections():
    if 'level' in cfg.options('logging'):
        logging.root.setLevel(getattr(logging, cfg.get('logging', 'level')))

disabled_modules = []
if 'modules' in cfg.sections():
    for name, value in cfg.items('modules'):
        if not int(value):
            disabled_modules.append(name)

# External dependencies
available_modules = []
unavailable_modules = []

for mod in ['netCDF4', 'scipy', 'ase', 'atomeye', 'enthought.mayavi', 'phonopy']:
    if mod in disabled_modules: continue
    try:
        __import__(mod)
        available_modules.append(mod)
    except ImportError:
        unavailable_modules.append(mod)

logging.debug('disabled_modules %r' % disabled_modules)
logging.debug('available_modules %r' % available_modules)
logging.debug('unavailable_modules %r' % unavailable_modules)

if 'netCDF4' in available_modules:
    from netCDF4 import Dataset
    netcdf_file = Dataset
else:
    from quippy.pupynere import netcdf_file

# if _quippy.so is dynamically linked with openmpi, we need to change dlopen() flags before importing it
if ('openmpi' in cfg.sections() and 'dynamic' in cfg.options['openmpi']) or \
       ('QUIP_ARCH' in os.environ and os.environ['QUIP_ARCH'].endswith('openmpi')):
    try:
        # Python 2.5 or newer
        from ctypes import RTLD_GLOBAL
    except ImportError:
        # Python 2.4
        from dl import RTLD_GLOBAL
    flags = sys.getdlopenflags()
    sys.setdlopenflags(flags | RTLD_GLOBAL)
    available_modules.append('mpi')

try:
    import _quippy
except ImportError as err:
    raise ImportError(err.message +
                    " - perhaps you are trying to import quippy from the source directory?")

# Reference values of .true. and .false. from Fortran
QUIPPY_TRUE = _quippy.qp_reference_true()
QUIPPY_FALSE = _quippy.qp_reference_false()

from oo_fortran import FortranDerivedType, FortranDerivedTypes, FortranRoutines, fortran_class_prefix, wrap_all

# Read spec file generated by f90doc and construct wrappers for classes
# and routines found therein.

def quippy_cleanup():
    try:
        _quippy.qp_verbosity_pop()
        _quippy.qp_system_finalise()
    except AttributeError:
        pass

_quippy.qp_system_initialise(-1, qp_quippy_running=QUIPPY_TRUE)
_quippy.qp_verbosity_push(0)
atexit.register(quippy_cleanup)

from spec import spec

QUIP_ROOT = spec['quip_root']
QUIP_ARCH = spec['quip_arch']
QUIP_MAKEFILE = spec['quip_makefile']

if 'netcdf' in disabled_modules:
    disabled_modules.append('netcdf')
else:
    if 'HAVE_NETCDF' in QUIP_MAKEFILE and QUIP_MAKEFILE['HAVE_NETCDF'] == 1:
        available_modules.append('netcdf')
    else:
        unavailable_modules.append('netcdf')

__all__ = ['QUIP_ROOT', 'QUIP_ARCH', 'QUIP_MAKEFILE',
           'available_modules', 'unavailable_modules',
           'disabled_modules',
           'set_fortran_indexing', 'get_fortran_indexing']

wrap_modules = spec['wrap_modules']

mod_names = [ modname for (modname, modfile) in spec['wrap_modules'] ]
mod_files = [ modfile for (modname, modfile) in spec['wrap_modules'] ]

# Jointly wrap atoms_types, atoms and connection into the respective classes

atoms_types_file = mod_files[mod_names.index('atoms_types')]

del mod_files[mod_names.index('atoms_types')]
del mod_names[mod_names.index('atoms_types')]

del mod_files[mod_names.index('atoms')]
del mod_names[mod_names.index('atoms')]

del mod_files[mod_names.index('connection')]
del mod_names[mod_names.index('connection')]

del mod_files[mod_names.index('domaindecomposition')]
del mod_names[mod_names.index('domaindecomposition')]

merge_modules = {'atoms': ('atoms_types', 'atoms', 'connection', 'domaindecomposition')}

wrap_modules = zip(mod_names, mod_files)
wrap_modules.append(('atoms', atoms_types_file))

mod_names = [ modname for (modname, modfile) in spec['wrap_modules'] ]
mod_files = [ modfile for (modname, modfile) in spec['wrap_modules'] ]


# List of Fortran modules which have Python wrappers in this package
python_wrappers = ['periodictable', 'table', 'potential',
                   'dictionary', 'dynamicalsystem', 'cinoutput', 'atoms',
                   'extendable_str', 'structures', 'elasticity']
modules_name_map = {}
for mod in python_wrappers:
    if mod in mod_names:
        modules_name_map[mod] = '_'+mod

pymods = wrap_all(_quippy, spec, wrap_modules,
                  merge_modules,
                  spec['short_names'],
                  prefix='qp_', package='quippy',
                  modules_name_map=modules_name_map)

# Add modules to quippy package and to sys.modules
for name, mod in pymods.items():
    sys.modules['quippy.'+name] = mod
    setattr(sys.modules[__name__], name, mod)

    # Emulate 'from quippy.X import *' for modules without wrapper
    if name in python_wrappers:
        continue
    for sym in mod.__all__:
        setattr(sys.modules[__name__], sym, getattr(mod, sym))
    __all__.extend(mod.__all__)

del wrap_modules, merge_modules, modules_name_map, mod_names, mod_files
del name, mod, pymods

# Python modules which extend Fortran modules

import quippy.atoms
from quippy.atoms import *
__all__.extend(quippy.atoms.__all__)

import quippy.dictionary
from quippy.dictionary import *
__all__.extend(quippy.dictionary.__all__)

import quippy.cinoutput
from quippy.cinoutput import *
__all__.extend(quippy.cinoutput.__all__)

import quippy.dynamicalsystem
from quippy.dynamicalsystem import *
__all__.extend(quippy.dynamicalsystem.__all__)

import quippy.potential
from quippy.potential import *
__all__.extend(quippy.potential.__all__)

import quippy.table
from quippy.table import *
__all__.extend(quippy.table.__all__)

import quippy.extendable_str
from quippy.extendable_str import *
__all__.extend(quippy.extendable_str.__all__)

import quippy.periodictable
from quippy.periodictable import *
__all__.extend(quippy.periodictable.__all__)

# Utility modules - pure Python

import quippy.fortranio
from quippy.fortranio import *
__all__.extend(quippy.fortranio.__all__)

if get_fortran_indexing():
   import quippy.farray
   __all__.extend(quippy.farray.__all__)
   from quippy.farray import *
   quippy_array = FortranArray
else:
   quippy_array = np.ndarray
__all__.append('quippy_array')

import quippy.io
from quippy.io import *
__all__.extend(quippy.io.__all__)

import quippy.util
from quippy.util import *
__all__.extend(quippy.util.__all__)

import quippy.asap
import quippy.povray
import quippy.cube
import quippy.netcdf
import quippy.imd
import quippy.vasp
import quippy.dan
import quippy.qbox

if 'HAVE_CP2K' in QUIP_MAKEFILE and QUIP_MAKEFILE['HAVE_CP2K'] == 1:
    import quippy.cp2k
    from quippy.cp2k import *
    __all__.extend(quippy.cp2k.__all__)

try:
    import quippy.castep
except ImportError:
    logging.debug('quippy.castep import quippy.failed.')

if 'atomeye' in available_modules:
    import atomeye
    import quippy.atomeyewriter

if 'enthought.mayavi' in available_modules:
    import quippy.plot3d
    from quippy.plot3d import *
    __all__.extend(quippy.plot3d.__all__)

import quippy.elasticity
from quippy.elasticity import *
__all__.extend(quippy.elasticity.__all__)

import quippy.surface
from quippy.surface import *
__all__.extend(quippy.surface.__all__)

import quippy.structures
from quippy.structures import *
__all__.extend(quippy.structures.__all__)

import quippy.crack
from quippy.crack import *
__all__.extend(quippy.crack.__all__)

if 'ase' in available_modules:
    import quippy.neb
    from quippy.neb import *
    __all__.extend(quippy.neb.__all__)
