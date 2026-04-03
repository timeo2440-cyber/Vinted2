import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import select, update
from database import init_db, AsyncSessionLocal, Setting, Account
from vinted.client import VintedClient
from vinted.auth import parse_cookie_string
from vinted.account_manager import AccountManager
from bot.poller import ItemPoller
from ws.manager import ws_manager
from api import filters, settings, bot_control, history, stats, logs, vinted_meta, accounts
from api.auth import router as auth_router
from api.admin import router as admin_router
from config import settings as app_settings
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def _ensure_admin():
    """Create default admin account at first startup if no user exists."""
    import os, bcrypt as _bcrypt
    from database import User
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).limit(1))
        if result.scalar_one_or_none():
            return  # Already have users

        admin_email = os.environ.get("ADMIN_EMAIL", "admin@vintedbot.com")
        admin_password = os.environ.get("ADMIN_PASSWORD", "Admin1234!")
        password_hash = _bcrypt.hashpw(admin_password.encode()[:72], _bcrypt.gensalt()).decode()
        admin = User(
            email=admin_email,
            password_hash=password_hash,
            role="admin",
            plan="unlimited",
        )
        db.add(admin)
        await db.commit()
        logging.getLogger("main").info(
            f"\n"
            f"{'='*50}\n"
            f"  COMPTE ADMIN CRÉÉ AUTOMATIQUEMENT\n"
            f"  Email    : {admin_email}\n"
            f"  Password : {admin_password}\n"
            f"  → Connectez-vous sur http://localhost:8000\n"
            f"{'='*50}"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────────
    await init_db()
    await _ensure_admin()

    # Build primary Vinted client (used for polling)
    client = VintedClient(app_settings.vinted_base_url)
    await client.__aenter__()

    # Load saved cookies for primary client
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Setting).where(Setting.key == "vinted_cookies"))
        row = result.scalar_one_or_none()
        if row and row.value:
            cookies = parse_cookie_string(row.value)
            if cookies:
                client.set_cookies(cookies)

    # Always fetch CSRF/anonymous session token
    await client.fetch_csrf_token()

    # Auto-repair: any account that has cookies but is marked expired → restore to authenticated
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Account)
            .where(Account.cookies != None, Account.cookies != "", Account.is_authenticated == False)
            .values(is_authenticated=True)
        )
        await db.commit()

    # Initialize per-user account clients
    account_manager = AccountManager(app_settings.vinted_base_url)
    await account_manager.initialize()

    # Create poller
    poller = ItemPoller(client, ws_manager, account_manager)

    # Store on app state
    app.state.vinted_client = client
    app.state.poller = poller
    app.state.ws_manager = ws_manager
    app.state.account_manager = account_manager

    # Auto-start: bot always runs 24/7
    await poller.start()

    yield

    # ── Shutdown ───────────────────────────────────────────────────────────────
    await poller.stop()
    await account_manager.close_all()
    await client.__aexit__(None, None, None)


app = FastAPI(
    title="Vinted AutoBot",
    description="Auto-buy bot for Vinted — SaaS multi-tenant",
    version="2.0.0",
    lifespan=lifespan,
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(filters.router)
app.include_router(settings.router)
app.include_router(bot_control.router)
app.include_router(history.router)
app.include_router(stats.router)
app.include_router(logs.router)
app.include_router(vinted_meta.router)
app.include_router(accounts.router)


# ── WebSocket ──────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(default=""),
):
    """
    Authenticated WebSocket.
    Client sends ?token=<jwt> so we can route events to the right user.
    """
    user_id = None
    if token:
        try:
            import jwt as _jwt
            payload = _jwt.decode(token, app_settings.secret_key, algorithms=["HS256"])
            user_id = int(payload["sub"])
        except Exception:
            user_id = None

    await ws_manager.connect(websocket, user_id=user_id)
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
        ws_manager.disconnect(websocket, user_id=user_id)


# ── Static / SPA ───────────────────────────────────────────────────────────────
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
