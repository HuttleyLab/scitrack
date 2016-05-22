#!/usr/bin/env python
from setuptools import setup
import sys

__author__ = "Gavin Huttley"
__copyright__ = "Copyright 2016, Gavin Huttley"
__credits__ = ["Gavin Huttley"]
__license__ = "BSD"
__version__ = "0.1"
__maintainer__ = "Gavin Huttley"
__email__ = "Gavin.Huttley@anu.edu.au"
__status__ = "Development"

# Check Python version, no point installing if unsupported version inplace
if sys.version_info < (2, 7):
    py_version = ".".join([str(n) for n in sys.version_info])
    raise RuntimeError("Python-2.7 or greater is required, Python-%s used." % py_version)

short_description = "scitrack"

# This ends up displayed by the installer
long_description = """scitrack
Lite-weight library to facilitate tracking scientific compute runs, version %s.
""" % __version__

setup(
    name="scitrack",
    version=__version__,
    author="Gavin Huttley",
    author_email="gavin.huttley@anu.edu.au",
    description=short_description,
    long_description=long_description,
    platforms=["any"],
    license=[__license__],
    keywords=["science", "logging", "parallel"],
    classifiers=[
            "Development Status :: 3 - Alpha",
            "Intended Audience :: Science/Research",
            "Programming Language :: Python :: 2.7",
            "License :: OSI Approved :: GNU General Public License (GPL)",
            "Topic :: Scientific/Engineering :: Bio-Informatics",
            "Topic :: Software Development :: Libraries :: Python Modules",
            "Operating System :: OS Independent",
            ],
    packages=["scitrack"],
    extras_require={"mpi": ["mpiutils", "mpi4py"]},
    url="https://bitbucket.org/gavin.huttley/scitrack",
    )
