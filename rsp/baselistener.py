from abc import ABC, abstractmethod

class BaseListener(ABC):
    @abstractmethod
    async def start(self):
        """ Abstract method """

    @abstractmethod
    async def stop(self):
        """ Abstract method """

    @abstractmethod
    async def __aenter__(self):
        """ Abstract method """

    @abstractmethod
    async def __aexit__(self, exc_type, exc, tb):
        """ Abstract method """

