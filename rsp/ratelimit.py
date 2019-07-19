import asyncio
from collections import deque

class Ratelimit:
    def __init__(self, rate, loop=None):
        self._loop = asyncio.get_event_loop() if loop is None else loop
        self._delay = 1. / rate
        self._last_released = 0
        self._waiters = deque()
        self._release_scheduled = False

    def _schedule_dispatch(self):
        self._loop.call_at(self._last_released + self._delay, self._dispatch)
        self._release_scheduled = True

    def _dispatch(self):
        self._release_scheduled = False
        while self._waiters:
            fut = self._waiters.popleft()
            if not fut.cancelled():
                fut.set_result(None)
                self._last_released = self._loop.time()
                break
        if self._waiters:
            self._schedule_dispatch()

    async def wait(self):
        t = self._loop.time()
        if self._last_released + self._delay < t and not self._release_scheduled:
            self._last_released = t
        else:
            fut = self._loop.create_future()
            self._waiters.append(fut)
            if not self._release_scheduled:
                self._schedule_dispatch()
            await fut

    async def __aenter__(self):
        await self.wait()
        return self

    async def __aexit__(self, exc, exc_type, tb):
        pass
