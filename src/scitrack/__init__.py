"""
SciTrack provides basic logging capabilities to track scientific computations.
"""

import contextlib
import hashlib
import importlib
import importlib.metadata
import inspect
import logging
import os
import platform
import re
import socket
import sys
import types
from collections.abc import Callable
from enum import Enum
from getpass import getuser
from pathlib import Path

__version__ = "2026.6.8"


VERSION_ATTRS = ["__version__", "version", "VERSION"]


class LogLabel(str, Enum):
    """labels emitted by scitrack itself.

    Notes
    -----
    User code may also pass arbitrary strings
    """

    MISC = "misc"
    PARAMS = "params"
    VERSION = "version"
    LICENSE = "license"
    INPUT_FILE = "input_file_path"
    OUTPUT_FILE = "output_file_path"
    MD5SUM = "md5sum"
    SYSTEM_DETAILS = "system_details"
    PYTHON = "python"
    USER = "user"
    COMMAND_STRING = "command_string"

    def __str__(self) -> str:
        return str(self.value)


def _installed_package_from_globals(g: dict[str, object]) -> str:
    """top-level installed distribution name from a frame's globals, or ''

    Notes
    -----
    Prefers ``__package__`` over ``__name__``, collapses dotted names
    to their top-level component, skips ``__main__``, and verifies the
    result is a registered installed distribution.
    """
    candidate = g.get("__package__") or g.get("__name__") or ""
    if not isinstance(candidate, str):
        return ""
    top = candidate.split(".")[0]
    if not top or top == "__main__":
        return ""
    try:
        importlib.metadata.distribution(top)
    except importlib.metadata.PackageNotFoundError:
        return ""
    return top


def get_package_name(obj: object | None = None) -> str:
    """returns the top-level package name

    Parameters
    ----------
    obj
        Any object whose defining module's top-level package name is
        wanted. If ``None``, the caller's frame is used instead.

    Returns
    -------
    str
        The top-level package name, or ``""`` when it cannot be
        resolved.

    Notes
    -----
    When no object is provided, the package name is inferred from the
    caller's frame, and is only returned if that package is installed.
    For any non-installed package, ``""`` is returned.
    """
    if obj is not None:
        mod = inspect.getmodule(obj)
        name = getattr(mod, "__name__", "")
        return name.split(".")[0]

    frame = inspect.currentframe()
    parent = frame.f_back if frame is not None else None
    try:
        if parent is None:
            return ""
        return _installed_package_from_globals(parent.f_globals)
    finally:
        del frame, parent


def _version_via_metadata(name: str) -> str | None:
    """resolve version from installed distribution metadata (PEP 566).

    Returns None if the distribution is not installed, the lookup raises
    any exception, or the recorded version is empty.
    """
    try:
        version = importlib.metadata.version(name)
    except Exception:  # noqa: BLE001
        return None
    return version or None


def get_version_for_package(package: str | types.ModuleType) -> str | None:
    """returns the version of package"""
    if isinstance(package, str):
        version = _version_via_metadata(package)
        if version is not None:
            return version
        try:
            mod = importlib.import_module(package)
        except ModuleNotFoundError as e:
            raise importlib.metadata.PackageNotFoundError(package) from e
    elif inspect.ismodule(package):
        version = _version_via_metadata(package.__name__.split(".")[0])
        if version is not None:
            return version
        mod = package
    else:
        msg = f"Unknown type, package {package}"  # type: ignore[unreachable]
        raise ValueError(msg)

    vn = None

    for v in VERSION_ATTRS:
        with contextlib.suppress(AttributeError):
            vn = getattr(mod, v)
            if callable(vn):
                vn = vn()

            break

    if isinstance(vn, (tuple, list)):
        vn = vn[0]

    del mod

    return vn


_REQ_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_EXTRA_CLAUSE_RE = re.compile(r"""^\s*extra\s*==\s*['\"]([^'\"]+)['\"]\s*$""")


def _split_requirement(req: str) -> tuple[str, str]:
    """split a Requires-Dist entry into (name, marker_text)."""
    head, _, marker = req.partition(";")
    match = _REQ_NAME_RE.match(head)
    name = match.group(1) if match else ""
    return name, marker.strip()


def _extract_extra(marker: str) -> tuple[str | None, str]:
    """find an ``extra == 'X'`` clause and return (extra_name, residual_marker).

    Notes
    -----
    The marker is split on top-level ``and`` so an extras clause can be
    excised without mangling neighbouring clauses; the residual rejoins
    the remaining clauses with ``and``.
    """
    if not marker:
        return None, marker
    clauses = re.split(r"\s+and\s+", marker)
    extra_name: str | None = None
    residual: list[str] = []
    for clause in clauses:
        match = _EXTRA_CLAUSE_RE.match(clause)
        if match is not None and extra_name is None:
            extra_name = match.group(1)
        else:
            residual.append(clause)
    return extra_name, " and ".join(residual)


def _marker_env() -> dict[str, str]:
    """current values of supported PEP 508 environment marker variables."""
    impl = sys.implementation
    impl_version = f"{impl.version.major}.{impl.version.minor}.{impl.version.micro}"
    return {
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        "python_full_version": platform.python_version(),
        "sys_platform": sys.platform,
        "platform_system": platform.system(),
        "platform_machine": platform.machine(),
        "implementation_name": impl.name,
        "implementation_version": impl_version,
        "os_name": os.name,
    }


def _version_tuple(value: str) -> tuple[int, ...]:
    """parse a dotted version string into a comparable tuple of ints."""
    return tuple(int(p) for p in value.split("."))


_ATOM_RE = re.compile(
    r"""^\s*
        ([A-Za-z_][A-Za-z0-9_]*)        # variable
        \s*(==|!=|<=|>=|<|>)\s*          # operator
        ['\"]([^'\"]+)['\"]              # quoted literal
        \s*$
    """,
    re.VERBOSE,
)
_VERSION_VARS = frozenset(
    {"python_version", "python_full_version", "implementation_version"},
)


def _compare(op: str, a: object, b: object) -> bool:
    """apply a comparison operator to two equally-typed operands."""
    if op == "==":
        return a == b
    if op == "!=":
        return a != b
    if op == "<":
        return bool(a < b)  # type: ignore[operator]
    if op == "<=":
        return bool(a <= b)  # type: ignore[operator]
    if op == ">":
        return bool(a > b)  # type: ignore[operator]
    return bool(a >= b)  # type: ignore[operator]


def _eval_atom(atom: str, env: dict[str, str]) -> bool:
    """evaluate a single ``var <op> 'value'`` clause."""
    match = _ATOM_RE.match(atom)
    if match is None:
        msg = f"unparseable marker atom: {atom!r}"
        raise ValueError(msg)
    var, op, literal = match.group(1), match.group(2), match.group(3)
    if var not in env:
        msg = f"unsupported marker variable: {var!r}"
        raise ValueError(msg)
    actual = env[var]
    if var in _VERSION_VARS:
        return _compare(op, _version_tuple(actual), _version_tuple(literal))
    return _compare(op, actual, literal)


def _evaluate_marker(marker: str) -> bool:
    """evaluate a residual marker; on any parse failure return True (conservative)."""
    if not marker:
        return True
    try:
        env = _marker_env()
        or_terms = re.split(r"\s+or\s+", marker)
        return any(
            all(_eval_atom(atom, env) for atom in re.split(r"\s+and\s+", term))
            for term in or_terms
        )
    except (ValueError, KeyError, AttributeError):
        return True


def get_package_dependencies(
    package: str,
    *,
    if_installed: bool = False,
) -> dict[str, list[str]]:
    """returns declared dependencies of an installed package, grouped by install option

    Parameters
    ----------
    package
        Distribution name to inspect.
    if_installed
        If ``True``, only return dependencies that are installed in the
        current environment.

    Returns
    -------
    dict[str, list[str]]
        Mapping of install-option to list of dependency package names.
        Core (unconditional) deps live under ``"core"``; each ``extra ==
        'X'`` group lives under key ``"X"``. Returns ``{}`` when the
        package is not installed or declares no dependencies.

    Notes
    -----
    Names are stripped of version specifiers, extras and markers.
    Non-extra environment markers are evaluated against the current
    interpreter; deps whose markers are False are omitted. By default
    the install-state of each dependency is not checked; pass
    ``if_installed=True`` to filter on it. Within a single call each
    distinct dependency name is probed at most once, and any group
    that ends up empty after filtering is omitted from the result.
    """
    try:
        raw = importlib.metadata.requires(package)
    except importlib.metadata.PackageNotFoundError:
        return {}
    if not raw:
        return {}

    result: dict[str, list[str]] = {}
    installed_cache: dict[str, bool] = {}
    for entry in raw:
        name, marker = _split_requirement(entry)
        if not name:
            continue
        extra, residual = _extract_extra(marker)
        if not _evaluate_marker(residual):
            continue
        if if_installed:
            if name not in installed_cache:
                try:
                    importlib.metadata.distribution(name)
                except importlib.metadata.PackageNotFoundError:
                    installed_cache[name] = False
                else:
                    installed_cache[name] = True
            if not installed_cache[name]:
                continue
        key = extra or "core"
        result.setdefault(key, []).append(name)
    return result


def _license_for_package(package: str) -> str:
    """resolve the license string for an installed package.

    Notes
    -----
    Prefers PEP 639 ``License-Expression`` over the legacy ``License``
    field; returns ``"UNKNOWN"`` if neither is declared, if both are
    empty, or if a field carries the literal sentinel ``"UNKNOWN"`` that
    older sdists write into ``PKG-INFO``. Propagates
    ``PackageNotFoundError`` from ``importlib.metadata.metadata`` when
    the distribution is not installed.
    """
    meta = importlib.metadata.metadata(package)
    for field in ("License-Expression", "License"):
        if field in meta:
            value = meta[field]
            if value and value.strip().upper() != "UNKNOWN":
                return value
    return "UNKNOWN"


def get_package_licenses(packages: list[str]) -> dict[str, str]:
    """returns the declared license of each named installed package

    Parameters
    ----------
    packages
        Distribution names to look up.

    Returns
    -------
    dict[str, str]
        Mapping of each name to its license string. Missing license
        metadata yields ``"UNKNOWN"``.

    Notes
    -----
    Raises ``PackageNotFoundError`` eagerly on the first uninstalled
    name, so callers never see a partial result.
    """
    return {name: _license_for_package(name) for name in packages}


class CachingLogger:
    """stores log messages until a log filename is provided"""

    def __init__(
        self,
        log_file_path: str | os.PathLike[str] | None = None,
        create_dir: bool = True,
        mode: str = "w",
    ) -> None:
        self._started = False
        self.create_dir = create_dir
        self._messages: list[str] = []
        self._hostname = socket.gethostname()
        self._mode = mode
        self._log_file_path: str | None = None
        self._logger: logging.Logger | None = None
        self._logfile: logging.Handler | None = None
        if log_file_path:
            self.log_file_path = log_file_path

    def _reset(self, mode: str = "w") -> None:
        self._mode = mode
        self._started = False
        self._messages = []
        if self._logfile is not None:
            if self._logger is not None:
                self._logger.removeHandler(self._logfile)
            self._logfile.flush()
            self._logfile.close()
            self._logfile = None

        self._logger = None
        self._log_file_path = None

    @property
    def log_file_path(self) -> str | None:
        return self._log_file_path

    @log_file_path.setter
    def log_file_path(self, path: str | os.PathLike[str]) -> None:
        """set the log file path and then dump cached log messages"""
        if self._log_file_path is not None:
            msg = f"log_file_path already defined as {self._log_file_path}"
            raise AttributeError(msg)

        log_path: Path = Path(path).expanduser().resolve(strict=False)
        if self.create_dir:
            log_path.parent.mkdir(parents=True, exist_ok=True)

        self._log_file_path = str(log_path)

        logger_name = "scitrack." + str(log_path).replace(os.sep, "_").replace(".", "_")
        self._logger = logging.getLogger(logger_name)
        self._logfile = set_logger(log_path, mode=self.mode, logger=self._logger)
        for m in self._messages:
            self._logger.info(m)

        self._messages = []
        self._started = True

    @property
    def mode(self) -> str:
        """the logfile opening mode"""
        return self._mode

    @mode.setter
    def mode(self, mode: str) -> None:
        """the logfile file opening mode"""
        self._mode = mode

    def _record_file(self, file_class: str | LogLabel, file_path: str) -> None:
        """writes the file path and md5 checksum to log file"""
        path: Path = Path(file_path).expanduser().resolve(strict=False)
        md5sum = get_file_hexdigest(path)
        self.log_message(str(path), label=file_class)
        self.log_message(md5sum, label=f"{file_class} {LogLabel.MD5SUM}")

    def input_file(
        self,
        file_path: str,
        label: str | LogLabel = LogLabel.INPUT_FILE,
    ) -> None:
        """logs path and md5 checksum

        Argument:
            - label is inserted before the message"""
        self._record_file(label, file_path)

    def output_file(
        self,
        file_path: str,
        label: str | LogLabel = LogLabel.OUTPUT_FILE,
    ) -> None:
        """logs path and md5 checksum

        Argument:
            - label is inserted before the message
        """
        self._record_file(label, file_path)

    def text_data(self, data: str, label: str | LogLabel | None = None) -> None:
        """logs md5 checksum for input text data.

        Argument:
            - label is inserted before the message

        For this to be useful you must ensure the text order is persistent.
        """
        if label is None:
            msg = "text_data requires a non-None label"
            raise ValueError(msg)
        md5sum = get_text_hexdigest(data)
        self.log_message(md5sum, label=label)

    def log_message(self, msg: str, label: str | LogLabel | None = None) -> None:
        """writes a log message

        Argument:
            - label is inserted before the message
        """
        label = label or LogLabel.MISC
        data = [str(label), msg]
        msg = " : ".join(data)
        if not self._started or self._logger is None:
            self._messages.append(msg)
        else:
            self._logger.info(msg)

    def log_args(self, args: dict[str, object] | None = None) -> None:
        """save arguments to file using label='params'

        Argument:
            - args: if None, uses inspect module to get locals
              from the calling frame
        """
        if args is None:
            frame = inspect.currentframe()
            parent = frame.f_back if frame is not None else None
            args = inspect.getargvalues(parent).locals if parent is not None else {}
            del frame, parent

        result = {
            k: args[k]
            for k in list(args)
            if not isinstance(args[k], self.__class__)
            and not isinstance(args[k], type(importlib))
        }
        self.log_message(str(result), label=LogLabel.PARAMS)

    def shutdown(self) -> None:
        """safely shutdown the logger"""
        self._reset()

    def _log_metadata(
        self,
        packages: list[str] | str | types.ModuleType | None,
        value_for: Callable[[str], str | None],
        label: LogLabel,
        *,
        accept_modules: bool,
        caller_name: str,
    ) -> None:
        """shared body for ``log_versions``/``log_licenses``.

        Notes
        -----
        Unions ``caller_name``'s installed dependencies with ``packages``,
        resolves each name via ``value_for``, then emits ``name==value``
        lines under ``label`` with the caller first, the rest
        alphabetical. Lookups happen eagerly so a failed resolution aborts
        before any line is written.
        """
        caller_value: str | None = None
        if caller_name:
            try:
                caller_value = value_for(caller_name)
            except importlib.metadata.PackageNotFoundError:
                caller_name = ""

        if packages is None:
            user_list: list[str | types.ModuleType] = []
        elif isinstance(packages, str) or (
            accept_modules and inspect.ismodule(packages)
        ):
            user_list = [packages]
        else:
            user_list = list(packages)

        user_names = {
            (p.__name__.split(".")[0] if inspect.ismodule(p) else p) for p in user_list
        }

        deps = (
            get_package_dependencies(caller_name, if_installed=True)
            if caller_name
            else {}
        )
        dep_names: set[str] = {n for names in deps.values() for n in names}

        entries: list[tuple[str, str | None]] = []
        if caller_name:
            entries.append((caller_name, caller_value))
        for pkg in sorted((dep_names | user_names) - {caller_name}):
            entries.append((pkg, value_for(pkg)))

        for name, value in entries:
            self.log_message(f"{name}=={value}", label=label)

    def log_versions(self, packages: list[str] | str | None = None) -> None:
        """logs the caller's package, its installed dependencies, and named packages

        Parameters
        ----------
        packages
            Additional package names (or imported modules) whose versions
            should also be logged.

        Notes
        -----
        The caller's package is resolved via ``get_package_name``. When
        it is an installed distribution, its declared dependencies
        (across ``core`` and every extras group) are fetched via
        ``get_package_dependencies(..., if_installed=True)`` so only
        currently-installed deps participate. The set of those names is
        union-ed with ``packages`` and emitted in alphabetical order
        after the caller's own version line. A name in ``packages`` that
        is not installed raises ``PackageNotFoundError``.
        """
        frame = inspect.currentframe()
        parent = frame.f_back if frame is not None else None
        caller_name = (
            _installed_package_from_globals(parent.f_globals)
            if parent is not None
            else ""
        )
        del frame, parent
        self._log_metadata(
            packages,
            get_version_for_package,
            LogLabel.VERSION,
            accept_modules=True,
            caller_name=caller_name,
        )

    def log_licenses(self, packages: list[str] | str | None = None) -> None:
        """logs the caller's package, its installed dependencies, and named packages

        Parameters
        ----------
        packages
            Additional package names whose licenses should also be logged.

        Notes
        -----
        Mirrors ``log_versions``: the caller's installed package is
        resolved from frame globals, its installed dependencies are
        fetched via ``get_package_dependencies(..., if_installed=True)``,
        and that set is union-ed with ``packages`` then emitted in
        alphabetical order after the caller's own license line. A name
        in ``packages`` that is not installed raises
        ``PackageNotFoundError``.
        """
        frame = inspect.currentframe()
        parent = frame.f_back if frame is not None else None
        caller_name = (
            _installed_package_from_globals(parent.f_globals)
            if parent is not None
            else ""
        )
        del frame, parent
        self._log_metadata(
            packages,
            _license_for_package,
            LogLabel.LICENSE,
            accept_modules=False,
            caller_name=caller_name,
        )


def set_logger(
    log_file_path: str | os.PathLike[str],
    level: int = logging.DEBUG,
    mode: str = "w",
    logger: logging.Logger | None = None,
) -> logging.Handler:
    """attach a file handler to ``logger`` (or the package logger by default)

    Writes a header block (system, python, user, command_string) to the file.
    """
    if logger is None:
        logger = logging.getLogger("scitrack")
    handler = logging.FileHandler(log_file_path, mode)
    handler.setLevel(level)
    hostpid = f"{socket.gethostname()}:{os.getpid()}"
    fmt = "%(asctime)s\t" + hostpid + "\t%(levelname)s\t%(message)s"
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.info(f"{LogLabel.SYSTEM_DETAILS} : system={platform.version()}")
    logger.info(f"{LogLabel.PYTHON} : {platform.python_version()}")
    logger.info(f"{LogLabel.USER} : {getuser()}")
    logger.info(f"{LogLabel.COMMAND_STRING} : {' '.join(sys.argv)}")
    return handler


def get_file_hexdigest(filename: str | os.PathLike[str]) -> str:
    """returns the md5 hexadecimal checksum of the file

    NOTE
    ----
    The md5 sum of get_text_hexdigest can differ from get_file_hexdigest.
    This will occur if the line ending character differs from being read in
    'rb' versus 'r' modes.
    """
    # from
    # http://stackoverflow.com/questions/1131220/get-md5-hash-of-big-files-in-python
    with Path(filename).open("rb") as infile:
        md5 = hashlib.md5(usedforsecurity=False)
        while True:
            if data := infile.read(128):
                md5.update(data)
            else:
                break

    return md5.hexdigest()


def get_text_hexdigest(data: str | bytes) -> str:
    """returns md5 hexadecimal checksum of string/unicode data

    NOTE
    ----
    The md5 sum of get_text_hexdigest can differ from get_file_hexdigest.
    This will occur if the line ending character differs from being read in
    'rb' versus 'r' modes.
    """
    if isinstance(data, str):
        data_bytes: bytes = data.encode("utf-8")
    elif isinstance(data, bytes):
        data_bytes = data
    else:
        msg = "can only checksum string, unicode or bytes data"  # type: ignore[unreachable]
        raise TypeError(msg)

    md5 = hashlib.md5(usedforsecurity=False)
    md5.update(data_bytes)
    return md5.hexdigest()


def log_summary(
    path: str | os.PathLike[str],
    *,
    labels: list[str] | None = None,
    all_labels: bool = False,
) -> dict[str, list[str]]:
    """returns logfile entries grouped by label

    Parameters
    ----------
    path
        The log file path.
    labels
        Extra labels (beyond the built-in ``LogLabel``) to recognise.
        Lines whose label is not in the recognised set are skipped
        silently.
    all_labels
        If ``True``, every label encountered in the file is captured,
        not just the recognised set.

    Returns
    -------
    dict[str, list[str]]
        Mapping of label to the list of values emitted under that label,
        in the order they appear in the file.

    Raises
    ------
    ValueError
        If a reserved label (``datetime``, ``hostname`` or ``os``) is
        requested, either via ``labels`` or an ``all_labels`` capture of a
        line bearing that label.

    Notes
    -----
    The returned mapping also includes reserved keys derived from the log
    itself: ``datetime`` (timestamp of the first logged line, that is when
    logging started) and ``hostname`` (host that produced the log, from
    that line's prefix), both absent only when the file has no parsable
    lines, plus ``os`` (operating system, from the ``system_details``
    line) when present. These names are reserved and may not be used as
    labels.
    """
    reserved = {"datetime", "hostname", "os"}
    if labels and (clash := reserved.intersection(labels)):
        msg = f"reserved labels cannot be requested: {sorted(clash)}"
        raise ValueError(msg)

    recognised: set[str] = {member.value for member in LogLabel}
    recognised.add(f"{LogLabel.INPUT_FILE} {LogLabel.MD5SUM}")
    recognised.add(f"{LogLabel.OUTPUT_FILE} {LogLabel.MD5SUM}")
    if labels:
        recognised.update(labels)

    result: dict[str, list[str]] = {}
    with Path(path).open(encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line:
                continue
            try:
                ts, hostpid, _level, message = line.split("\t", 3)
            except ValueError:
                continue
            result.setdefault("datetime", [ts])
            result.setdefault("hostname", [hostpid.rsplit(":", 1)[0]])
            try:
                label, value = message.split(" : ", 1)
            except ValueError:
                continue
            if not all_labels and label not in recognised:
                continue
            if label in reserved:
                msg = f"'{label}' is a reserved label in log_summary()"
                raise ValueError(msg)
            result.setdefault(label, []).append(value)
            if label == LogLabel.SYSTEM_DETAILS.value:
                result.setdefault("os", [value.removeprefix("system=")])
    return result
