#!/usr/bin/env python
import pathlib
import sys

from setuptools import find_packages, setup


__author__ = "Gavin Huttley"
__copyright__ = "Copyright 2016-2020, Gavin Huttley"
__credits__ = ["Gavin Huttley"]
__license__ = "BSD"
__version__ = "2020.6.5"
__maintainer__ = "Gavin Huttley"
__email__ = "Gavin.Huttley@anu.edu.au"
__status__ = "Development"

if sys.version_info < (3, 6):
    py_version = ".".join([str(n) for n in sys.version_info])
    raise RuntimeError(
        "Python-3.6 or greater is required, Python-%s used." % py_version
    )

PROJECT_URLS = {
    "Documentation": "https://github.com/HuttleyLab/scitrack",
    "Bug Tracker": "https://github.com/HuttleyLab/scitrack/issues",
    "Source Code": "https://github.com/HuttleyLab/scitrack",
}

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
    long_description_content_type="text/x-rst",
    platforms=["any"],
    license=[__license__],
    keywords=["science", "logging"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: BSD License",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    packages=find_packages(where="src"),
    package_dir={"": PACKAGE_DIR},
    url="https://github.com/HuttleyLab/scitrack",
    project_urls=PROJECT_URLS,
)
