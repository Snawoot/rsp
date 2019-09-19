import enum
import logging


class LogLevel(enum.IntEnum):
    debug = logging.DEBUG
    info = logging.INFO
    warn = logging.WARN
    error = logging.ERROR
    fatal = logging.FATAL
    crit = logging.CRITICAL

    def __str__(self):
        return self.name


BUFSIZE = 16 * 1024
SO_ORIGINAL_DST = 80
SOL_IPV6 = 41
