# encoding: utf-8
from logging import Handler, Formatter, makeLogRecord
from PySide.QtCore import *


class LoggerHandler(Handler):
    def __init__(self, logger_widget):
        self.logger_widget = logger_widget
        super(LoggerHandler, self).__init__()


    def emit(self, record):
        self.logger_widget.emit(SIGNAL('new_log(QString)'),
                                self.format(record))



class ColoredFormatter(Formatter):
    @staticmethod
    def gen_colorscheme(**kwargs):
        _dict = {'DEBUG': 'gray',
                 'INFO': 'green',
                 'WARNING': 'orange',
                 'ERROR': 'red',
                 'CRITICAL': 'red'}
        for levelname in kwargs:
            _dict[levelname] = kwargs[levelname]

        return _dict


    def __init__(self, fmt=None, datefmt=None, colors=None):
        super(ColoredFormatter, self).__init__(fmt, datefmt)
        if not colors:
            self.colors = {}
        else:
            self.colors = colors


    def format(self, record):
        _r = makeLogRecord(record.__dict__)
        for item in self.colors:
            if item == 'asctime':
                info = self.formatTime(_r, self.datefmt)
            else:
                info = _r.__getattribute__(item)
            _r.__setattr__(item, '<font color=%s>%s</font>' %
                                         (self.colors[item](info), info))

        _r.message = _r.getMessage()
        if self.usesTime() and not 'asctime' in self.colors:
            _r.asctime = '<b>%s</b>' % self.formatTime(record, self.datefmt)
        s = self._fmt % _r.__dict__

        return s


