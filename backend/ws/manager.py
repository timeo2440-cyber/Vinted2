import json
import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from fastapi import WebSocket

if TYPE_CHECKING:
    pass


class WebSocketManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, event_type: str, data: dict) -> None:
        """Broadcast a typed event to all connected WebSocket clients."""
        message = json.dumps({
            "type": event_type,
            "data": data,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        dead = []
        for ws in list(self.active_connections):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def broadcast_new_item(self, item: dict, matched_filter_ids: list[int]) -> None:
        await self.broadcast("new_item", {**item, "matched_filter_ids": matched_filter_ids})

    async def broadcast_item_match(self, item: dict, filter_id: int, filter_name: str) -> None:
        await self.broadcast("item_match", {
            **item,
            "filter_id": filter_id,
            "filter_name": filter_name,
        })

    async def broadcast_buy_attempt(self, item_id: str, filter_id: int) -> None:
        await self.broadcast("buy_attempt", {
            "item_id": item_id,
            "filter_id": filter_id,
            "status": "pending",
        })

    async def broadcast_buy_result(self, item_id: str, success: bool, price: float | None, error: str | None) -> None:
        await self.broadcast("buy_result", {
            "item_id": item_id,
            "status": "success" if success else "failed",
            "price": price,
            "error": error,
        })

    async def broadcast_bot_status(self, status: dict) -> None:
        await self.broadcast("bot_status", status)

    async def broadcast_log(self, level: str, message: str, category: str = "general") -> None:
        await self.broadcast("log", {
            "level": level,
            "message": message,
            "category": category,
        })

    async def broadcast_auth_error(self, message: str = "Session expired") -> None:
        await self.broadcast("auth_error", {"message": message})

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)


# Global singleton
ws_manager = WebSocketManager()
