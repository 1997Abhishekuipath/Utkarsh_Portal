"""
Sprint G — Redis pub/sub fan-out for multi-instance WebSocket broadcast.

Each API instance:
  1. Accepts WS connections locally (via services.ws.ConnectionManager).
  2. Publishes admin publish events to the shared 'hsi:broadcast' channel.
  3. Subscribes to the channel and forwards incoming messages to its own WS clients.

This makes publish events visible across all replicas behind a load balancer.
Falls back cleanly to single-instance mode when Redis is unavailable.
"""
from __future__ import annotations
import os, json, asyncio, logging
from typing import Optional

logger = logging.getLogger(__name__)

REDIS_URL  = os.environ.get('REDIS_URL', '').strip()
CHANNEL    = os.environ.get('WS_BROADCAST_CHANNEL', 'hsi:broadcast')

_redis_pub = None      # redis.asyncio client used for PUBLISH
_listener_task: Optional[asyncio.Task] = None


async def init_publisher():
    """Lazy-init a publisher client. Safe to call repeatedly."""
    global _redis_pub
    if _redis_pub is not None:
        return _redis_pub
    if not REDIS_URL:
        return None
    try:
        import redis.asyncio as aioredis
        _redis_pub = aioredis.from_url(REDIS_URL, decode_responses=True,
                                       socket_connect_timeout=2)
        await _redis_pub.ping()
        logger.info(f"[pubsub] Redis publisher ready on {CHANNEL}")
        return _redis_pub
    except Exception as e:                                  # noqa: BLE001
        logger.warning(f"[pubsub] Redis unavailable ({e}); multi-instance WS disabled")
        _redis_pub = None
        return None


async def publish(payload: dict) -> bool:
    """Publish a payload to the broadcast channel. Returns True on success."""
    client = await init_publisher()
    if client is None:
        return False
    try:
        await client.publish(CHANNEL, json.dumps(payload))
        return True
    except Exception as e:                                  # noqa: BLE001
        logger.warning(f"[pubsub] publish failed: {e}")
        return False


async def start_listener(local_broadcast_fn):
    """Start a background task that subscribes to the channel and forwards
    messages to a local broadcaster (the in-process WS manager).

    Args:
        local_broadcast_fn: async callable(payload: dict) → None
    """
    global _listener_task
    if _listener_task and not _listener_task.done():
        return
    if not REDIS_URL:
        return

    async def _run():
        try:
            import redis.asyncio as aioredis
            sub_client = aioredis.from_url(REDIS_URL, decode_responses=True)
            pubsub = sub_client.pubsub()
            await pubsub.subscribe(CHANNEL)
            logger.info(f"[pubsub] listener subscribed to {CHANNEL}")
            async for msg in pubsub.listen():
                if msg is None or msg.get('type') != 'message':
                    continue
                data = msg.get('data')
                try:
                    payload = json.loads(data) if isinstance(data, str) else data
                except Exception:                           # noqa: BLE001
                    continue
                if isinstance(payload, dict):
                    try:
                        await local_broadcast_fn(payload)
                    except Exception as e:                  # noqa: BLE001
                        logger.warning(f"[pubsub] local broadcast failed: {e}")
        except asyncio.CancelledError:
            raise
        except Exception as e:                              # noqa: BLE001
            logger.warning(f"[pubsub] listener crashed: {e}")

    _listener_task = asyncio.create_task(_run())
