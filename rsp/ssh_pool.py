import asyncio
import logging
import collections
from functools import partial

import asyncssh


class SSHPoolBorrow:
    def __init__(self, get, release):
        self._conn = None
        self._get = get
        self._release = release

    async def __aenter__(self):
        self._conn = await self._get()
        return self._conn

    async def __aexit__(self, exc, exc_type, tb):
        if exc_type is None:
            self._release(self._conn)


class SSHPool:
    def __init__(self, *,
                 dst_address,
                 dst_port,
                 ratelimit,
                 ssh_options=None,
                 timeout=4,
                 backoff=5,
                 size=15,
                 loop=None):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._loop = loop if loop is not None else asyncio.get_event_loop()
        self._dst_address = dst_address
        self._dst_port = dst_port
        self._timeout = timeout
        self._ssh_options = ssh_options
        self._size = size
        self._backoff = backoff
        self._waiters = collections.deque()
        self._reserve = collections.deque()
        self._ratelimit = ratelimit
        self._tasks = set()

    async def start(self):
        self._rebalance_pool()

    async def stop(self):
        while self._tasks:
            tasks = list(self._tasks)
            self._tasks.clear()
            for t in tasks:
                t.cancel()
            await asyncio.wait(tasks)
        for conn in self._reserve:
            conn.abort()

    def _task_done_cb(self, task):
        if not task.cancelled():
            exc = task.exception()
            if exc is not None:
                try:
                    raise exc
                except Exception:
                    self._logger.exception("Got exception from finished pool "
                                           "task: %s", str(exc))
        self._tasks.discard(task)

    def _rebalance_pool(self):
        debt = self._size - len(self._reserve) + len(self._waiters) - len(self._tasks)
        self._logger.debug("_rebalance_pool: debt=%d; len(reserve)=%d, "
                           "len(waiters)=%d, len(tasks)=%d", debt,
                           len(self._reserve), len(self._waiters),
                           len(self._tasks))
        for i in range(debt):
            task = self._loop.create_task(self._build_conn())
            task.add_done_callback(self._task_done_cb)
            self._tasks.add(task)

    async def _build_conn(self):
        async def fail():
            self._logger.debug("Failed upstream connection. Backoff for %d "
                               "seconds", self._backoff)
            await asyncio.sleep(self._backoff)

        while True:
            try:
                async with self._ratelimit:
                    self._logger.debug("_build_conn: connect attempt.")
                    conn = await asyncio.wait_for(
                        asyncssh.connect(self._dst_address,
                                         self._dst_port,
                                         options=self._ssh_options()),
                        self._timeout)
                    break
            except asyncio.TimeoutError:
                self._logger.error("Connection to upstream timed out.")
                await fail()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._logger.exception("Got exception while connecting to upstream: %s", str(exc))
                await fail()
        self._logger.debug("Successfully built upstream connection.")
        while self._waiters:
            fut = self._waiters.popleft()
            if not fut.cancelled():
                self._logger.warning("Pool exhausted. Dispatching connection directly to waiter!")
                fut.set_result(conn)
                break
        else:
            self._reserve.append(conn)
                    
    async def get(self):
        if self._reserve:
            conn = self._reserve.popleft()
            self._rebalance_pool()
            self._logger.debug("Obtained connection from pool.")
            return conn
        else:
            fut = self._loop.create_future()
            self._waiters.append(fut)
            self._rebalance_pool()
            self._logger.debug("Awaiting for free connection.")
            return await fut

    def release(self, conn):
        self._logger.debug("Connection released.")
        self._reserve.append(conn)

    def borrow(self):
        return SSHPoolBorrow(self.get, self.release)

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.stop()
