import json
import asyncio
from datetime import datetime, timezone
from typing import Optional
from fastapi import WebSocket


class WebSocketManager:
    def __init__(self):
        # Map user_id → list of WebSocket connections (a user can have multiple tabs open)
        self._user_connections: dict[int, list[WebSocket]] = {}
        # Unauthenticated connections (for backwards compat — receive global events only)
        self._anon_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket, user_id: Optional[int] = None) -> None:
        await websocket.accept()
        if user_id is not None:
            self._user_connections.setdefault(user_id, []).append(websocket)
        else:
            self._anon_connections.append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: Optional[int] = None) -> None:
        if user_id is not None:
            conns = self._user_connections.get(user_id, [])
            if websocket in conns:
                conns.remove(websocket)
            if not conns:
                self._user_connections.pop(user_id, None)
        else:
            if websocket in self._anon_connections:
                self._anon_connections.remove(websocket)

    def _build_message(self, event_type: str, data: dict) -> str:
        return json.dumps({
            "type": event_type,
            "data": data,
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    async def _send(self, ws: WebSocket, message: str) -> bool:
        """Send to one connection. Returns False if dead."""
        try:
            await ws.send_text(message)
            return True
        except Exception:
            return False

    async def broadcast(self, event_type: str, data: dict) -> None:
        """Broadcast to ALL connected users (global events)."""
        message = self._build_message(event_type, data)
        dead_user: list[tuple[int, WebSocket]] = []
        dead_anon: list[WebSocket] = []

        for user_id, conns in list(self._user_connections.items()):
            for ws in list(conns):
                if not await self._send(ws, message):
                    dead_user.append((user_id, ws))

        for ws in list(self._anon_connections):
            if not await self._send(ws, message):
                dead_anon.append(ws)

        for user_id, ws in dead_user:
            self.disconnect(ws, user_id)
        for ws in dead_anon:
            self.disconnect(ws)

    async def send_to_user(self, user_id: int, event_type: str, data: dict) -> None:
        """Send an event only to a specific user's connections."""
        conns = list(self._user_connections.get(user_id, []))
        if not conns:
            return
        message = self._build_message(event_type, data)
        dead = []
        for ws in conns:
            if not await self._send(ws, message):
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, user_id)

    async def broadcast_new_item(self, item: dict, matched_filter_ids: list[int]) -> None:
        """All items go to all users (global shared feed)."""
        await self.broadcast("new_item", {**item, "matched_filter_ids": matched_filter_ids})

    async def broadcast_item_match(self, item: dict, filter_id: int, filter_name: str, user_id) -> None:
        """Matches go only to the user who owns the filter.
        Falls back to broadcast if user_id is None (legacy filters with no owner)."""
        payload = {**item, "filter_id": filter_id, "filter_name": filter_name}
        if user_id is not None:
            await self.send_to_user(int(user_id), "item_match", payload)
        else:
            await self.broadcast("item_match", payload)

    async def broadcast_buy_attempt(self, item_id: str, filter_id: int, user_id: int) -> None:
        await self.send_to_user(user_id, "buy_attempt", {
            "item_id": item_id,
            "filter_id": filter_id,
            "status": "pending",
        })

    async def broadcast_buy_result(self, item_id: str, success: bool, price, error, user_id: int) -> None:
        await self.send_to_user(user_id, "buy_result", {
            "item_id": item_id,
            "status": "success" if success else "failed",
            "price": price,
            "error": error,
        })

    async def broadcast_bot_status(self, status: dict) -> None:
        await self.broadcast("bot_status", status)

    async def broadcast_log(self, level: str, message: str, category: str = "general", user_id: Optional[int] = None) -> None:
        if user_id is not None:
            await self.send_to_user(user_id, "log", {"level": level, "message": message, "category": category})
        else:
            # Global log (admin/bot events) → broadcast to all
            await self.broadcast("log", {"level": level, "message": message, "category": category})

    async def broadcast_auth_error(self, message: str = "Session expired") -> None:
        await self.broadcast("auth_error", {"message": message})

    @property
    def connection_count(self) -> int:
        total = sum(len(v) for v in self._user_connections.values())
        return total + len(self._anon_connections)


# Global singleton
ws_manager = WebSocketManager()
