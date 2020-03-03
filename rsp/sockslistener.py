import asyncio
import logging
import collections
from functools import partial
import struct
import socket

from .constants import BUFSIZE
from .utils import detect_af
from .baselistener import BaseListener


class SocksException(Exception):
    pass


class BadVersion(SocksException):
    pass


class BadAuthMethod(SocksException):
    pass


class BadAddress(SocksException):
    pass


SOCKS5REQ = struct.Struct('!BBBB')


class SocksListener(BaseListener):  # pylint: disable=too-many-instance-attributes
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

    async def _socks_prologue(self, reader, writer):
        ver = await reader.readexactly(1)
        if ver != b'\x05':
            raise BadVersion("Incorrect protocol version")

        n_methods = await reader.readexactly(1)
        n_methods = int.from_bytes(n_methods, 'big')
        if n_methods == 0:
            writer.write(b'\x05\xff')
            raise BadAuthMethod("Client didn't proposed any auth method, "
                                "even \"NO AUTHENTICATION REQUIRED\" method")

        methods = await reader.readexactly(n_methods)
        if b'\x00' not in methods:
            writer.write(b'\x05\xff')
            raise BadAuthMethod("Client didn't proposed the only suitable "
                                "\"NO AUTHENTICATION REQUIRED\" method")

        writer.write(b'\x05\x00')

        req_header = await reader.readexactly(SOCKS5REQ.size)
        req_ver, req_cmd, req_rsv, req_atyp = SOCKS5REQ.unpack(req_header)
        if req_ver != 5:
            ...
            raise BadVersion("Client specified inappropriate version "
                             "in connection request")
        if not (1 <= req_cmd <= 3):
            writer.write(b'\x05\x07')
            raise UnsupportedCommand("Client requested unsupported command")

        if req_atyp not in (1,3,4):
            writer.write(b'\x05\x08')
            raise UnsupportedAddress("Client requested connection to "
                                     "unsupported address type")

        if req_atyp == 3:
            # FQDN address
            fqdn_len = await reader.readexactly(1)
            fqdn_len = int.from_bytes(fqdn_len, 'big')
            if fqdn_len == 0:
                writer.write(b'\x05\x01')
                raise BadAddress("Client requested connection to 0-length "
                                 "domain name")
            address = (await reader.readexactly(fqdn_len)).decode('ascii')
        elif req_atyp == 1:
            # IPv4 address
            address = await reader.readexactly(4)
            address = socket.inet_ntoa(address)
        elif req_atyp == 4:
            # IPv6 address
            address = await reader.readexactly(16)
            address = socket.inet_ntop(socket.AF_INET6, address)
        port = await reader.readexactly(2)
        port = int.from_bytes(port, 'big')
        return req_cmd, address, port

    async def _socks_ok(self, reader, writer, peer):
        peer_addr, peer_port = peer
        peer_af = None
        try:
            peer_af = detect_af(peer_addr)
        except:
            pass
        if peer_af == socket.AF_INET:
            resp = (b'\x05\x00\x00\x01' + socket.inet_aton(peer_addr) +
                    peer_port.to_bytes(2, 'big'))
        elif peer_af == socket.AF_INET6:
            resp = (b'\x05\x00\x00\x04' + socket.inet_pton(AF_INET6, peer_addr) +
                    peer_port.to_bytes(2, 'big'))
        else:
            resp = b'\x05\x00\x00\x03\x00\x00\x00'
        self._logger.debug("Sending response to client: %s", resp.hex())
        writer.write(resp)

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
            cmd, dst_addr, dst_port = await self._socks_prologue(reader, writer)
            if cmd != 1:
                writer.write(b'\x05\x07')
                return
            self._logger.info("Client %s requested connection to %s:%s",
                              peer_addr, dst_addr, dst_port)
            async with self._pool.borrow() as ssh_conn:
                dst_reader, dst_writer = await asyncio.wait_for(
                    ssh_conn.open_connection(dst_addr, dst_port),
                    self._timeout)
                await self._socks_ok(reader, writer, writer.get_extra_info('sockname'))
                t1 = asyncio.ensure_future(self._pump(writer, dst_reader))
                t2 = asyncio.ensure_future(self._pump(dst_writer, reader))
                try:
                    await asyncio.gather(t1, t2)
                finally:
                    self._logger.debug("Client %s: gather finally begin", peer_addr)
                    for t in (t1, t2):
                        if not t.done():
                            t.cancel()
                            while not t.done():
                                try:
                                    await t
                                except asyncio.CancelledError:
                                    pass
                    self._logger.debug("Client %s: gather finally end", peer_addr)
        except asyncio.CancelledError:  # pylint: disable=try-except-raise
            raise
        except ConnectionResetError:
            self._logger.debug("Connection for client %s has been reset", peer_addr)
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
        self._logger.info("SOCKS5 server listening on %s:%d",
                          self._listen_address, self._listen_port)

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.stop()
