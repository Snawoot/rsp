import asyncio
import logging
import collections
import socket
import ctypes
from functools import partial

from . import constants
from .utils import detect_af
from .baselistener import BaseListener


BUFSIZE = constants.BUFSIZE


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


class TransparentListener(BaseListener):  # pylint: disable=too-many-instance-attributes
    def __init__(self, *,
                 listen_address,
                 listen_port,
                 pool,
                 timeout=4,
                 loop=None):
        self._loop = loop if loop is not None else asyncio.get_event_loop()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._listen_address = listen_address
        self._listen_port = listen_port
        self._children = set()
        self._server = None
        self._pool = pool
        self._timeout = timeout

    async def stop(self):
        self._server.close()
        await self._server.wait_closed()
        while self._children:
            children = list(self._children)
            self._children.clear()
            self._logger.debug("Cancelling %d client handlers...",
                               len(children))
            for task in children:
                task.cancel()
            await asyncio.wait(children)
            # workaround for TCP server keeps spawning handlers for a while
            # after wait_closed() completed
            await asyncio.sleep(.5)

    async def _pump(self, writer, reader):
        while True:
            data = await reader.read(BUFSIZE)
            if not data:
                break
            writer.write(data)
            await writer.drain()

    async def handler(self, reader, writer):
        peer_addr = writer.transport.get_extra_info('peername')
        self._logger.info("Client %s connected", str(peer_addr))
        dst_writer = None
        try:
            # Instead get dst addr from socket options
            sock = writer.transport.get_extra_info('socket')
            dst_addr, dst_port = get_orig_dst(sock)
            self._logger.info("Client %s requested connection to %s:%s",
                              peer_addr, dst_addr, dst_port)
            async with self._pool.borrow() as ssh_conn:
                dst_reader, dst_writer = await asyncio.wait_for(
                    ssh_conn.open_connection(dst_addr, dst_port),
                    self._timeout)
                t1 = asyncio.ensure_future(self._pump(writer, dst_reader))
                t2 = asyncio.ensure_future(self._pump(dst_writer, reader))
                try:
                    await asyncio.gather(t1, t2)
                finally:
                    for t in (t1, t2):
                        if not t.done():
                            t.cancel()
                            while not t.done():
                                try:
                                    await t
                                except asyncio.CancelledError:
                                    pass
        except asyncio.CancelledError:  # pylint: disable=try-except-raise
            raise
        except Exception as exc:  # pragma: no cover
            self._logger.exception("Connection handler stopped with exception:"
                                   " %s", str(exc))
        finally:
            self._logger.info("Client %s disconnected", str(peer_addr))
            if dst_writer is not None:
                dst_writer.close()
            writer.close()

    async def start(self):
        def _spawn(reader, writer):
            def task_cb(task, fut):
                self._children.discard(task)
            task = self._loop.create_task(self.handler(reader, writer))
            self._children.add(task)
            task.add_done_callback(partial(task_cb, task))

        self._server = await asyncio.start_server(_spawn,
                                                  self._listen_address,
                                                  self._listen_port)
        self._logger.info("Transparent Proxy server listening on %s:%d",
                          self._listen_address, self._listen_port)

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.stop()
