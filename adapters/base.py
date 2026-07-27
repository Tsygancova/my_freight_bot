from abc import ABC, abstractmethod

class BaseAdapter(ABC):
    def __init__(self, credentials: dict):
        self.credentials = credentials

    @abstractmethod
    async def fetch_orders(self) -> list[dict]:
        pass