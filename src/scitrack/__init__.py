"""
SciTrack provides basic logging capabilities to track scientific computations.
"""

import contextlib
import hashlib
import importlib
import inspect
import logging
import os
import platform
import socket
import sys
import types
from getpass import getuser
from pathlib import Path

__version__ = "2024.10.8"


VERSION_ATTRS = ["__version__", "version", "VERSION"]


def abspath(path: str) -> str:
    """returns an expanded, absolute path"""
    return str(Path(path).expanduser().resolve())


def _create_path(path: str | os.PathLike) -> None:
    """creates path"""
    dir_path: Path = Path(path)
    if dir_path.exists():
        return

    dir_path.mkdir(parents=True, exist_ok=True)


def get_package_name(object: object) -> str:
    """returns the package name for the provided object"""
    name = inspect.getmodule(object).__name__  # type: ignore
    return name.split(".")[0]


def get_version_for_package(package: str | types.ModuleType) -> str | None:
    """returns the version of package"""
    if isinstance(package, str):
        try:
            mod = importlib.import_module(package)
        except ModuleNotFoundError as e:
            msg = f"Unknown package {package}"
            raise ValueError(msg) from e
    elif inspect.ismodule(package):
        mod = package
    else:
        msg = f"Unknown type, package {package}"
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


class CachingLogger:
    """stores log messages until a log filename is provided"""

    def __init__(
        self,
        log_file_path: os.PathLike | None = None,
        create_dir: bool = True,
        mode: str = "w",
    ) -> None:
        self._started = False
        self.create_dir = create_dir
        self._messages: list[str] = []
        self._hostname = socket.gethostname()
        self._mode = mode
        self._log_file_path = None
        self._logfile = None
        if log_file_path:
            self.log_file_path = log_file_path

    def _reset(self, mode: str = "w") -> None:
        self._mode = mode
        self._started = False
        self._messages = []
        if self._logfile is not None:
            self._logfile.flush()
            self._logfile.close()
            self._logfile = None

        self._log_file_path = None

    @property
    def log_file_path(self):
        return self._log_file_path

    @log_file_path.setter
    def log_file_path(self, path: str) -> None:
        """set the log file path and then dump cached log messages"""
        if self._log_file_path is not None:
            msg = f"log_file_path already defined as {self._log_file_path}"
            raise AttributeError(msg)

        log_path: Path = Path(path).expanduser().resolve()
        if self.create_dir:
            log_path.parent.mkdir(parents=True, exist_ok=True)

        self._log_file_path = str(log_path)

        self._logfile = set_logger(self._log_file_path, mode=self.mode)
        for m in self._messages:
            logging.info(m)

        self._messages = []
        self._started = True

    @property
    def mode(self):
        """the logfile opening mode"""
        return self._mode

    @mode.setter
    def mode(self, mode: str) -> None:
        """the logfile file opening mode"""
        self._mode = mode

    def _record_file(self, file_class: str, file_path: str) -> None:
        """writes the file path and md5 checksum to log file"""
        file_path = abspath(file_path)
        md5sum = get_file_hexdigest(file_path)
        self.log_message(file_path, label=file_class)
        self.log_message(md5sum, label=f"{file_class} md5sum")

    def input_file(self, file_path: str, label: str = "input_file_path") -> None:
        """logs path and md5 checksum

        Argument:
            - label is inserted before the message"""
        self._record_file(label, file_path)

    def output_file(self, file_path: str, label: str = "output_file_path") -> None:
        """logs path and md5 checksum

        Argument:
            - label is inserted before the message"""
        self._record_file(label, file_path)

    def text_data(self, data: str, label: str | None = None) -> None:
        """logs md5 checksum for input text data.

        Argument:
            - label is inserted before the message

        For this to be useful you must ensure the text order is persistent."""
        assert label is not None, "You must provide a data label"
        md5sum = get_text_hexdigest(data)
        self.log_message(md5sum, label=label)

    def log_message(self, msg: str, label: str | None = None) -> None:
        """writes a log message

        Argument:
            - label is inserted before the message"""
        label = label or "misc"
        data = [label, msg]
        msg = " : ".join(data)
        if not self._started:
            self._messages.append(msg)
        else:
            logging.info(msg)

    def log_args(self, args: dict | None = None) -> None:
        """save arguments to file using label='params'
        Argument:
            - args: if None, uses inspect module to get locals
              from the calling frame"""
        if args is None:
            parent = inspect.currentframe().f_back
            args = inspect.getargvalues(parent).locals

        result = {
            k: args[k]
            for k in list(args)
            if not isinstance(args[k], self.__class__)
            and not isinstance(args[k], type(importlib))
        }
        self.log_message(str(result), label="params")

    def shutdown(self) -> None:
        """safely shutdown the logger"""
        if self._logfile:
            logging.getLogger().removeHandler(self._logfile)
        self._reset()

    def log_versions(self, packages: list[str] | str | None = None) -> None:
        """logs version from the global namespace where
        method is invoked, plus from any named packages"""
        to_check: list[str | types.ModuleType] = []
        if isinstance(packages, str) or inspect.ismodule(packages):
            to_check = [packages]
        elif isinstance(packages, (list, tuple)):
            to_check = packages

        for i, p in enumerate(to_check):
            if inspect.ismodule(p):
                to_check[i] = p.__name__

        frame: types.FrameType | None = inspect.currentframe()
        if frame is None:
            return

        parent = frame.f_back
        if parent is None:
            return

        g = parent.f_globals
        name = g.get("__package__", g.get("__name__", ""))
        if name:
            vn = get_version_for_package(name)
        else:
            vn = [g.get(v, None) for v in VERSION_ATTRS if g.get(v, None)]
            vn = vn[0] if vn else None
            name = get_package_name(parent)

        versions = [(name, vn)]
        for package in to_check:
            vn = get_version_for_package(package)
            versions.append((package, vn))

        for n_v in versions:
            self.log_message("{}=={}".format(*n_v), label="version")


def set_logger(
    log_file_path: str | os.PathLike,
    level: int = logging.DEBUG,
    mode: str = "w",
) -> logging.Handler:
    """setup logging"""
    handler = logging.FileHandler(log_file_path, mode)
    handler.setLevel(level)
    hostpid = f"{socket.gethostname()}:{os.getpid()}"
    fmt = "%(asctime)s\t" + hostpid + "\t%(levelname)s\t%(message)s"
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")
    handler.setFormatter(formatter)
    logging.root.addHandler(handler)
    logging.root.setLevel(level)
    logger = logging.getLogger(handler.name)
    logger.info(f"system_details : system={platform.version()}")
    logger.info(f"python : {platform.python_version()}")
    logger.info(f"user : {getuser()}")
    logger.info(f"command_string : {' '.join(sys.argv)}")
    return handler


def get_file_hexdigest(filename: str | os.PathLike) -> str:
    """returns the md5 hexadecimal checksum of the file

    NOTE
    ----
    The md5 sum of get_text_hexdigest can differ from get_file_hexdigest.
    This will occur if the line ending character differs from being read in
    'rb' versus 'r' modes.
    """
    # from
    # http://stackoverflow.com/questions/1131220/get-md5-hash-of-big-files-in-python
    with open(filename, "rb") as infile:
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
        msg = "can only checksum string, unicode or bytes data"
        raise TypeError(msg)

    md5 = hashlib.md5(usedforsecurity=False)
    md5.update(data_bytes)
    return md5.hexdigest()
