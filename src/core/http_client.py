import httpx
import logging
from typing import Optional
from src.core.config import settings

logger = logging.getLogger(__name__)

class HTTPClientManager:
    """
    Singleton manager for the global httpx.AsyncClient connection pool.
    """
    _instance: Optional['HTTPClientManager'] = None
    _client: Optional[httpx.AsyncClient] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def init(self):
        """Initializes the shared AsyncClient with connection limits."""
        if self._client is None:
            limits = httpx.Limits(
                max_connections=settings.HTTP_POOL_MAX_CONNECTIONS,
                max_keepalive_connections=settings.HTTP_POOL_MAX_KEEPALIVE
            )
            timeout = httpx.Timeout(settings.HTTP_TIMEOUT)
            self._client = httpx.AsyncClient(limits=limits, timeout=timeout)
            logger.info("Initialized global HTTP client pool")

    async def close(self):
        """Gracefully closes the shared AsyncClient."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("Closed global HTTP client pool")

    @property
    def client(self) -> httpx.AsyncClient:
        """Returns the shared AsyncClient, initializing it if necessary."""
        if self._client is None:
            self.init()
        return self._client

def get_http_client() -> httpx.AsyncClient:
    """Helper function to get the global HTTP client."""
    return HTTPClientManager().client
