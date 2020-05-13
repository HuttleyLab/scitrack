#!/usr/bin/env python
import pathlib
import sys

from setuptools import setup, find_packages

__author__ = "Gavin Huttley"
__copyright__ = "Copyright 2016, Gavin Huttley"
__credits__ = ["Gavin Huttley"]
__license__ = "BSD"
__version__ = "0.1.8.1"
__maintainer__ = "Gavin Huttley"
__email__ = "Gavin.Huttley@anu.edu.au"
__status__ = "Development"

if sys.version_info < (3, 6):
    py_version = ".".join([str(n) for n in sys.version_info])
    raise RuntimeError(
        "Python-3.6 or greater is required, Python-%s used." % py_version
    )

short_description = "scitrack"

readme_path = pathlib.Path(__file__).parent / "README.rst"

long_description = readme_path.read_text()

PACKAGE_DIR = "src"

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
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Operating System :: OS Independent",
    ],
    packages=find_packages(where="src"),
    package_dir={"": PACKAGE_DIR},
    url="https://github.com/HuttleyLab/scitrack",
)
