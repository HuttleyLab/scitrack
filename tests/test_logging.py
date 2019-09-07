# -*- coding: utf-8 -*-

import os
import shutil
import subprocess
import sys
from collections import Counter

from scitrack import (CachingLogger, get_package_name, get_text_hexdigest,
                      get_version_for_package, logging)

__author__ = "Gavin Huttley"
__copyright__ = "Copyright 2016, Gavin Huttley"
__credits__ = ["Gavin Huttley"]
__license__ = "BSD"
__version__ = "0.1.8.1"
__maintainer__ = "Gavin Huttley"
__email__ = "Gavin.Huttley@anu.edu.au"
__status__ = "Development"

LOGFILE_NAME = "delme.log"
DIRNAME = "delme"


def test_creates_path():
    """creates a log path"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = os.path.join(DIRNAME, LOGFILE_NAME)
    LOGGER.input_file("sample.fasta")
    LOGGER.shutdown()
    assert os.path.exists(DIRNAME)
    assert os.path.exists(os.path.join(DIRNAME, LOGFILE_NAME))
    try:
        shutil.rmtree(DIRNAME)
    except OSError:
        pass


def test_tracks_args():
    """details on host, python version should be present in log"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = os.path.join(LOGFILE_NAME)
    LOGGER.input_file("sample.fasta")
    LOGGER.shutdown()
    with open(LOGFILE_NAME, "r") as infile:
        contents = "".join(infile.readlines())
        for label in ["system_details", "python", "user", "command_string"]:
            assert contents.count(label) == 1, (label, contents.count(label))
    try:
        os.remove(LOGFILE_NAME)
    except OSError:
        pass


def test_tracks_locals():
    """details on local arguments should be present in log"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = os.path.join(LOGFILE_NAME)

    def track_func(a=1, b="abc"):
        LOGGER.log_args()

    track_func()
    LOGGER.shutdown()
    with open(LOGFILE_NAME, "r") as infile:
        for line in infile:
            index = line.find("params :")
            if index > 0:
                got = eval(line.split("params :")[1])
                break
    assert got == dict(a=1, b="abc")
    try:
        os.remove(LOGFILE_NAME)
        pass
    except OSError:
        pass


def test_package_inference():
    """correctly identify the package name"""
    name = get_package_name(CachingLogger)
    assert name == "scitrack"


def test_package_versioning():
    """correctly identify versions for specified packages"""
    vn = get_version_for_package("numpy")
    assert type(vn) is str
    try:  # not installed, but using valuerrror rather than import error
        get_version_for_package("gobbledygook")
    except ValueError:
        pass

    try:
        get_version_for_package(1)
    except ValueError:
        pass


def test_tracks_versions():
    """should track versions"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = os.path.join(LOGFILE_NAME)
    LOGGER.input_file("sample.fasta")
    LOGGER.log_versions(["numpy"])
    LOGGER.shutdown()
    with open(LOGFILE_NAME, "r") as infile:
        contents = "".join(infile.readlines())
        for label in ["system_details", "python", "user", "command_string"]:
            assert contents.count(label) == 1, (label, contents.count(label))
        for line in contents.splitlines():
            if "version :" in line:
                if "numpy" not in line:
                    assert "==%s" % __version__ in line, line
                else:
                    assert "numpy" in line, line
        print("\n\n", contents)
    try:
        os.remove(LOGFILE_NAME)
    except OSError:
        pass


def test_tracks_versions_string():
    """should track version if package name is a string"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = os.path.join(LOGFILE_NAME)
    LOGGER.log_versions("numpy")
    LOGGER.shutdown()
    import numpy

    expect = "numpy==%s" % numpy.__version__
    del numpy
    with open(LOGFILE_NAME, "r") as infile:
        contents = "".join(infile.readlines())
        for line in contents.splitlines():
            if "version :" in line and "numpy" in line:
                assert expect in line, line
    try:
        os.remove(LOGFILE_NAME)
    except OSError:
        pass


def test_tracks_versions_module():
    """should track version if package is a module"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = os.path.join(LOGFILE_NAME)
    import numpy

    expect = "numpy==%s" % numpy.__version__
    LOGGER.log_versions(numpy)
    LOGGER.shutdown()
    del numpy
    with open(LOGFILE_NAME, "r") as infile:
        contents = "".join(infile.readlines())
        for line in contents.splitlines():
            if "version :" in line and "numpy" in line:
                assert expect in line, line
    try:
        os.remove(LOGFILE_NAME)
    except OSError:
        pass


def test_appending():
    """appending to an existing logfile should work"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = LOGFILE_NAME
    LOGGER.input_file("sample.fasta")
    LOGGER.shutdown()
    records = Counter()
    with open(LOGFILE_NAME) as infile:
        for line in infile:
            records[line] += 1
    vals = set(list(records.values()))
    assert vals == {1}
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.mode = "a"
    LOGGER.log_file_path = LOGFILE_NAME
    LOGGER.input_file("sample.fasta")
    LOGGER.shutdown()

    records = Counter()
    with open(LOGFILE_NAME) as infile:
        for line in infile:
            records[line] += 1
    vals = set(list(records.values()))

    assert vals == {2}

    try:
        os.remove(LOGFILE_NAME)
    except OSError:
        pass


def test_mdsum_input():
    """md5 sum of input file should be correct"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = os.path.join(LOGFILE_NAME)
    LOGGER.input_file("sample.fasta")
    LOGGER.shutdown()

    with open(LOGFILE_NAME, "r") as infile:
        num = 0
        for line in infile:
            line = line.strip()
            if "input_file_path md5sum" in line:
                assert "96eb2c2632bae19eb65ea9224aaafdad" in line
                num += 1
        assert num == 1

    try:
        os.remove(LOGFILE_NAME)
    except OSError:
        pass


def test_md5sum_text():
    """md5 sum for text data should be computed"""
    data = u"åbcde"
    s = get_text_hexdigest(data)
    assert s
    data = "abcde"
    s = get_text_hexdigest(data)
    assert s
