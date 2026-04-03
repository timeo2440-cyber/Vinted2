import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import select
from database import init_db, AsyncSessionLocal, Setting
from vinted.client import VintedClient
from vinted.auth import parse_cookie_string
from vinted.account_manager import AccountManager
from bot.poller import ItemPoller
from ws.manager import ws_manager
from api import filters, settings, bot_control, history, stats, logs, vinted_meta, accounts
from config import settings as app_settings
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()

    # Build primary Vinted client (used for polling)
    client = VintedClient(app_settings.vinted_base_url)
    await client.__aenter__()

    # Load saved cookies for primary client, then always fetch CSRF/anonymous session
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Setting).where(Setting.key == "vinted_cookies"))
        row = result.scalar_one_or_none()
        if row and row.value:
            cookies = parse_cookie_string(row.value)
            if cookies:
                client.set_cookies(cookies)

    # Always initialize Vinted session (anonymous if no saved cookies)
    # This fetches XSRF-TOKEN and sets anonymous session cookies
    await client.fetch_csrf_token()

    # Auto-repair: any account with cookies stored but marked as expired → restore to authenticated.
    # We trust saved cookies unconditionally; the user explicitly pasted them.
    # Cloudflare often blocks session validation which wrongly marks accounts as expired.
    async with AsyncSessionLocal() as db:
        from sqlalchemy import update
        from database import Account
        await db.execute(
            update(Account)
            .where(Account.cookies != None, Account.cookies != "", Account.is_authenticated == False)
            .values(is_authenticated=True)
        )
        await db.commit()

    # Initialize account manager (one client per saved account)
    account_manager = AccountManager(app_settings.vinted_base_url)
    await account_manager.initialize()

    # Create poller (passes account_manager to BuyEngine for rotation)
    poller = ItemPoller(client, ws_manager, account_manager)

    # Store on app state
    app.state.vinted_client = client
    app.state.poller = poller
    app.state.ws_manager = ws_manager
    app.state.account_manager = account_manager

    # Auto-start: the bot always runs 24/7
    await poller.start()

    yield

    # Shutdown
    await poller.stop()
    await account_manager.close_all()
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
app.include_router(vinted_meta.router)
app.include_router(accounts.router)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        poller: ItemPoller = websocket.app.state.poller
        status = await poller.get_status()
        await ws_manager.broadcast_bot_status(status)
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if msg == "ping":
                    await websocket.send_text('{"type":"pong"}')
            except asyncio.TimeoutError:
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
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/", include_in_schema=False)
async def serve_index():
    index = os.path.join(app_settings.frontend_dir, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return {"error": "Frontend not found."}


@app.get("/{path:path}", include_in_schema=False)
async def serve_spa(path: str):
    if path.startswith("api/") or path.startswith("ws"):
        from fastapi import HTTPException
        raise HTTPException(404)
    file_path = os.path.join(app_settings.frontend_dir, path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    return FileResponse(os.path.join(app_settings.frontend_dir, "index.html"))
