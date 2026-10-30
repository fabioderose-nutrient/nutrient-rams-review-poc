"""RAMS Reviewer: FastAPI backend, packaged for Azure Container Apps.

Serves the frontend, the sample documents, and the AI review endpoint backed
by the Nutrient Python SDK (structured extraction with native confidence and
source bounding boxes).
"""

import asyncio
import json
import os
import threading
import time
from pathlib import Path

import httpx
import nutrient_sdk as ns
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import extraction

ROOT = Path(__file__).resolve().parent.parent
INPUTS = Path(os.environ.get("INPUT_DIR") or ROOT / "inputs")
OUTPUTS = Path(os.environ.get("OUTPUT_DIR") or ROOT / "outputs")
FRONTEND = ROOT / "frontend"
OUTPUTS.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="RAMS Reviewer")

_page_counts = {}
_progress = {}
_progress_lock = threading.Lock()


@app.middleware("http")
async def no_cache(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache"
    return response


def _safe_input(name):
    if not name or "/" in name or "\\" in name or ".." in name:
        return None
    path = INPUTS / name
    return path if path.is_file() else None


def _page_count(path):
    stamp = path.stat().st_mtime
    cached = _page_counts.get(path.name)
    if cached and cached[0] == stamp:
        return cached[1]
    extraction._ensure_sdk()
    pages = 0
    try:
        doc = ns.Document.open(str(path))
        try:
            pages = doc.get_page_count()
        finally:
            doc.close()
    except Exception:
        pages = 0
    _page_counts[path.name] = (stamp, pages)
    return pages


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/config")
def config():
    """Browser configuration: the Web SDK license key (empty = evaluation mode)."""
    return {"web_sdk_license_key": os.environ.get("NUTRIENT_WEB_SDK_LICENSE_KEY", "")}


OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")


@app.post("/internal/ollama/v1/chat/completions")
async def ollama_relay(request: Request):
    """Relay between the SDK and a local Ollama server (AI_PROVIDER=ollama).

    The SDK asks for token log-probabilities to compute its confidence score;
    Ollama's answer to that request is rejected by the SDK, so the relay drops
    it and the SDK falls back to its grounding score. It also caps the answer
    length, because a small model can loop inside a JSON array until the
    context limit. Only reachable from the machine itself."""
    if request.client is None or request.client.host not in ("127.0.0.1", "::1"):
        raise HTTPException(403, "Internal endpoint")
    body = await request.json()
    body.pop("logprobs", None)
    body.pop("top_logprobs", None)
    body.setdefault("max_tokens", int(os.environ.get("OLLAMA_MAX_TOKENS", "2000")))
    body.setdefault("presence_penalty", float(os.environ.get("OLLAMA_PRESENCE_PENALTY", "0.6")))

    async def forward():
        async with httpx.AsyncClient(timeout=1200.0) as client:
            return await client.post(f"{OLLAMA_URL}/v1/chat/completions", json=body)

    # Shielded: when the SDK gives up, the Ollama call still completes instead
    # of leaving the model runner busy with an abandoned request.
    upstream = await asyncio.shield(asyncio.ensure_future(forward()))
    return JSONResponse(upstream.json(), status_code=upstream.status_code)


@app.get("/api/files")
def files():
    result = []
    for path in sorted(INPUTS.glob("*.pdf"), key=lambda p: p.name.lower()):
        result.append({"name": path.name, "pages": _page_count(path)})
    return result


@app.get("/api/pdf")
def pdf(name: str):
    path = _safe_input(name)
    if path is None:
        raise HTTPException(404, "Unknown file")
    return FileResponse(path, media_type="application/pdf")


@app.get("/api/progress")
def progress(job: str):
    with _progress_lock:
        state = _progress.get(job)
    if not state:
        return {"known": False}
    return {"known": True, **state}


@app.post("/api/process")
def process(file: str, job: str | None = None):
    path = _safe_input(file)
    if path is None:
        raise HTTPException(404, "Unknown file")

    def report(stage, done, total):
        if job:
            with _progress_lock:
                _progress[job] = {"stage": stage, "done": done, "total": total,
                                  "started": _progress.get(job, {}).get("started", time.time())}

    report("Opening the document", 0, 2)
    started = time.time()
    try:
        result = extraction.process_document(str(path), progress=report)
    except Exception as exc:
        raise HTTPException(500, f"Processing failed: {exc}") from exc
    finally:
        if job:
            with _progress_lock:
                _progress.pop(job, None)

    result["file"] = path.name
    result["processing_seconds"] = round(time.time() - started, 1)
    try:
        (OUTPUTS / f"{path.name}.json").write_text(json.dumps(result, indent=1))
    except OSError:
        pass
    return JSONResponse(result)


app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
