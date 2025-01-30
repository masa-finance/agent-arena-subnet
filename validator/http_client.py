import httpx
from typing import Optional


class HttpClientManager:
    def __init__(self):
        """
        Initialize the HttpClientManager.
        """
        self.client: Optional[httpx.AsyncClient] = None

    async def start(self):
        """
        Start the HTTP client.
        """
        self.client = httpx.AsyncClient()

    async def stop(self):
        """
        Stop the HTTP client and close connections.
        """
        if self.client:
            await self.client.close()
