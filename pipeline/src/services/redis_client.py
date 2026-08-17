import os
import json
import redis.asyncio as redis
from typing import Optional, Dict, Any

REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")

class RedisClient:
    """
    Asynchronous Redis Client for managing the job queue.
    Used for communication between the YouTube Scout Agent and Scribe Agents.
    """
    def __init__(self):
        self.client = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=30.0)

    async def push_to_queue(self, queue_name: str, payload: Dict[str, Any]) -> int:
        """
        Push a JSON payload to the right (tail) of a Redis list.
        """
        data_str = json.dumps(payload)
        return await self.client.rpush(queue_name, data_str)

    async def pop_from_queue(self, queue_name: str, timeout: int = 5) -> Optional[Dict[str, Any]]:
        """
        Pop a JSON payload from the Redis list using brpop.
        """
        try:
            res = await self.client.brpop(queue_name, timeout=timeout)
            if res:
                _, val = res
                return json.loads(val)
        except Exception:
            pass
        return None

    async def ping(self) -> bool:
        """
        Ping Redis to check connection health.
        """
        try:
            return await self.client.ping()
        except Exception:
            return False

    async def close(self):
        """
        Close the Redis connection pool.
        """
        await self.client.close()

# Global Client Instance
redis_client = RedisClient()
