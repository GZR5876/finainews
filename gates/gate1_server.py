"""
Gate 1: FastAPI server that serves candidates.html and receives selections.
Writes selections.json then shuts down. ~25 lines of real logic.
"""
import asyncio
import json
import os
import signal
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

SELECTIONS_PATH = Path(__file__).parent.parent / "data" / "selections.json"
CANDIDATES_HTML = Path(__file__).parent.parent / "data" / "candidates.html"

app = FastAPI()
_shutdown_event = asyncio.Event()


@app.get("/", response_class=HTMLResponse)
async def serve_candidates():
    return HTMLResponse(CANDIDATES_HTML.read_text())


@app.post("/submit")
async def receive_selections(request: Request):
    body = await request.json()  # {item_id: bool, ...}
    SELECTIONS_PATH.write_text(json.dumps(body, indent=2))
    _shutdown_event.set()
    return JSONResponse({"status": "saved", "count": sum(1 for v in body.values() if v)})


@app.get("/health")
async def health():
    return {"ok": True}


async def serve_until_submitted(host: str = "127.0.0.1", port: int = 8765):
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    serve_task = asyncio.create_task(server.serve())
    await _shutdown_event.wait()
    server.should_exit = True
    await serve_task


def wait_for_selections(host: str = "127.0.0.1", port: int = 8765) -> dict[int, bool]:
    """Blocking call: starts the server, waits for POST /submit, returns selections."""
    asyncio.run(serve_until_submitted(host, port))
    raw = json.loads(SELECTIONS_PATH.read_text())
    # Keys come in as strings from JSON
    return {int(k): bool(v) for k, v in raw.items()}
