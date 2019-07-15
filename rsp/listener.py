import asyncio
import logging
import collections
from functools import partial

from .constants import BUFSIZE
from .utils import get_orig_dst


class Listener:  # pylint: disable=too-many-instance-attributes
    def __init__(self, *,
                 listen_address,
                 listen_port,
                 pool,
                 timeout=None,
                 proxy_protocol=None,
                 loop=None):
        self._loop = loop if loop is not None else asyncio.get_event_loop()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._listen_address = listen_address
        self._listen_port = listen_port
        self._children = set()
        self._server = None
        self._conn_pool = pool
        self._proxy_protocol = proxy_protocol

    async def stop(self):
        await self._conn_pool.stop()
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
            try:
                data = await reader.read(BUFSIZE)
            except asyncio.CancelledError:
                raise
            except ConnectionResetError:
                break
            if not data:
                break
            writer.write(data)

            try:
                await writer.drain()
            except ConnectionResetError:
                break
            except asyncio.CancelledError:
                raise

    async def handler(self, reader, writer):
        peer_addr = writer.transport.get_extra_info('peername')
        self._logger.info("Client %s connected", str(peer_addr))
        if self._proxy_protocol:
            try:
                sock = writer.transport.get_extra_info('socket')
                orig_dst = get_orig_dst(sock)
                prologue = self._proxy_protocol.prologue(peer_addr, orig_dst)
                self._logger.debug("Client %s orig_dst=%s", str(peer_addr), str(orig_dst))
                self._logger.debug("Client %s prologue=%s", str(peer_addr), repr(prologue))
            except Exception as exc:
                self._logger.exception("Unable to handle connection transparency: "
                                   "%s", str(exc))
                return
        dst_writer = None
        try:
            dst_reader, dst_writer = await self._conn_pool.get() 
            if self._proxy_protocol:
                dst_writer.write(prologue)
            await asyncio.gather(self._pump(writer, dst_reader),
                                 self._pump(dst_writer, reader))
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
        self._logger.info("Server ready.")
