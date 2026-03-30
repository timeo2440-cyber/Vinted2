from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/bot", tags=["bot"])


@router.post("/start")
async def start_bot(request: Request):
    poller = request.app.state.poller
    if poller.running:
        return {"ok": True, "message": "Bot already running"}
    await poller.start()
    return {"ok": True, "message": "Bot started"}


@router.post("/stop")
async def stop_bot(request: Request):
    poller = request.app.state.poller
    if not poller.running:
        return {"ok": True, "message": "Bot already stopped"}
    await poller.stop()
    return {"ok": True, "message": "Bot stopped"}


@router.get("/status")
async def bot_status(request: Request):
    poller = request.app.state.poller
    status = await poller.get_status()
    # Check auth
    from vinted.auth import validate_session
    client = request.app.state.vinted_client
    auth = await validate_session(client)
    status["authenticated"] = auth["authenticated"]
    status["username"] = auth.get("username")
    status["ws_connections"] = request.app.state.ws_manager.connection_count
    return status
