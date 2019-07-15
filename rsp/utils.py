import asyncio
import argparse
import logging
import logging.handlers
import ssl
import os
import queue
import socket
import ctypes

from . import constants


def ignore_ssl_error(loop):
    """Ignore aiohttp #3535 issue with SSL data after close

    There appears to be an issue on Python 3.7 and aiohttp SSL that throws a
    ssl.SSLError fatal error (ssl.SSLError: [SSL: KRB5_S_INIT] application data
    after close notify (_ssl.c:2609)) after we are already done with the
    connection. See GitHub issue aio-libs/aiohttp#3535

    Given a loop, this sets up a exception handler that ignores this specific
    exception, but passes everything else on to the previous exception handler
    this one replaces.

    """
    orig_handler = loop.get_exception_handler()

    def ignore_ssl_error(loop, context):
        if context.get('message') == 'SSL error in data received':
            # validate we have the right exception, transport and protocol
            exception = context.get('exception')
            protocol = context.get('protocol')
            if (
                isinstance(exception, ssl.SSLError) and exception.reason == 'KRB5_S_INIT' and
                isinstance(protocol, asyncio.sslproto.SSLProtocol) and
                'application data after close notify' in exception.strerror
            ):
                if loop.get_debug():
                    asyncio.log.logger.debug('Ignoring aiohttp SSL KRB5_S_INIT error')
                return
        if orig_handler is not None:
            orig_handler(loop, context)
        else:
            loop.default_exception_handler(context)

    loop.set_exception_handler(ignore_ssl_error)


class OverflowingQueue(queue.Queue):
    def put(self, item, block=True, timeout=None):
        try:
            return queue.Queue.put(self, item, block, timeout)
        except queue.Full:
            pass

    def put_nowait(self, item):
        return self.put(item, False)


class AsyncLoggingHandler:
    def __init__(self, logfile=None, maxsize=1024):
        _queue = OverflowingQueue(maxsize)
        if logfile is None:
            _handler = logging.StreamHandler()
        else:
            _handler = logging.FileHandler(logfile)
        self._listener = logging.handlers.QueueListener(_queue, _handler)
        self._async_handler = logging.handlers.QueueHandler(_queue)

        _handler.setFormatter(logging.Formatter('%(asctime)s '
                                                '%(levelname)-8s '
                                                '%(name)s: %(message)s',
                                                '%Y-%m-%d %H:%M:%S'))

    def __enter__(self):
        self._listener.start()
        return self._async_handler

    def __exit__(self, exc_type, exc_value, traceback):
        self._listener.stop()


def setup_logger(name, verbosity, handler):
    logger = logging.getLogger(name)
    logger.setLevel(verbosity)
    logger.addHandler(handler)
    return logger


def check_port(value):
    def fail():
        raise argparse.ArgumentTypeError(
            "%s is not a valid port number" % value)
    try:
        ivalue = int(value)
    except ValueError:
        fail()
    if not 0 < ivalue < 65536:
        fail()
    return ivalue


def check_positive_float(value):
    def fail():
        raise argparse.ArgumentTypeError(
            "%s is not a valid value" % value)
    try:
        fvalue = float(value)
    except ValueError:
        fail()
    if fvalue <= 0:
        fail()
    return fvalue


def check_positive_int(value):
    def fail():
        raise argparse.ArgumentTypeError(
            "%s is not a valid value" % value)
    try:
        fvalue = int(value)
    except ValueError:
        fail()
    if fvalue <= 0:
        fail()
    return fvalue


def check_loglevel(arg):
    try:
        return constants.LogLevel[arg]
    except (IndexError, KeyError):
        raise argparse.ArgumentTypeError("%s is not valid loglevel" % (repr(arg),))


def enable_uvloop():  # pragma: no cover
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except ImportError:
        return False
    else:
        return True


def exit_handler(exit_event, signum, frame):  # pragma: no cover pylint: disable=unused-argument
    logger = logging.getLogger('MAIN')
    if exit_event.is_set():
        logger.warning("Got second exit signal! Terminating hard.")
        os._exit(1)  # pylint: disable=protected-access
    else:
        logger.warning("Got first exit signal! Terminating gracefully.")
        exit_event.set()


async def heartbeat():
    """ Hacky coroutine which keeps event loop spinning with some interval
    even if no events are coming. This is required to handle Futures and
    Events state change when no events are occuring."""
    while True:
        await asyncio.sleep(.5)


def detect_af(addr):
    return socket.getaddrinfo(addr,
                              None,
                              socket.AF_UNSPEC,
                              0,
                              0,
                              socket.AI_NUMERICHOST)[0][0]


class sockaddr(ctypes.Structure):
    _fields_ = [('sa_family', ctypes.c_uint16),
                ('sa_data', ctypes.c_char * 14),
               ]


class sockaddr_in(ctypes.Structure):
    _fields_ = [('sin_family', ctypes.c_uint16),
                ('sin_port', ctypes.c_uint16),
                ('sin_addr', ctypes.c_uint32),
               ]

sockaddr_size = max(ctypes.sizeof(sockaddr_in), ctypes.sizeof(sockaddr))


class sockaddr_in6(ctypes.Structure):
    _fields_ = [('sin6_family', ctypes.c_uint16),
                ('sin6_port', ctypes.c_uint16),
                ('sin6_flowinfo', ctypes.c_uint32),
                ('sin6_addr', ctypes.c_char * 16),
                ('sin6_scope_id', ctypes.c_uint32),
               ]


sockaddr6_size = ctypes.sizeof(sockaddr_in6)


def get_orig_dst(sock):
    own_addr = sock.getsockname()[0]
    own_af = detect_af(own_addr)
    if own_af == socket.AF_INET:
        buf = sock.getsockopt(socket.SOL_IP, constants.SO_ORIGINAL_DST, sockaddr_size)
        sa = sockaddr_in.from_buffer_copy(buf)
        addr = socket.ntohl(sa.sin_addr)
        addr = str(addr >> 24) + '.' + str((addr >> 16) & 0xFF) + '.' + str((addr >> 8) & 0xFF) + '.' + str(addr & 0xFF)
        port = socket.ntohs(sa.sin_port)
        return addr, port
    elif own_af == socket.AF_INET6:
        buf = sock.getsockopt(constants.SOL_IPV6, constants.SO_ORIGINAL_DST, sockaddr6_size)
        sa = sockaddr_in6.from_buffer_copy(buf)
        addr = socket.inet_ntop(socket.AF_INET6, sa.sin6_addr)
        port = socket.ntohs(sa.sin_port)
        return addr, port
    else:
        raise RuntimeError("Unknown address family!")
