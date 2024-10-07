import contextlib
import sys
from collections import Counter
from pathlib import Path

import pytest

from scitrack import (
    CachingLogger,
    get_file_hexdigest,
    get_package_name,
    get_text_hexdigest,
    get_version_for_package,
)

__version__ = "2024.10.8"

TEST_ROOTDIR = Path(__file__).parent

DIRNAME = "delme"
LOGFILE_NAME = "delme.log"


@pytest.fixture
def logfile(tmp_path):
    return tmp_path / LOGFILE_NAME


def test_creates_path(logfile):
    """creates a log path"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta")
    LOGGER.shutdown()
    assert logfile.exists()


def test_set_path_if_exists(logfile):
    """cannot change an existing logging path"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta")
    with pytest.raises(AttributeError):
        LOGGER.log_file_path = logfile.parent / "invalid.log"
    LOGGER.shutdown()


def test_tracks_args(logfile):
    """details on host, python version should be present in log"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta")
    LOGGER.shutdown()
    contents = logfile.read_text()
    for label in ["system_details", "python", "user", "command_string"]:
        assert contents.count(f"\t{label}") == 1, (
            label,
            contents.count(label),
        )


def test_tracks_locals(logfile):
    """details on local arguments should be present in log"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile

    def track_func(a=1, b="abc"):
        LOGGER.log_args()

    track_func()
    LOGGER.shutdown()
    log_data = logfile.read_text().splitlines()
    for line in log_data:
        index = line.find("params :")
        if index > 0:
            got = eval(line.split("params :")[1])
            break
    assert got == dict(a=1, b="abc")


def test_tracks_locals_skip_module(logfile):
    """local arguments should exclude modules"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile

    def track_func(a=1, b="abc"):
        import gzip  # noqa

        LOGGER.log_args()

    track_func()
    LOGGER.shutdown()
    for line in logfile.read_text().splitlines():
        index = line.find("params :")
        if index > 0:
            got = eval(line.split("params :")[1])
            break
    assert got == dict(a=1, b="abc")


def test_package_inference():
    """correctly identify the package name"""
    name = get_package_name(CachingLogger)
    assert name == "scitrack"


def test_package_versioning():
    """correctly identify versions for specified packages"""
    vn = get_version_for_package("numpy")
    assert type(vn) is str
    with contextlib.suppress(ValueError):
        get_version_for_package("gobbledygook")
    with contextlib.suppress(ValueError):
        get_version_for_package(1)


def test_tracks_versions(logfile):
    """should track versions"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta")
    LOGGER.log_versions(["numpy"])
    LOGGER.shutdown()
    contents = logfile.read_text()
    for label in ["system_details", "python", "user", "command_string"]:
        assert contents.count(f"\t{label}") == 1, (
            label,
            contents.count(label),
        )
    for line in contents.splitlines():
        if "version :" in line:
            if "numpy" not in line:
                assert f"=={__version__}" in line, line
            else:
                assert "numpy" in line, line


def test_caching(logfile):
    """should cache calls prior to logging"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta")
    assert (
        "sample-lf.fasta" in LOGGER._messages[-2] and "md5sum" in LOGGER._messages[-1]
    )
    LOGGER.log_versions(["numpy"])
    assert "numpy==" in LOGGER._messages[-1]

    LOGGER.log_file_path = logfile
    LOGGER.shutdown()


def test_shutdown(logfile):
    """correctly purges contents"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta")
    LOGGER.shutdown()


def test_tracks_versions_empty(logfile):
    """should track version of scitrack"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta")
    LOGGER.log_versions()
    LOGGER.shutdown()
    contents = logfile.read_text()
    for label in ["system_details", "python", "user", "command_string"]:
        assert contents.count(f"\t{label}") == 1, (
            label,
            contents.count(label),
        )
    for line in contents.splitlines():
        if "version :" in line:
            assert f"=={__version__}" in line, line


def test_tracks_versions_string(logfile):
    """should track version if package name is a string"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.log_versions("numpy")
    LOGGER.shutdown()
    import numpy

    expect = f"numpy=={numpy.__version__}"
    del numpy
    for line in logfile.read_text().splitlines():
        if "version :" in line and "numpy" in line:
            assert expect in line, line


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


def test_tracks_versions_module(logfile):
    """should track version if package is a module"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    import numpy

    expect = f"numpy=={numpy.__version__}"
    LOGGER.log_versions(numpy)
    LOGGER.shutdown()
    del numpy
    for line in logfile.read_text().splitlines():
        if "version :" in line and "numpy" in line:
            assert expect in line, line


def test_appending(logfile):
    """appending to an existing logfile should work"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta")
    LOGGER.shutdown()
    records = Counter()
    for line in logfile.read_text().splitlines():
        records[line] += 1
    vals = set(list(records.values()))
    assert vals == {1}
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.mode = "a"
    LOGGER.log_file_path = logfile
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta")
    LOGGER.shutdown()

    records = Counter()
    for line in logfile.read_text().splitlines():
        records[line] += 1
    vals = set(list(records.values()))

    assert vals == {2}


def test_mdsum_input(logfile):
    """md5 sum of input file should be correct"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    # first file has LF, second has CRLF line endings
    hex_path = [
        ("96eb2c2632bae19eb65ea9224aaafdad", "sample-lf.fasta"),
        ("e7e219f66be15d8afc7cdb85303305a7", "sample-crlf.fasta"),
    ]
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta")
    LOGGER.input_file(TEST_ROOTDIR / "sample-crlf.fasta")
    LOGGER.shutdown()

    with open(logfile) as infile:
        num = 0
        for line in infile:
            for h, p in hex_path:
                if p in line:
                    assert "input_file" in line
                    line = next(infile)
                    assert h in line
                    num += 1

        assert num == len(hex_path)


def test_mdsum_output(logfile):
    """md5 sum of output file should be correct"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    # first file has LF, second has CRLF line endings
    hex_path = [
        ("96eb2c2632bae19eb65ea9224aaafdad", "sample-lf.fasta"),
    ]
    LOGGER.output_file(TEST_ROOTDIR / "sample-lf.fasta")
    LOGGER.shutdown()

    with open(logfile) as infile:
        num = 0
        for line in infile:
            for h, p in hex_path:
                if p in line:
                    line = next(infile)
                    assert h in line
                    num += 1

        assert num == len(hex_path)


def test_logging_text(logfile):
    """correctly logs text data"""
    text = "abcde\nedfgu\nyhbnd"
    hexd = "f06597f8a983dfc93744192b505a8af9"
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.text_data(text, label="UNIQUE")
    LOGGER.shutdown()
    contents = logfile.read_text().splitlines()
    unique = next((line for line in contents if "UNIQUE" in line), None)
    assert hexd in unique


def test_logfile_path(logfile):
    """correctly assigned"""
    LOGGER = CachingLogger(create_dir=True, log_file_path=logfile)
    assert LOGGER.log_file_path == str(logfile)
    LOGGER.shutdown()


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
        got = get_text_hexdigest(data)
        assert got == h, (p, repr(data))


def test_get_text_hexdigest_invalid():
    """raises TypeError when invalid data provided"""
    with pytest.raises(TypeError):
        get_text_hexdigest(None)

    with pytest.raises(TypeError):
        get_text_hexdigest([])


def test_read_from_written(tmp_path):
    """create files with different line endings dynamically"""
    text = "abcdeENDedfguENDyhbnd"
    for ex, lf in (
        ("f06597f8a983dfc93744192b505a8af9", "\n"),
        ("39db5cc2f7749f02e0c712a3ece12ffc", "\r\n"),
    ):
        p = tmp_path / "test.txt"
        data = text.replace("END", lf)
        p.write_bytes(data.encode("utf-8"))
        expect = get_text_hexdigest(data)
        assert expect == ex, (expect, ex)
        got = get_file_hexdigest(p)
        assert got == expect, f"FAILED: {lf!r}, {(ex, got)}"
