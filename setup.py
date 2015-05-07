#!/usr/bin/env python
from setuptools import setup
import sys, os, re, subprocess

__author__ = "Gavin Huttley"
__copyright__ = "Copyright 2014, Gavin Huttley"
__credits__ = ["Gavin Huttley"]
__license__ = "GPL"
__version__ = "0.1"
__maintainer__ = "Gavin Huttley"
__email__ = "Gavin.Huttley@anu.edu.au"
__status__ = "Development"

# Check Python version, no point installing if unsupported version inplace
if sys.version_info < (2, 7):
    py_version = ".".join([str(n) for n in sys.version_info])
    raise RuntimeError("Python-2.7 or greater is required, Python-%s used." % py_version)

short_description = "trackcomp"

# This ends up displayed by the installer
long_description = """scitrack
Lite-weight library to facilitate tracking scientific compute runs %s.
""" % __version__

setup(
    name="scitrack",
    version=__version__,
    author="Gavin Huttley",
    author_email="gavin.huttley@anu.edu.au",
    description=short_description,
    long_description=long_description,
    platforms=["any"],
    license=["GPL"],
    keywords=["science", "bioinformatics"],
    classifiers=[
            "Development Status :: 5 - Production/Stable",
            "Intended Audience :: Science/Research",
            "License :: OSI Approved :: GNU General Public License (GPL)",
            "Topic :: Scientific/Engineering :: Bio-Informatics",
            "Topic :: Software Development :: Libraries :: Python Modules",
            "Operating System :: OS Independent",
            ],
    packages=['scitrack'],
    )
