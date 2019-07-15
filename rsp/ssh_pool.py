import asyncio
import logging
import collections
from functools import partial

import asyncssh


class SSHPool:
    def __init__(self, *,
                 dst_address,
                 dst_port,
                 ssh_options=None,
                 timeout=4,
                 backoff=5,
                 ttl=60,
                 size=15,
                 loop=None):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._loop = loop if loop is not None else asyncio.get_event_loop()
        self._dst_address = dst_address
        self._dst_port = dst_port
        self._timeout = timeout
        self._ssh_options = ssh_options
        self._ttl = ttl
        self._size = size
        self._backoff = backoff
        self._waiters = collections.deque()
        self._reserve = collections.deque()
        self._respawn_required = asyncio.Event()
        self._respawn_required.set()
        self._respawn_coro = None
        self._conn_builders = set()

    async def start(self):
        self._conn_builders = set(self._loop.create_task(self._build_conn())
                                  for _ in range(self._size))

    async def stop(self):
        while self._conn_builders:
            tasks = list(self._conn_builders)
            self._conn_builders.clear()
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        for conn, _ in self._reserve:
            conn.abort()

    async def _build_conn(self):
        async def fail():
            self._logger.debug("Failed upstream connection. Backoff for %d "
                               "seconds", self._backoff)
            await asyncio.sleep(self._backoff)

        async def taker(grabbed):
            grabbed.set()

        def try_remove_from_queue(elem):
            try:
                self._reserve.remove(elem)
            except ValueError:
                self._logger.debug("Not found expired connection "
                                   "in reserve. This should not happen.")
            else:
                elem[0].abort()

        while True:
            try:
                conn = await asyncio.wait_for(
                    asyncssh.connect(self._dst_address,
                                     self._dst_port,
                                     options=self._ssh_options),
                    self._timeout)
            except asyncio.TimeoutError:
                self._logger.error("Connection to upstream timed out.")
                await fail()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._logger.exception("Got exception while connecting to upstream: %s", str(exc))
                await fail()
            else:
                self._logger.debug("Successfully built upstream connection.")
                while self._waiters:
                    fut = self._waiters.popleft()
                    if not fut.cancelled():
                        self._logger.warning("Pool exhausted. Dispatching connection directly to waiter!")
                        fut.set_result(conn)
                        break
                else:
                    grabbed = asyncio.Event()

                    elem = (conn, partial(taker, grabbed))
                    self._reserve.append(elem)

                    try:
                        await asyncio.wait_for(event.wait(), self._ttl)
                    except asyncio.TimeoutError:
                        if not grabbed.is_set():
                            try_remove_from_queue(elem)
                    
    async def get(self):
        if self._reserve:
            conn, take = self._reserve.popleft()
            await take()
            self._logger.debug("Obtained connection from pool.")
            return conn
        else:
            fut = self._loop.create_future()
            self._waiters.append(fut)
            self._logger.debug("Awaiting for free connection.")
            return await fut
