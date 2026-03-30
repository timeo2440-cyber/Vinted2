import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import select
from database import init_db, AsyncSessionLocal, Setting
from vinted.client import VintedClient
from vinted.auth import parse_cookie_string
from bot.poller import ItemPoller
from ws.manager import ws_manager
from api import filters, settings, bot_control, history, stats, logs
from config import settings as app_settings
import os


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()

    # Build Vinted client
    client = VintedClient(app_settings.vinted_base_url)
    await client.__aenter__()

    # Load saved cookies
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Setting).where(Setting.key == "vinted_cookies"))
        row = result.scalar_one_or_none()
        if row and row.value:
            cookies = parse_cookie_string(row.value)
            if cookies:
                client.set_cookies(cookies)
                await client.fetch_csrf_token()

    # Create poller
    poller = ItemPoller(client, ws_manager)

    # Store on app state
    app.state.vinted_client = client
    app.state.poller = poller
    app.state.ws_manager = ws_manager

    yield

    # Shutdown
    await poller.stop()
    await client.__aexit__(None, None, None)


app = FastAPI(
    title="Vinted AutoBot",
    description="Auto-buy bot for Vinted with real-time web interface",
    version="1.0.0",
    lifespan=lifespan,
)

# Register API routers
app.include_router(filters.router)
app.include_router(settings.router)
app.include_router(bot_control.router)
app.include_router(history.router)
app.include_router(stats.router)
app.include_router(logs.router)


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Send initial bot status
        poller: ItemPoller = websocket.app.state.poller
        status = await poller.get_status()
        await ws_manager.broadcast_bot_status(status)

        # Keep connection alive and listen for pings
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if msg == "ping":
                    await websocket.send_text('{"type":"pong"}')
            except asyncio.TimeoutError:
                # Send a keepalive ping
                try:
                    await websocket.send_text('{"type":"ping"}')
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        ws_manager.disconnect(websocket)


# Serve frontend static files
frontend_dir = app_settings.frontend_dir
if os.path.isdir(frontend_dir):
    # Mount static FIRST so CSS/JS/assets are served directly without hitting route handlers
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/", include_in_schema=False)
async def serve_index():
    index = os.path.join(app_settings.frontend_dir, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return {"error": "Frontend not found. Make sure the frontend/ folder exists."}


@app.get("/{path:path}", include_in_schema=False)
async def serve_spa(path: str):
    # Never intercept API or WS paths
    if path.startswith("api/") or path.startswith("ws"):
        from fastapi import HTTPException
        raise HTTPException(404)
    file_path = os.path.join(app_settings.frontend_dir, path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    return FileResponse(os.path.join(app_settings.frontend_dir, "index.html"))
