"""FastAPI layer: thin HTTP wrapper around python/session.py.

No logic lives here beyond translation: JSON in, session method, JSON out,
plus error mapping. Sessions are held in a process-local dict (no database,
per the brief) - restarting the server forgets them, which is fine for a
buildathon demo.

Run from the repo root:
    python api/main.py                  # synthetic mode (default)
    python api/main.py --no-synthetic   # real hardware (Windows + eego attached)
or equivalently: uvicorn api.main:app (KAIRA_SYNTHETIC=0 for real mode).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# python/ is a plain folder, not a package (prescribed repo layout), so put it
# on sys.path instead of inventing package plumbing the team would trip over.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))

import math

import decide  # noqa: E402
import session as session_mod  # noqa: E402
import stream  # noqa: E402
import tasks  # noqa: E402
from session import Session, SessionStateError  # noqa: E402

# Synthetic vs real hardware is a single switch on stream (HANDOFF: "swaps
# the board id"). Default ON so the demo never needs an amplifier.
stream.SYNTHETIC = os.environ.get("KAIRA_SYNTHETIC", "1") != "0"

# Rehearsal knob: the protocol baseline is 3 minutes, which is correct for a
# patient and painful for a dev click-through. KAIRA_BASELINE_SECONDS=15
# shortens it without code edits; unset means the real protocol.
session_mod.BASELINE_SECONDS = float(
    os.environ.get("KAIRA_BASELINE_SECONDS", session_mod.BASELINE_SECONDS)
)

app = FastAPI(title="Kaira", description="Adaptive cognitive assessment - demo API")

# The React dev server is the only client; keep CORS scoped to it.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: dict[str, Session] = {}


# Session raises typed errors; map them to HTTP once, centrally.
@app.exception_handler(ValueError)
async def _bad_request(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(SessionStateError)
async def _wrong_phase(_: Request, exc: SessionStateError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


class StartRequest(BaseModel):
    patient_ref: str = Field(min_length=1)
    domain: str


class AnswerRequest(BaseModel):
    task_id: str
    result: Literal["correct", "incorrect", "timeout"]
    elapsed_seconds: float = Field(ge=0)


def _get(session_id: str) -> Session:
    try:
        return sessions[session_id]
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown session {session_id!r}")


@app.get("/")
def root() -> dict:
    return {
        "app": "kaira",
        "synthetic": stream.SYNTHETIC,
        "domains": {d: tasks.has_tasks(d) for d in tasks.domains()},
        # The UI shades the live sparkline with the effort band; multiples are
        # DERIVED from decide's log thresholds so display and rule cannot drift.
        "band": [round(math.exp(decide.LOW_LOAD), 2), round(math.exp(decide.HIGH_LOAD), 2)],
    }


@app.post("/session/start")
def start(req: StartRequest) -> dict:
    s = session_mod.begin(req.patient_ref, req.domain)
    sessions[s.id] = s
    return {"session_id": s.id, "baseline_seconds": session_mod.BASELINE_SECONDS}


@app.get("/session/{session_id}/baseline-status")
def baseline_status(session_id: str) -> dict:
    return _get(session_id).baseline_status()


@app.get("/session/{session_id}/next-task")
def next_task(session_id: str) -> dict:
    return _get(session_id).next_task()


@app.post("/session/{session_id}/answer")
def answer(session_id: str, req: AnswerRequest) -> dict:
    return _get(session_id).submit_answer(req.task_id, req.result, req.elapsed_seconds)


@app.get("/session/{session_id}/report")
def report(session_id: str) -> dict:
    return _get(session_id).report()


@app.get("/session/{session_id}/live-load")
def live_load(session_id: str) -> dict:
    return _get(session_id).live_load()


if __name__ == "__main__":
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="Kaira API")
    parser.add_argument(
        "--synthetic",
        action=argparse.BooleanOptionalAction,
        # Inherit the env var (already applied above) so KAIRA_SYNTHETIC=0
        # works on this launch path too; the flag still wins when passed.
        default=stream.SYNTHETIC,
        help="synthetic board (default) vs real eego hardware",
    )
    parser.add_argument("--host", default="127.0.0.1")
    # 8300, not 8000: Django dev servers (UQwest included) squat on 8000.
    parser.add_argument("--port", type=int, default=8300)
    args = parser.parse_args()

    stream.SYNTHETIC = args.synthetic
    uvicorn.run(app, host=args.host, port=args.port)
