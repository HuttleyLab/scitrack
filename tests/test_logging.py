# -*- coding: utf-8 -*-

import os, shutil, subprocess
import sys, os

try:
    from mpiutils.dispatcher import USING_MPI, barrier, size
except ImportError:
    USING_MPI = False
    rank = lambda: None
    barrier = lambda: None
    size = lambda: 1

from scitrack import CachingLogger, logging, get_text_hexdigest

__author__ = "Gavin Huttley"
__copyright__ = "Copyright 2016, Gavin Huttley"
__credits__ = ["Gavin Huttley"]
__license__ = "BSD"
__version__ = "0.1.1"
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
    barrier()
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
    barrier()
    with open(LOGFILE_NAME, "r") as infile:
        contents = "".join(infile.readlines())
        for label in ["system_details", "python", "user", "command_string"]:
            assert contents.count(label) == size(), (label, contents.count(label))
    barrier()
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
    barrier()
    with open(LOGFILE_NAME, "r") as infile:
        num = 0
        for line in infile:
            line = line.strip()
            if "input_file_path md5sum" in line:
                assert "96eb2c2632bae19eb65ea9224aaafdad" in line
                num += 1
        assert num == size()
    
    barrier()
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
    
