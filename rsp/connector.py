import asyncio


class PooledSSHConnector:
    def __init__(self, pool, timeout=4):
        self._pool = pool
        self._timeout = timeout

    async def connect(self, host, port):
        conn = await self._pool.get() 
        return await asyncio.wait_for(conn.open_connection(host, port), self._timeout)
