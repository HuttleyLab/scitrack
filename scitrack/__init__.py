import os
import sys
import platform
import socket
import logging
import hashlib
import inspect

__author__ = "Gavin Huttley"
__copyright__ = "Copyright 2016, Gavin Huttley"
__credits__ = ["Gavin Huttley"]
__license__ = "BSD"
__version__ = "0.1.5"
__maintainer__ = "Gavin Huttley"
__email__ = "Gavin.Huttley@anu.edu.au"
__status__ = "Development"


def abspath(path):
    """returns an expanded, absolute path"""
    return os.path.abspath(os.path.expanduser(path))


def _create_path(path):
    """creates path"""
    if os.path.exists(path):
        return

    os.makedirs(path, exist_ok=True)


try:
    from mpiutils.dispatcher import checkmakedirs as create_path
    from mpiutils.mpi_logging import MPIFileHandler as FileHandler
except ImportError:
    create_path = _create_path
    FileHandler = logging.FileHandler


class CachingLogger(object):
    """stores log messages until a log filename is provided"""

    def __init__(self, log_file_path=None, create_dir=True, mode="w"):
        super(CachingLogger, self).__init__()
        self._log_file_path = None
        self._logfile = None
        self._started = False
        self.create_dir = create_dir
        self._messages = []
        self._hostname = socket.gethostname()
        self._mode = mode
        if log_file_path:
            self.log_file_path = log_file_path

    def _reset(self, mode="w"):
        self._log_file_path = None
        self._mode = mode
        self._started = False
        self._messages = []
        if self._logfile is not None:
            self._logfile.close()
            self._logfile = None

    @property
    def log_file_path(self):
        return self._log_file_path

    @log_file_path.setter
    def log_file_path(self, path):
        """set the log file path and then dump cached log messages"""
        path = abspath(path)
        if self.create_dir:
            dirname = os.path.dirname(path)
            create_path(dirname)

        self._log_file_path = path

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
    def mode(self, mode):
        """the logfile file opening mode"""
        self._mode = mode

    def _record_file(self, file_class, file_path):
        """writes the file path and md5 checksum to log file"""
        file_path = abspath(file_path)
        md5sum = get_file_hexdigest(file_path)
        self.log_message(file_path, label=file_class)
        self.log_message(md5sum, label="%s md5sum" % file_class)

    def input_file(self, file_path, label="input_file_path"):
        """logs path and md5 checksum

        Argument:
            - label is inserted before the message"""
        self._record_file(label, file_path)

    def output_file(self, file_path, label="output_file_path"):
        """logs path and md5 checksum

        Argument:
            - label is inserted before the message"""
        self._record_file(label, file_path)

    def text_data(self, data, label=None):
        """logs md5 checksum for input text data.

        Argument:
            - label is inserted before the message

        For this to be useful you must ensure the text order is persistent."""
        assert label is not None, "You must provide a data label"
        md5sum = get_text_hexdigest(data)
        self.log_message(md5sum, label=label)

    def log_message(self, msg, label=None):
        """writes a log message

        Argument:
            - label is inserted before the message"""
        label = label or 'misc'
        data = [label, msg]
        msg = ' : '.join(data)
        if not self._started:
            self._messages.append(msg)
        else:
            logging.info(msg)

    def log_args(self, args=None):
        """save arguments to file using label='params'
        Argument:
            - args: if None, uses inspect module to get locals
              from the calling frame"""
        if args is None:
            parent = inspect.currentframe().f_back
            args = inspect.getargvalues(parent).locals

        # remove args whose value is a CachingLogger
        for k in list(args):
            if type(args[k]) == self.__class__:
                del(args[k])

        self.log_message(str(args), label="params")

    def shutdown(self):
        """safely shutdown the logger"""
        logging.getLogger().removeHandler(self._logfile)
        self._logfile.flush()
        self._logfile.close()
        self._logfile = None
        self._reset()


def set_logger(log_file_path, level=logging.DEBUG, mode="w"):
    """setup logging"""
    handler = FileHandler(log_file_path, mode)
    handler.setLevel(level)
    hostpid = socket.gethostname() + ':' + str(os.getpid())
    fmt = '%(asctime)s\t' + hostpid + '\t%(levelname)s\t%(message)s'
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")
    handler.setFormatter(formatter)
    logging.root.addHandler(handler)
    logging.root.setLevel(level)
    logging.info('system_details : system=%s' % platform.version())
    logging.info('python : %s' % platform.python_version())
    logging.info("user : %s" % os.environ['USER'])
    logging.info("command_string : %s" % ' '.join(sys.argv))
    return handler


def get_file_hexdigest(filename):
    '''returns the md5 hexadecimal checksum of the file'''
    # from
    # http://stackoverflow.com/questions/1131220/get-md5-hash-of-big-files-in-python
    with open(filename, 'rb') as infile:
        md5 = hashlib.md5()
        while True:
            data = infile.read(128)
            if not data:
                break

            md5.update(data)
    return md5.hexdigest()


def get_text_hexdigest(data):
    """returns md5 hexadecimal checksum of string/unicode data"""
    if data.__class__ not in ("".__class__, u"".__class__):
        raise TypeError("can only checksum string or unicode data")
    data = data.encode('utf-8')
    md5 = hashlib.md5()
    md5.update(data)
    return md5.hexdigest()
