import sys
import argparse
import asyncio
import logging
import ssl
import signal
from functools import partial

from sdnotify import SystemdNotifier
import asyncssh

from .listener import SocksListener
from .constants import LogLevel
from . import utils
from .connpool import ConnPool


def parse_args():
    parser = argparse.ArgumentParser(
        description="Rapid SSH Proxy",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("dst_address",
                        help="target hostname")
    parser.add_argument("dst_port",
                        nargs="?",
                        default=22,
                        type=utils.check_port,
                        help="target port")
    parser.add_argument("-v", "--verbosity",
                        help="logging verbosity",
                        type=utils.check_loglevel,
                        choices=LogLevel,
                        default=LogLevel.info)
    parser.add_argument("-l", "--logfile",
                        help="log file location",
                        metavar="FILE")
    parser.add_argument("--disable-uvloop",
                        help="do not use uvloop even if it is available",
                        action="store_true")

    listen_group = parser.add_argument_group('listen options')
    listen_group.add_argument("-a", "--bind-address",
                              default="127.0.0.1",
                              help="bind address")
    listen_group.add_argument("-p", "--bind-port",
                              default=1080,
                              type=utils.check_port,
                              help="bind port")

    pool_group = parser.add_argument_group('pool options')
    pool_group.add_argument("-n", "--pool-size",
                            default=15,
                            type=utils.check_positive_int,
                            help="connection pool size")
    pool_group.add_argument("-B", "--backoff",
                            default=5,
                            type=utils.check_positive_float,
                            help="delay after connection attempt failure in seconds")
    pool_group.add_argument("-T", "--ttl",
                            default=60,
                            type=utils.check_positive_float,
                            help="lifetime of idle pool connection in seconds")
    pool_group.add_argument("-w", "--timeout",
                            default=4,
                            type=utils.check_positive_float,
                            help="server connect timeout")

    ssh_group = parser.add_argument_group('SSH options')
    ssh_group.add_argument("-L", "--login",
                           help="SSH login. Default is name of current user")
    ssh_group.add_argument("-I", "--identity",
                           action="append",
                           help="SSH private key file. By default program looks "
                           "for SSH keys in usual locations. This option may be "
                           "specified multiple times",
                           metavar="KEY_FILE")
    ssh_group.add_argument("-P", "--password",
                           help="SSH password. If not specified, password auth"
                           " will be disabled")

    return parser.parse_args()

def ssh_options_from_args(args):
    kw = dict()
    kw['gss_host'] = None
    if args.login is not None:
        kw['username'] = args.login
    if args.identity is not None:
        kw['client_keys'] = list(args.identity)
    if args.password is not None:
        kw['password'] = args.password
    return asyncssh.SSHClientConnectionOptions(**kw)


async def amain(args, loop):  # pragma: no cover
    print(args)
    assert 0
    logger = logging.getLogger('MAIN')

    #pool = ConnPool(dst_address=args.dst_address,
    #                dst_port=args.dst_port,
    #                ssl_context=context,
    #                ssl_hostname=ssl_hostname,
    #                timeout=args.timeout,
    #                backoff=args.backoff,
    #                ttl=args.ttl,
    #                size=args.pool_size,
    #                loop=loop)
    #await pool.start()
    server = SocksListener(listen_address=args.bind_address,
                      listen_port=args.bind_port,
                      timeout=args.timeout,
                      pool=None,
                      loop=loop)
    await server.start()
    logger.info("Server started.")

    exit_event = asyncio.Event()
    beat = asyncio.ensure_future(utils.heartbeat())
    sig_handler = partial(utils.exit_handler, exit_event)
    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)
    notifier = await loop.run_in_executor(None, SystemdNotifier)
    await loop.run_in_executor(None, notifier.notify, "READY=1")
    await exit_event.wait()

    logger.debug("Eventloop interrupted. Shutting down server...")
    await loop.run_in_executor(None, notifier.notify, "STOPPING=1")
    beat.cancel()
    await server.stop()
    #await pool.stop()


def main():  # pragma: no cover
    args = parse_args()
    with utils.AsyncLoggingHandler(args.logfile) as log_handler:
        logger = utils.setup_logger('MAIN', args.verbosity, log_handler)
        utils.setup_logger('SocksListener', args.verbosity, log_handler)
        utils.setup_logger('ConnPool', args.verbosity, log_handler)

        logger.info("Starting eventloop...")
        if not args.disable_uvloop:
            if utils.enable_uvloop():
                logger.info("uvloop enabled.")
            else:
                logger.info("uvloop is not available. "
                            "Falling back to built-in event loop.")

        loop = asyncio.get_event_loop()
        loop.run_until_complete(amain(args, loop))
        loop.close()
        logger.info("Server finished its work.")
