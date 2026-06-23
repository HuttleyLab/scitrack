import logging
import sys
from collections import Counter
from pathlib import Path

import pytest

import scitrack as _scitrack
from scitrack import (
    CachingLogger,
    LogLabel,
    __version__,
    get_file_hexdigest,
    get_package_dependencies,
    get_package_licenses,
    get_package_name,
    get_text_hexdigest,
    get_version_for_package,
    log_summary,
    set_logger,
)

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
    assert got == {"a": 1, "b": "abc"}


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
    assert got == {"a": 1, "b": "abc"}


def test_package_inference():
    """correctly identify the package name"""
    name = get_package_name(CachingLogger)
    assert name == "scitrack"


def test_get_package_name_no_arg_installed_package(monkeypatch):
    # no-arg call returns the caller's installed package name

    class _Parent:
        f_globals = {"__package__": "scitrack", "__name__": "scitrack"}

    class _Frame:
        f_back = _Parent()

    monkeypatch.setattr(_scitrack.inspect, "currentframe", lambda: _Frame())
    assert get_package_name() == "scitrack"


def test_get_package_name_no_arg_subpackage(monkeypatch):
    # dotted subpackage collapses to its top-level distribution name

    class _Parent:
        f_globals = {"__package__": "scitrack.sub", "__name__": "scitrack.sub"}

    class _Frame:
        f_back = _Parent()

    monkeypatch.setattr(_scitrack.inspect, "currentframe", lambda: _Frame())
    assert get_package_name() == "scitrack"


def test_get_package_name_no_arg_falls_back_to_name(monkeypatch):
    # when __package__ is empty, fall back to __name__

    class _Parent:
        f_globals = {"__package__": "", "__name__": "scitrack"}

    class _Frame:
        f_back = _Parent()

    monkeypatch.setattr(_scitrack.inspect, "currentframe", lambda: _Frame())
    assert get_package_name() == "scitrack"


def test_get_package_name_no_arg_not_installed(monkeypatch):
    # caller's package is not an installed distribution

    class _Parent:
        f_globals = {
            "__package__": "not_a_real_pkg_xyz",
            "__name__": "not_a_real_pkg_xyz",
        }

    class _Frame:
        f_back = _Parent()

    monkeypatch.setattr(_scitrack.inspect, "currentframe", lambda: _Frame())
    assert get_package_name() == ""


def test_get_package_name_no_arg_main_script(monkeypatch):
    # script run directly (__name__ == "__main__") is not a package

    class _Parent:
        f_globals = {"__package__": None, "__name__": "__main__"}

    class _Frame:
        f_back = _Parent()

    monkeypatch.setattr(_scitrack.inspect, "currentframe", lambda: _Frame())
    assert get_package_name() == ""


def test_get_package_name_no_arg_no_current_frame(monkeypatch):
    # inspect.currentframe() returning None yields ""

    monkeypatch.setattr(_scitrack.inspect, "currentframe", lambda: None)
    assert get_package_name() == ""


def test_get_package_name_no_arg_no_parent_frame(monkeypatch):
    # frame.f_back is None (top-of-stack caller) yields ""

    class _Frame:
        f_back = None

    monkeypatch.setattr(_scitrack.inspect, "currentframe", lambda: _Frame())
    assert get_package_name() == ""


def test_package_versioning():
    """correctly identify versions for specified packages"""
    from importlib.metadata import PackageNotFoundError

    vn = get_version_for_package("numpy")
    assert type(vn) is str
    with pytest.raises(PackageNotFoundError, match="gobbledygook"):
        get_version_for_package("gobbledygook")
    with pytest.raises(ValueError, match="Unknown type"):
        get_version_for_package(1)


def test_get_version_for_package_not_installed():
    # uninstalled package name -> PackageNotFoundError carrying the name
    from importlib.metadata import PackageNotFoundError

    with pytest.raises(PackageNotFoundError, match="definitely_not_installed_xyz"):
        get_version_for_package("definitely_not_installed_xyz")


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
    assert "sample-lf.fasta" in LOGGER._messages[-2]
    assert "md5sum" in LOGGER._messages[-1]
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
    import numpy as np

    expect = f"numpy=={np.__version__}"
    del np
    for line in logfile.read_text().splitlines():
        if "version :" in line and "numpy" in line:
            assert expect in line, line


def test_log_versions_unknown_package(logfile):
    # log_versions on an uninstalled name -> PackageNotFoundError
    from importlib.metadata import PackageNotFoundError

    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    with pytest.raises(PackageNotFoundError, match="definitely_not_installed_xyz"):
        LOGGER.log_versions("definitely_not_installed_xyz")
    LOGGER.shutdown()


def test_log_versions_partial_list_raises_eagerly(logfile):
    # mixed list: bad name aborts before any "version :" line is written
    from importlib.metadata import PackageNotFoundError

    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    with pytest.raises(PackageNotFoundError, match="definitely_not_installed_xyz"):
        LOGGER.log_versions(["numpy", "definitely_not_installed_xyz"])
    LOGGER.shutdown()
    assert not any("version :" in line for line in logfile.read_text().splitlines())


def test_log_versions_uninstalled_module_does_not_raise(logfile):
    # an imported module with no installed dist -> no raise; version recorded
    pyfile = TEST_ROOTDIR / "delme_log.py"
    pyfile.write_text("__version__ = 'local-only'\n")
    sys.path.append(str(TEST_ROOTDIR))
    import delme_log

    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.log_versions(delme_log)
    LOGGER.shutdown()
    pyfile.unlink()
    assert any(
        "delme_log==local-only" in line for line in logfile.read_text().splitlines()
    )


def test_get_version_for_package():
    """should track version if package is a module"""
    import numpy as np

    got = get_version_for_package(np)
    assert got == np.__version__
    # one with a callable
    pyfile = TEST_ROOTDIR / "delme.py"
    pyfile.write_text("def version():\n  return 'my-version'")
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
    import numpy as np

    expect = f"numpy=={np.__version__}"
    LOGGER.log_versions(np)
    LOGGER.shutdown()
    del np
    for line in logfile.read_text().splitlines():
        if "version :" in line and "numpy" in line:
            assert expect in line, line


def test_get_package_dependencies_not_installed(monkeypatch):
    # unknown package -> empty dict (never raises)
    def fake_requires(name):
        raise _scitrack.importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(_scitrack.importlib.metadata, "requires", fake_requires)
    assert get_package_dependencies("definitely_not_installed_xyz") == {}


@pytest.mark.parametrize("requires_value", [lambda: None, list])
def test_get_package_dependencies_no_requires(monkeypatch, requires_value):
    # installed package with no declared deps -> empty dict
    monkeypatch.setattr(
        _scitrack.importlib.metadata,
        "requires",
        lambda _: requires_value(),
    )
    assert get_package_dependencies("scitrack") == {}


def test_get_package_dependencies_core_only(monkeypatch):
    # unconditional deps land under "core", names stripped of specifiers
    monkeypatch.setattr(
        _scitrack.importlib.metadata,
        "requires",
        lambda _: ["numpy>=1.0", "pandas (>=2.0)"],
    )
    assert get_package_dependencies("scitrack") == {"core": ["numpy", "pandas"]}


@pytest.mark.parametrize(
    "raw",
    [
        "numpy",
        "numpy>=1.0",
        "numpy (>=1.0)",
        "numpy[security]>=1.0",
        "numpy ; python_version >= '3.0'",
    ],
)
def test_get_package_dependencies_strips_specifiers(monkeypatch, raw):
    # every surface form of a single requirement collapses to the base name
    monkeypatch.setattr(_scitrack.importlib.metadata, "requires", lambda _: [raw])
    assert get_package_dependencies("scitrack") == {"core": ["numpy"]}


def test_get_package_dependencies_partitions_extras(monkeypatch):
    # extras-gated deps go under per-extra keys; core deps stay under "core"
    monkeypatch.setattr(
        _scitrack.importlib.metadata,
        "requires",
        lambda _: [
            "numpy>=1.0",
            "pytest; extra == 'test'",
            "sphinx; extra == 'docs'",
        ],
    )
    assert get_package_dependencies("scitrack") == {
        "core": ["numpy"],
        "test": ["pytest"],
        "docs": ["sphinx"],
    }


def test_get_package_dependencies_env_marker_drops_false(monkeypatch):
    # dep gated by a marker that's false in this env is dropped (no empty core)
    monkeypatch.setattr(
        _scitrack.importlib.metadata,
        "requires",
        lambda _: ["numpy; python_version < '2.0'"],
    )
    assert get_package_dependencies("scitrack") == {}


def test_get_package_dependencies_env_marker_keeps_true(monkeypatch):
    # dep gated by a marker that's true in this env is kept under "core"
    monkeypatch.setattr(
        _scitrack.importlib.metadata,
        "requires",
        lambda _: ["numpy; python_version >= '3.0'"],
    )
    assert get_package_dependencies("scitrack") == {"core": ["numpy"]}


@pytest.mark.parametrize(
    ("marker_tail", "expected"),
    [
        ("python_version >= '3.0'", {"test": ["pytest"]}),
        ("python_version < '2.0'", {}),
    ],
)
def test_get_package_dependencies_extras_with_env_marker(
    monkeypatch,
    marker_tail,
    expected,
):
    # extras-gated dep is included in its group only when the residual marker passes
    req = f"pytest; extra == 'test' and {marker_tail}"
    monkeypatch.setattr(_scitrack.importlib.metadata, "requires", lambda _: [req])
    assert get_package_dependencies("scitrack") == expected


def test_get_package_dependencies_unparseable_marker_kept(monkeypatch):
    # unparseable marker -> conservative fallback keeps the dep under "core"
    monkeypatch.setattr(
        _scitrack.importlib.metadata,
        "requires",
        lambda _: ["numpy; this is not a real marker"],
    )
    assert get_package_dependencies("scitrack") == {"core": ["numpy"]}


@pytest.mark.parametrize(
    ("marker", "expected"),
    [
        (
            "python_version >= '3.0' and extra == 'test' and python_version >= '3.0'",
            {"test": ["pytest"]},
        ),
        (
            "python_version < '2.0' and extra == 'test' and python_version >= '3.0'",
            {},
        ),
        (
            "python_version >= '3.0' and extra == 'test' and python_version < '2.0'",
            {},
        ),
    ],
)
def test_get_package_dependencies_three_clause_extra_middle(
    monkeypatch,
    marker,
    expected,
):
    # extra clause embedded in a 3-clause and-chain - residual must rejoin with ' and '
    monkeypatch.setattr(
        _scitrack.importlib.metadata,
        "requires",
        lambda _: [f"pytest; {marker}"],
    )
    assert get_package_dependencies("scitrack") == expected


def test_get_package_dependencies_if_installed_default_unchanged(monkeypatch):
    # default if_installed=False still returns deps even when not installed
    monkeypatch.setattr(
        _scitrack.importlib.metadata,
        "requires",
        lambda _: ["definitely_not_installed_xyz", "also_missing_abc"],
    )
    assert get_package_dependencies("scitrack") == {
        "core": ["definitely_not_installed_xyz", "also_missing_abc"],
    }


def test_get_package_dependencies_if_installed_filters_mixed(monkeypatch):
    # if_installed=True keeps installed names and drops uninstalled ones
    monkeypatch.setattr(
        _scitrack.importlib.metadata,
        "requires",
        lambda _: ["pytest>=7", "definitely_not_installed_xyz"],
    )
    assert get_package_dependencies("scitrack", if_installed=True) == {
        "core": ["pytest"],
    }


def test_get_package_dependencies_if_installed_drops_empty_group(monkeypatch):
    # if_installed=True omits a group entirely when none of its deps are installed
    monkeypatch.setattr(
        _scitrack.importlib.metadata,
        "requires",
        lambda _: [
            "pytest>=7",
            "definitely_not_installed_xyz; extra == 'missing'",
            "another_missing_abc; extra == 'missing'",
        ],
    )
    assert get_package_dependencies("scitrack", if_installed=True) == {
        "core": ["pytest"],
    }


def test_get_package_dependencies_if_installed_memoizes(monkeypatch):
    # the same dep name in multiple groups triggers exactly one installation probe
    monkeypatch.setattr(
        _scitrack.importlib.metadata,
        "requires",
        lambda _: [
            "pytest>=7",
            "pytest; extra == 'test'",
            "pytest; extra == 'dev'",
        ],
    )
    call_counts: dict[str, int] = {}
    real_distribution = _scitrack.importlib.metadata.distribution

    def counting_distribution(name):
        call_counts[name] = call_counts.get(name, 0) + 1
        return real_distribution(name)

    monkeypatch.setattr(
        _scitrack.importlib.metadata,
        "distribution",
        counting_distribution,
    )
    result = get_package_dependencies("scitrack", if_installed=True)
    assert result == {"core": ["pytest"], "test": ["pytest"], "dev": ["pytest"]}
    assert call_counts == {"pytest": 1}


def test_get_package_dependencies_if_installed_empty_requires_no_probe(monkeypatch):
    # if_installed=True with no requires returns {} and never probes installation state
    monkeypatch.setattr(_scitrack.importlib.metadata, "requires", lambda _: [])
    probed: list[str] = []

    def trap(name):
        probed.append(name)
        raise AssertionError("installation probe must not be called")

    monkeypatch.setattr(_scitrack.importlib.metadata, "distribution", trap)
    assert get_package_dependencies("scitrack", if_installed=True) == {}
    assert probed == []


def test_appending(logfile):
    """appending to an existing logfile should work"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta")
    LOGGER.shutdown()
    records = Counter()
    for line in logfile.read_text().splitlines():
        records[line] += 1
    vals = set(records.values())
    assert vals == {1}
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.mode = "a"
    LOGGER.log_file_path = logfile
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta")
    LOGGER.shutdown()

    records = Counter()
    for line in logfile.read_text().splitlines():
        records[line] += 1
    vals = set(records.values())

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


def test_text_data_requires_label(logfile):
    """text_data raises ValueError when label is omitted"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    with pytest.raises(ValueError, match="non-None label"):
        LOGGER.text_data("anything")
    LOGGER.shutdown()


def test_loglabel_values_are_strings():
    """LogLabel members format as their plain string value"""
    from scitrack import LogLabel

    assert LogLabel.PARAMS == "params"
    assert f"{LogLabel.PARAMS}" == "params"
    assert str(LogLabel.MISC) == "misc"


def test_input_file_accepts_loglabel_enum(logfile):
    """passing a LogLabel member as the label yields the same log line as the default"""
    from scitrack import LogLabel

    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta", label=LogLabel.INPUT_FILE)
    LOGGER.shutdown()
    contents = logfile.read_text()
    assert "\tinput_file_path :" in contents
    assert "\tinput_file_path md5sum :" in contents


def test_input_file_accepts_custom_string_label(logfile):
    """custom string labels still work for back-compat"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta", label="my-tag")
    LOGGER.shutdown()
    contents = logfile.read_text()
    assert "\tmy-tag :" in contents
    assert "\tmy-tag md5sum :" in contents


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


def test_set_logger_default_logger(tmp_path):
    """set_logger attaches the handler to the 'scitrack' logger when none is passed"""
    log_path = tmp_path / "default.log"
    handler = set_logger(log_path)
    pkg_logger = logging.getLogger("scitrack")
    try:
        assert handler in pkg_logger.handlers
        assert log_path.exists()
    finally:
        pkg_logger.removeHandler(handler)
        handler.flush()
        handler.close()


def test_log_versions_no_current_frame(monkeypatch, logfile):
    """log_versions returns silently if inspect.currentframe yields None"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    monkeypatch.setattr(_scitrack.inspect, "currentframe", lambda: None)
    LOGGER.log_versions()
    LOGGER.shutdown()


def test_log_versions_no_parent_frame(monkeypatch, logfile):
    """log_versions returns silently when the caller's f_back is None"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile

    class _Frame:
        f_back = None

    monkeypatch.setattr(_scitrack.inspect, "currentframe", lambda: _Frame())
    LOGGER.log_versions()
    LOGGER.shutdown()


def test_log_versions_uses_caller_package_name(monkeypatch, logfile):
    # log_versions resolves the caller's package name and writes its version
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile

    class _Parent:
        f_globals = {"__name__": "scitrack"}

    class _Frame:
        f_back = _Parent()

    monkeypatch.setattr(_scitrack.inspect, "currentframe", lambda: _Frame())
    LOGGER.log_versions()
    LOGGER.shutdown()

    contents = logfile.read_text()
    assert "scitrack==" in contents


def test_log_versions_resolves_external_caller_package(monkeypatch, logfile):
    # the real chain is consumer -> log_versions -> _log_metadata, so the
    # frame above scitrack's own is the true caller. log_versions() must
    # resolve that consumer package (numpy here) and log its version, rather
    # than stopping at its immediate scitrack parent
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile

    class _Consumer:
        f_globals = {"__name__": "numpy"}
        f_back = None

    class _Scitrack:
        f_globals = {"__name__": "scitrack"}
        f_back = _Consumer()

    class _Frame:
        f_back = _Scitrack()

    monkeypatch.setattr(_scitrack.inspect, "currentframe", lambda: _Frame())
    LOGGER.log_versions()
    LOGGER.shutdown()

    expect = f"numpy=={get_version_for_package('numpy')}"
    contents = logfile.read_text()
    assert expect in contents


def test_log_versions_emits_installed_deps_of_caller(monkeypatch, logfile):
    # caller's get_package_dependencies(if_installed=True) is flattened into version lines
    captured_args: dict[str, object] = {}

    def fake_deps(name, *, if_installed):
        captured_args["name"] = name
        captured_args["if_installed"] = if_installed
        return {"core": ["pkg_a"], "dev": ["pkg_b"]}

    versions = {"scitrack": "9.9.9", "pkg_a": "1.1", "pkg_b": "2.2"}
    monkeypatch.setattr(_scitrack, "get_package_dependencies", fake_deps)
    monkeypatch.setattr(_scitrack, "get_version_for_package", lambda n: versions[n])

    class _Parent:
        f_globals = {"__name__": "scitrack"}

    class _Frame:
        f_back = _Parent()

    monkeypatch.setattr(_scitrack.inspect, "currentframe", lambda: _Frame())

    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.log_versions()
    LOGGER.shutdown()

    contents = logfile.read_text()
    assert "pkg_a==1.1" in contents
    assert "pkg_b==2.2" in contents
    assert captured_args == {"name": "scitrack", "if_installed": True}


def test_log_versions_dedups_user_pkg_overlapping_dep(monkeypatch, logfile):
    # a name appearing in both deps and the user list yields exactly one version line
    monkeypatch.setattr(
        _scitrack,
        "get_package_dependencies",
        lambda name, *, if_installed: {"core": ["pkg_a", "pkg_b"]},
    )
    versions = {"scitrack": "9.9.9", "pkg_a": "1.1", "pkg_b": "2.2"}
    monkeypatch.setattr(_scitrack, "get_version_for_package", lambda n: versions[n])

    class _Parent:
        f_globals = {"__name__": "scitrack"}

    class _Frame:
        f_back = _Parent()

    monkeypatch.setattr(_scitrack.inspect, "currentframe", lambda: _Frame())

    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.log_versions(["pkg_a"])
    LOGGER.shutdown()

    lines = [ln for ln in logfile.read_text().splitlines() if "\tversion :" in ln]
    pkg_a_lines = [ln for ln in lines if "pkg_a==" in ln]
    assert len(pkg_a_lines) == 1


def test_log_versions_caller_first_then_alphabetical(monkeypatch, logfile):
    # caller's version line precedes the union, which is emitted in alphabetical order
    monkeypatch.setattr(
        _scitrack,
        "get_package_dependencies",
        lambda name, *, if_installed: {"core": ["zeta"], "dev": ["alpha"]},
    )
    versions = {"scitrack": "9.9.9", "alpha": "0.1", "mid": "0.5", "zeta": "0.9"}
    monkeypatch.setattr(_scitrack, "get_version_for_package", lambda n: versions[n])

    class _Parent:
        f_globals = {"__name__": "scitrack"}

    class _Frame:
        f_back = _Parent()

    monkeypatch.setattr(_scitrack.inspect, "currentframe", lambda: _Frame())

    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.log_versions(["mid"])
    LOGGER.shutdown()

    version_lines = [
        ln.split("\tversion : ", 1)[1]
        for ln in logfile.read_text().splitlines()
        if "\tversion : " in ln
    ]
    assert version_lines == ["scitrack==9.9.9", "alpha==0.1", "mid==0.5", "zeta==0.9"]


def test_log_versions_caller_in_user_list_not_duplicated(monkeypatch, logfile):
    # caller's own name in `packages=` does not double up the caller version line
    monkeypatch.setattr(
        _scitrack,
        "get_package_dependencies",
        lambda name, *, if_installed: {},
    )
    versions = {"scitrack": "9.9.9"}
    monkeypatch.setattr(_scitrack, "get_version_for_package", lambda n: versions[n])

    class _Parent:
        f_globals = {"__name__": "scitrack"}

    class _Frame:
        f_back = _Parent()

    monkeypatch.setattr(_scitrack.inspect, "currentframe", lambda: _Frame())

    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.log_versions(["scitrack"])
    LOGGER.shutdown()

    version_lines = [
        ln for ln in logfile.read_text().splitlines() if "\tversion :" in ln
    ]
    scitrack_lines = [ln for ln in version_lines if "scitrack==" in ln]
    assert len(scitrack_lines) == 1


def test_log_versions_uninstalled_dep_skipped(monkeypatch, logfile):
    # uninstalled declared deps are dropped via if_installed=True before logging
    monkeypatch.setattr(
        _scitrack.importlib.metadata,
        "requires",
        lambda _: ["pkg_installed", "pkg_not_installed"],
    )

    def fake_distribution(name):
        if name in {"pkg_installed", "scitrack"}:
            return
        raise _scitrack.importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(
        _scitrack.importlib.metadata,
        "distribution",
        fake_distribution,
    )

    versions = {"scitrack": "9.9.9", "pkg_installed": "1.0"}
    monkeypatch.setattr(_scitrack, "get_version_for_package", lambda n: versions[n])

    class _Parent:
        f_globals = {"__name__": "scitrack"}

    class _Frame:
        f_back = _Parent()

    monkeypatch.setattr(_scitrack.inspect, "currentframe", lambda: _Frame())

    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.log_versions()
    LOGGER.shutdown()

    contents = logfile.read_text()
    assert "pkg_installed==1.0" in contents
    assert "pkg_not_installed" not in contents


def _make_session_log(logfile):
    """write a representative scitrack session for log_summary tests"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta")
    LOGGER.input_file(TEST_ROOTDIR / "sample-crlf.fasta")
    LOGGER.log_args({"a": 1, "b": "abc"})
    LOGGER.log_versions(["numpy"])
    LOGGER.shutdown()


def test_log_summary_groups_built_in_labels(logfile):
    """default call returns every standard scitrack label"""
    _make_session_log(logfile)
    summary = log_summary(logfile)

    assert "system_details" in summary
    assert "python" in summary
    assert "user" in summary
    assert "command_string" in summary
    assert "params" in summary
    assert "version" in summary
    assert "input_file_path" in summary
    assert "input_file_path md5sum" in summary

    assert len(summary["system_details"]) == 1
    assert len(summary["input_file_path"]) == 2
    assert len(summary["input_file_path md5sum"]) == 2
    assert len(summary["version"]) >= 1  # at minimum, numpy from packages=
    assert summary["params"] == ["{'a': 1, 'b': 'abc'}"]


def test_log_summary_preserves_values_with_colons(logfile):
    """`params : {'k': 'v'}` value is captured intact even though it contains colons"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.log_args({"x": 1, "y": "needs : space"})
    LOGGER.shutdown()

    summary = log_summary(logfile)
    assert summary["params"] == ["{'x': 1, 'y': 'needs : space'}"]


def test_log_summary_accepts_pathlike(logfile):
    """passing a Path object works, not just str"""
    _make_session_log(logfile)
    assert log_summary(Path(logfile)) == log_summary(str(logfile))


def test_log_summary_md5sum_default_includes_output(logfile):
    """output_file_path md5sum is recognised without specifying labels"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.output_file(TEST_ROOTDIR / "sample-lf.fasta")
    LOGGER.shutdown()

    summary = log_summary(logfile)
    assert "output_file_path" in summary
    assert "output_file_path md5sum" in summary


def test_log_summary_extra_labels(logfile):
    """user-supplied labels widen the recognised set"""
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.input_file(TEST_ROOTDIR / "sample-lf.fasta", label="my-tag")
    LOGGER.shutdown()

    default = log_summary(logfile)
    assert "my-tag" not in default
    assert "my-tag md5sum" not in default

    widened = log_summary(logfile, labels=["my-tag", "my-tag md5sum"])
    assert len(widened["my-tag"]) == 1
    assert len(widened["my-tag md5sum"]) == 1


def test_log_summary_loglabel_enum_as_extra_label(logfile):
    """LogLabel members can be passed via the labels list (back-compat with strings)"""
    _make_session_log(logfile)
    # PARAMS is already recognised by default. Passing it again is a no-op
    # but should not double-count entries.
    summary = log_summary(logfile, labels=[LogLabel.PARAMS])
    assert len(summary["params"]) == 1


def test_log_summary_empty_file(tmp_path):
    """empty log file yields empty dict"""
    empty = tmp_path / "empty.log"
    empty.write_text("")
    assert log_summary(empty) == {}


def test_log_summary_ignores_unknown_labels(tmp_path):
    """lines with an unrecognised label are skipped"""
    log = tmp_path / "synth.log"
    log.write_text(
        "2026-06-09 10:00:00\thost:1\tINFO\tparams : alpha\n"
        "2026-06-09 10:00:00\thost:1\tINFO\tnot_a_known_label : ignored\n"
        "2026-06-09 10:00:00\thost:1\tINFO\tparams : beta\n",
    )
    summary = log_summary(log)
    assert summary == {"params": ["alpha", "beta"]}


def test_log_summary_skips_malformed_lines(tmp_path):
    """blank lines, lines with too few tabs, and lines without ' : ' are all skipped"""
    log = tmp_path / "malformed.log"
    log.write_text(
        "\n"  # blank
        "no tabs at all\n"  # < 4 fields
        "2026-06-09 10:00:00\thost:1\tINFO\tno_colon_separator\n"  # no ' : '
        "2026-06-09 10:00:00\thost:1\tINFO\tparams : kept\n",
    )
    assert log_summary(log) == {"params": ["kept"]}


def test_log_summary_multiple_entries_preserve_order(tmp_path):
    """multiple entries under the same label come back in file order"""
    log = tmp_path / "ordered.log"
    log.write_text(
        "2026-06-09 10:00:00\thost:1\tINFO\tversion : a==1\n"
        "2026-06-09 10:00:00\thost:1\tINFO\tversion : b==2\n"
        "2026-06-09 10:00:00\thost:1\tINFO\tversion : c==3\n",
    )
    assert log_summary(log) == {"version": ["a==1", "b==2", "c==3"]}


def test_log_summary_recognises_license_label(tmp_path):
    """license lines emitted by log_licenses are captured by default"""
    log = tmp_path / "lic.log"
    log.write_text(
        "2026-06-09 10:00:00\thost:1\tINFO\tlicense : scitrack==BSD-3-Clause\n"
        "2026-06-09 10:00:00\thost:1\tINFO\tlicense : numpy==BSD-3-Clause\n",
    )
    assert log_summary(log) == {
        "license": ["scitrack==BSD-3-Clause", "numpy==BSD-3-Clause"],
    }


def test_log_summary_all_labels_captures_unknown(tmp_path):
    """all_labels=True records every label, including ones not in the recognised set"""
    log = tmp_path / "all.log"
    log.write_text(
        "2026-06-09 10:00:00\thost:1\tINFO\tparams : standard\n"
        "2026-06-09 10:00:00\thost:1\tINFO\tbespoke_tag : x\n"
        "2026-06-09 10:00:00\thost:1\tINFO\tanother_tag : y\n",
    )

    default = log_summary(log)
    assert "bespoke_tag" not in default
    assert "another_tag" not in default

    everything = log_summary(log, all_labels=True)
    assert everything == {
        "params": ["standard"],
        "bespoke_tag": ["x"],
        "another_tag": ["y"],
    }


def test_loglabel_license_value():
    # LogLabel exposes a LICENSE member that formats as "license"
    assert LogLabel.LICENSE == "license"
    assert f"{LogLabel.LICENSE}" == "license"


def test_get_package_licenses_returns_dict_for_installed():
    # returns a {name: license_string} mapping for installed packages
    got = get_package_licenses(["pytest"])
    assert set(got) == {"pytest"}
    assert isinstance(got["pytest"], str)
    assert got["pytest"]


def test_get_package_licenses_raises_for_uninstalled():
    # uninstalled package name -> PackageNotFoundError carrying the name
    from importlib.metadata import PackageNotFoundError

    with pytest.raises(PackageNotFoundError, match="definitely_not_installed_xyz"):
        get_package_licenses(["definitely_not_installed_xyz"])


def test_get_package_licenses_prefers_license_expression(monkeypatch):
    # PEP 639 License-Expression wins when both fields are present
    monkeypatch.setattr(
        _scitrack.importlib.metadata,
        "metadata",
        lambda _: {"License-Expression": "MIT", "License": "Apache-2.0"},
    )
    assert get_package_licenses(["anything"]) == {"anything": "MIT"}


def test_get_package_licenses_falls_back_to_license(monkeypatch):
    # legacy License field is used when License-Expression is missing
    monkeypatch.setattr(
        _scitrack.importlib.metadata,
        "metadata",
        lambda _: {"License": "BSD-3-Clause"},
    )
    assert get_package_licenses(["anything"]) == {"anything": "BSD-3-Clause"}


def test_get_package_licenses_unknown_when_missing(monkeypatch):
    # neither License-Expression nor License declared -> "UNKNOWN"
    monkeypatch.setattr(_scitrack.importlib.metadata, "metadata", lambda _: {})
    assert get_package_licenses(["anything"]) == {"anything": "UNKNOWN"}


@pytest.mark.parametrize(
    "meta",
    [
        pytest.param({"License-Expression": "", "License": "MIT"}, id="empty_expr"),
        pytest.param(
            {"License-Expression": "UNKNOWN", "License": "MIT"},
            id="sentinel_expr",
        ),
    ],
)
def test_get_package_licenses_falls_through_empty_or_sentinel(monkeypatch, meta):
    # an empty or literal-"UNKNOWN" License-Expression falls through to License
    monkeypatch.setattr(_scitrack.importlib.metadata, "metadata", lambda _: meta)
    assert get_package_licenses(["anything"]) == {"anything": "MIT"}


def test_get_package_licenses_partial_raises_eagerly(monkeypatch):
    # a missing name in the middle of the list raises rather than returning a partial dict
    from importlib.metadata import PackageNotFoundError

    def fake_metadata(name):
        if name == "definitely_not_installed_xyz":
            raise PackageNotFoundError(name)
        return {"License": "MIT"}

    monkeypatch.setattr(_scitrack.importlib.metadata, "metadata", fake_metadata)
    with pytest.raises(PackageNotFoundError, match="definitely_not_installed_xyz"):
        get_package_licenses(["pkg_a", "definitely_not_installed_xyz", "pkg_b"])


def test_log_licenses_uses_caller_package(monkeypatch, logfile):
    # caller's package is resolved from frame globals and its license is logged
    monkeypatch.setattr(
        _scitrack,
        "_license_for_package",
        lambda name: {"scitrack": "BSD-3-Clause"}[name],
    )
    monkeypatch.setattr(
        _scitrack,
        "get_package_dependencies",
        lambda name, *, if_installed: {},
    )

    class _Parent:
        f_globals = {"__name__": "scitrack"}

    class _Frame:
        f_back = _Parent()

    monkeypatch.setattr(_scitrack.inspect, "currentframe", lambda: _Frame())

    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.log_licenses()
    LOGGER.shutdown()

    contents = logfile.read_text()
    assert "\tlicense : scitrack==BSD-3-Clause" in contents


def test_log_licenses_emits_installed_deps(monkeypatch, logfile):
    # caller's deps (resolved with if_installed=True) are flattened into license lines
    captured: dict[str, object] = {}

    def fake_deps(name, *, if_installed):
        captured["name"] = name
        captured["if_installed"] = if_installed
        return {"core": ["pkg_a"], "dev": ["pkg_b"]}

    licenses = {"scitrack": "BSD-3-Clause", "pkg_a": "MIT", "pkg_b": "Apache-2.0"}
    monkeypatch.setattr(_scitrack, "get_package_dependencies", fake_deps)
    monkeypatch.setattr(_scitrack, "_license_for_package", lambda n: licenses[n])

    class _Parent:
        f_globals = {"__name__": "scitrack"}

    class _Frame:
        f_back = _Parent()

    monkeypatch.setattr(_scitrack.inspect, "currentframe", lambda: _Frame())

    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.log_licenses()
    LOGGER.shutdown()

    contents = logfile.read_text()
    assert "pkg_a==MIT" in contents
    assert "pkg_b==Apache-2.0" in contents
    assert captured == {"name": "scitrack", "if_installed": True}


def test_log_licenses_partial_list_raises_eagerly(logfile):
    # mixed list: bad name aborts before any "license :" line is written
    from importlib.metadata import PackageNotFoundError

    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    with pytest.raises(PackageNotFoundError, match="definitely_not_installed_xyz"):
        LOGGER.log_licenses(["pytest", "definitely_not_installed_xyz"])
    LOGGER.shutdown()
    assert not any("license :" in line for line in logfile.read_text().splitlines())


def test_log_licenses_caller_first_then_alphabetical_dedup(monkeypatch, logfile):
    # caller's line precedes the union; the union is alphabetical and de-duplicated
    monkeypatch.setattr(
        _scitrack,
        "get_package_dependencies",
        lambda name, *, if_installed: {"core": ["zeta", "alpha"], "dev": ["alpha"]},
    )
    licenses = {
        "scitrack": "BSD-3-Clause",
        "alpha": "MIT",
        "mid": "Apache-2.0",
        "zeta": "GPL-3.0",
    }
    monkeypatch.setattr(_scitrack, "_license_for_package", lambda n: licenses[n])

    class _Parent:
        f_globals = {"__name__": "scitrack"}

    class _Frame:
        f_back = _Parent()

    monkeypatch.setattr(_scitrack.inspect, "currentframe", lambda: _Frame())

    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.log_licenses(["mid", "alpha", "scitrack"])
    LOGGER.shutdown()

    license_lines = [
        ln.split("\tlicense : ", 1)[1]
        for ln in logfile.read_text().splitlines()
        if "\tlicense : " in ln
    ]
    assert license_lines == [
        "scitrack==BSD-3-Clause",
        "alpha==MIT",
        "mid==Apache-2.0",
        "zeta==GPL-3.0",
    ]


@pytest.mark.parametrize(
    "make_frame",
    [
        pytest.param(lambda: None, id="no_current_frame"),
        pytest.param(lambda: type("_F", (), {"f_back": None})(), id="no_parent_frame"),
    ],
)
def test_log_licenses_silent_on_frame_failure(monkeypatch, logfile, make_frame):
    # restricted runtimes (None) and top-of-stack callers (f_back is None) both no-op
    monkeypatch.setattr(_scitrack.inspect, "currentframe", make_frame)
    LOGGER = CachingLogger(create_dir=True)
    LOGGER.log_file_path = logfile
    LOGGER.log_licenses()
    LOGGER.shutdown()
    assert not any("license :" in line for line in logfile.read_text().splitlines())
