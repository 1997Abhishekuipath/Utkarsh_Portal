"""
Lightweight WebSocket fan-out for content publish events.

Clients subscribe via WS; admin's "Publish All" calls broadcast(event) and every
connected client receives the event. Used to refresh content within ≤5s of an
admin publish (PRD §6.6).

Single-instance only. For multi-instance deployments behind a load balancer,
swap this for Redis pub/sub.
"""
from __future__ import annotations
import asyncio, json, logging
from typing import Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self._clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
        logger.info(f"[ws] connect — total={len(self._clients)}")

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._clients.discard(ws)
        logger.info(f"[ws] disconnect — total={len(self._clients)}")

    async def broadcast(self, payload: dict):
        text = json.dumps(payload)
        # Iterate copy so concurrent disconnects don't blow up
        async with self._lock:
            targets = list(self._clients)
        dead = []
        for ws in targets:
            try:
                await ws.send_text(text)
            except Exception:                                 # noqa: BLE001
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)

    @property
    def count(self) -> int:
        return len(self._clients)


manager = ConnectionManager()
