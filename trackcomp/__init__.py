import os, sys, platform
from traceback import format_exc
import logging, hashlib

__author__ = "Gavin Huttley"
__copyright__ = "Copyright 2014, Gavin Huttley"
__credits__ = ["Gavin Huttley"]
__license__ = "GPL"
__version__ = "0.1"
__maintainer__ = "Gavin Huttley"
__email__ = "Gavin.Huttley@anu.edu.au"
__status__ = "Development"


def abspath(path):
    """returns an expanded, absolute path"""
    return os.path.abspath(os.path.expanduser(path))

def create_path(path):
    """creates path"""
    try:
        os.makedirs(path)
    except OSError, e:
        pass

class CachingLogger(object):
    """stores log messages until a log filename is provided"""
    def __init__(self, log_file_path=None, create_dir=True):
        super(CachingLogger, self).__init__()
        self._log_file_path = None
        self._started = False
        self.create_dir = create_dir
        self._messages = []
        
        if log_file_path:
            self.log_file_path = log_file_path
        
    
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
        
        set_logger(self.log_file_path)
        for m in self._messages:
            logging.info(m)
        
        self._messages = []
        self._started = True
        
    
    def write(self, msg):
        """writes a log message"""
        
        if not self._started:
            self._messages.append(msg)
        else:
            logging.info(msg)
        
    

def set_logger(logfile_name, level=logging.DEBUG):
    """setup logging"""
    logging.basicConfig(filename=logfile_name, filemode='w', level=level,
                format='%(asctime)s\t%(levelname)s\t%(message)s',
                datefmt="%Y-%m-%d %H:%M:%S")
    logging.info('system_details: system=%s:python=%s' % (platform.version(),
                                                  platform.python_version()))

def get_file_hexdigest(filename):
    '''returns the md5 hexadecimal checksum of the file'''
    # from http://stackoverflow.com/questions/1131220/get-md5-hash-of-big-files-in-python
    with open(filename) as infile:
        md5 = hashlib.md5()
        while True:
            data = infile.read(128)
            if not data:
                break
            
            md5.update(data)
    return md5.hexdigest()
