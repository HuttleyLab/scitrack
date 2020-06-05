# -*- coding: utf-8 -*-
import shutil
import sys

from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scitrack import (
    CachingLogger,
    get_file_hexdigest,
    get_package_name,
    get_text_hexdigest,
    get_version_for_package,
)


__author__ = "Gavin Huttley"
__copyright__ = "Copyright 2016-2020, Gavin Huttley"
__credits__ = ["Gavin Huttley"]
__license__ = "BSD"
__version__ = "2020.6.1"
__maintainer__ = "Gavin Huttley"
__email__ = "Gavin.Huttley@anu.edu.au"
__status__ = "Development"

TEST_ROOTDIR = Path(__file__).parent

DIRNAME = TEST_ROOTDIR / "delme"
LOGFILE_NAME = DIRNAME / "delme.log"


def test_creates_path():
    """creates a log path"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = LOGFILE_NAME
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta")
    LOGGER.shutdown()
    assert DIRNAME.exists()
    assert LOGFILE_NAME.exists()

    try:
        shutil.rmtree(DIRNAME)
    except OSError:
        pass


def test_tracks_args():
    """details on host, python version should be present in log"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = LOGFILE_NAME
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta")
    LOGGER.shutdown()
    contents = LOGFILE_NAME.read_text()
    for label in ["system_details", "python", "user", "command_string"]:
        assert contents.count(f"\t{label}") == 1, (
            label,
            contents.count(label),
        )

    try:
        shutil.rmtree(DIRNAME)
    except OSError:
        pass


def test_tracks_locals():
    """details on local arguments should be present in log"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = LOGFILE_NAME

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
        shutil.rmtree(DIRNAME)
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
    LOGGER.log_file_path = LOGFILE_NAME
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta")
    LOGGER.log_versions(["numpy"])
    LOGGER.shutdown()
    contents = LOGFILE_NAME.read_text()
    for label in ["system_details", "python", "user", "command_string"]:
        assert contents.count(f"\t{label}") == 1, (
            label,
            contents.count(label),
        )
    for line in contents.splitlines():
        if "version :" in line:
            if "numpy" not in line:
                assert "==%s" % __version__ in line, line
            else:
                assert "numpy" in line, line

    try:
        shutil.rmtree(DIRNAME)
    except OSError:
        pass


def test_caching():
    """should cache calls prior to logging"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta")
    assert (
        "sample-lf.fasta" in LOGGER._messages[-2] and "md5sum" in LOGGER._messages[-1]
    )
    LOGGER.log_versions(["numpy"])
    assert "numpy==" in LOGGER._messages[-1]

    LOGGER.log_file_path = LOGFILE_NAME
    LOGGER.shutdown()
    try:
        shutil.rmtree(DIRNAME)
    except OSError:
        pass


def test_shutdown():
    """correctly purges contents"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = LOGFILE_NAME
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta")
    LOGGER.shutdown()
    try:
        shutil.rmtree(DIRNAME)
    except OSError:
        pass


def test_tracks_versions_empty():
    """should track version of scitrack"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = LOGFILE_NAME
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta")
    LOGGER.log_versions()
    LOGGER.shutdown()
    contents = LOGFILE_NAME.read_text()
    for label in ["system_details", "python", "user", "command_string"]:
        assert contents.count(f"\t{label}") == 1, (
            label,
            contents.count(label),
        )
    for line in contents.splitlines():
        if "version :" in line:
            assert "==%s" % __version__ in line, line

    try:
        shutil.rmtree(DIRNAME)
    except OSError:
        pass


def test_tracks_versions_string():
    """should track version if package name is a string"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = LOGFILE_NAME
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
        shutil.rmtree(DIRNAME)
    except OSError:
        pass


def test_get_version_for_package():
    """should track version if package is a module"""
    import numpy

    got = get_version_for_package(numpy)
    assert got == numpy.__version__
    # one with a callable
    pyfile = TEST_ROOTDIR / "delme.py"
    pyfile.write_text("\n".join(["def version():", "  return 'my-version'"]))
    sys.path.append(TEST_ROOTDIR)
    import delme

    got = get_version_for_package("delme")
    assert got == "my-version"
    pyfile.unlink()

    # func returns a list
    pyfile.write_text("version = ['my-version']\n")
    from importlib import reload

    got = get_version_for_package(reload(delme))
    assert got == "my-version"
    pyfile.unlink()


def test_tracks_versions_module():
    """should track version if package is a module"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = LOGFILE_NAME
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
        shutil.rmtree(DIRNAME)
    except OSError:
        pass


def test_appending():
    """appending to an existing logfile should work"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = LOGFILE_NAME
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta")
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
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta")
    LOGGER.shutdown()

    records = Counter()
    with open(LOGFILE_NAME) as infile:
        for line in infile:
            records[line] += 1
    vals = set(list(records.values()))

    assert vals == {2}

    try:
        shutil.rmtree(DIRNAME)
    except OSError:
        pass


def test_mdsum_input():
    """md5 sum of input file should be correct"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = LOGFILE_NAME
    # first file has LF, second has CRLF line endings
    hex_path = [
        ("96eb2c2632bae19eb65ea9224aaafdad", "sample-lf.fasta"),
        ("e7e219f66be15d8afc7cdb85303305a7", "sample-crlf.fasta"),
    ]
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta")
    LOGGER.input_file(TEST_ROOTDIR / "sample-crlf.fasta")
    LOGGER.shutdown()

    with open(LOGFILE_NAME, "r") as infile:
        num = 0
        for line in infile:
            for h, p in hex_path:
                if p in line:
                    assert "input_file" in line
                    line = next(infile)
                    assert h in line
                    num += 1

        assert num == len(hex_path)

    try:
        shutil.rmtree(DIRNAME)
    except OSError:
        pass


def test_mdsum_output():
    """md5 sum of output file should be correct"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = LOGFILE_NAME
    # first file has LF, second has CRLF line endings
    hex_path = [
        ("96eb2c2632bae19eb65ea9224aaafdad", "sample-lf.fasta"),
    ]
    LOGGER.output_file(TEST_ROOTDIR / "sample-lf.fasta")
    LOGGER.shutdown()

    with open(LOGFILE_NAME, "r") as infile:
        num = 0
        for line in infile:
            for h, p in hex_path:
                if p in line:
                    line = next(infile)
                    assert h in line
                    num += 1

        assert num == len(hex_path)

    try:
        shutil.rmtree(DIRNAME)
    except OSError:
        pass


def test_logging_text():
    """correctly logs text data"""
    text = "abcde\nedfgu\nyhbnd"
    hexd = "f06597f8a983dfc93744192b505a8af9"
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = LOGFILE_NAME
    LOGGER.text_data(text, label="UNIQUE")
    LOGGER.shutdown()
    contents = LOGFILE_NAME.read_text().splitlines()
    unique = None
    for line in contents:
        if "UNIQUE" in line:
            unique = line
            break
    assert hexd in unique
    try:
        shutil.rmtree(DIRNAME)
    except OSError:
        pass


def test_logfile_path():
    """correctly assigned"""
    LOGGER = CachingLogger(create_dir=True, log_file_path=LOGFILE_NAME)
    assert LOGGER.log_file_path == str(LOGFILE_NAME)
    LOGGER.shutdown()
    try:
        shutil.rmtree(DIRNAME)
    except OSError:
        pass


def test_md5sum_text():
    """md5 sum for text data should be computed"""
    data = "åbcde"
    s = get_text_hexdigest(data)
    assert s
    data = "abcde"
    s = get_text_hexdigest(data)
    assert s

    # loading contents from files with diff line-endings and check
    hex_path = [
        ("96eb2c2632bae19eb65ea9224aaafdad", "sample-lf.fasta"),
        ("e7e219f66be15d8afc7cdb85303305a7", "sample-crlf.fasta"),
    ]
    for h, p in hex_path:
        p = TEST_ROOTDIR / p
        data = p.read_bytes()
        print(p, repr(data))
        got = get_text_hexdigest(data)
        assert got == h, (p, repr(data))


def test_get_text_hexdigest_invalid():
    """raises TypeError when invalid data provided"""
    with pytest.raises(TypeError):
        get_text_hexdigest(None)

    with pytest.raises(TypeError):
        get_text_hexdigest([])


def test_read_from_written():
    """create files with different line endings dynamically"""
    text = "abcdeENDedfguENDyhbnd"
    with TemporaryDirectory(dir=TEST_ROOTDIR) as dirname:
        for ex, lf in (
            ("f06597f8a983dfc93744192b505a8af9", "\n"),
            ("39db5cc2f7749f02e0c712a3ece12ffc", "\r\n"),
        ):
            p = Path(dirname) / "test.txt"
            data = text.replace("END", lf)
            p.write_bytes(data.encode("utf-8"))
            expect = get_text_hexdigest(data)
            assert expect == ex, (expect, ex)
            got = get_file_hexdigest(p)
            assert got == expect, f"FAILED: {repr(lf)}, {(ex, got)}"
