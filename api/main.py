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

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# python/ is a plain folder, not a package (prescribed repo layout), so put it
# on sys.path instead of inventing package plumbing the team would trip over.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))

import math
import socket
import tempfile
import threading
import time

import numpy as np  # noqa: E402

import decide  # noqa: E402
import features  # noqa: E402
import preprocess  # noqa: E402
import session as session_mod  # noqa: E402
import stream  # noqa: E402
import tasks  # noqa: E402
from session import Session, SessionStateError  # noqa: E402

# Synthetic vs real hardware is a single switch on stream (HANDOFF: "swaps
# the board id"). Default ON so the demo never needs an amplifier.
stream.SYNTHETIC = os.environ.get("KAIRA_SYNTHETIC", "1") != "0"

# Real-mode transport: "lsl" (eego host broadcasts; any OS) or "brainflow"
# (amp plugged into this machine; Windows only). LSL is the default per the
# organizers' guidance.
stream.SOURCE = os.environ.get("KAIRA_SOURCE", stream.SOURCE)

# Rehearsal knob: the protocol baseline is 3 minutes, which is correct for a
# patient and painful for a dev click-through. KAIRA_BASELINE_SECONDS=15
# shortens it without code edits; unset means the real protocol.
session_mod.BASELINE_SECONDS = float(
    os.environ.get("KAIRA_BASELINE_SECONDS", session_mod.BASELINE_SECONDS)
)

from contextlib import asynccontextmanager

# --- Signal-source manager ---------------------------------------------------
# TEST: dummy LSL stream if broadcasting, else the synthetic generator;
# never blocks. LIVE: only a stream named EE511* (the real amp), retrying
# until it appears. One state dict, one background thread per attempt.

LIVE_PREFIX = ""

# The patient display proves it is alive by polling; the clinician cannot
# start a session no patient screen would show. 5 s of silence = gone.
_patient_seen = 0.0
PATIENT_TIMEOUT = 5.0


def _patient_connected() -> bool:
    return (time.time() - _patient_seen) > 0 and (time.time() - _patient_seen) < PATIENT_TIMEOUT


def _lan_ip() -> str:
    """This machine's address on the local network (hotspot). The UDP
    connect never sends a packet; it just asks the OS which interface would
    route there, which works with or without real internet."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()

source = {
    "mode": "test",  # test | live
    "selected": None,  # explicit stream name chosen from the picker; None = auto
    "connected": False,
    "stream": None,  # LSL stream name when connected over LSL
    "fs": None,
    "channels": None,
    "detail": "",
    "attempting": False,
}
_attempt_lock = threading.Lock()


def _attempt(mode: str) -> None:
    """One connection attempt on a worker thread; LIVE retries every few
    seconds while it stays selected and unconnected."""
    with _attempt_lock:
        if source["mode"] != mode:
            return  # the user switched modes while this attempt waited its turn
        source["attempting"] = True
        try:
            picked = source["selected"]
            if picked:
                # An explicit pick from the dropdown wins over auto rules.
                stream.SOURCE = "lsl"
                stream.SYNTHETIC = False
                stream.connect(name_prefix=picked)
                source.update(connected=True, stream=stream.lsl_name,
                              fs=stream.fs, channels=len(stream.ch_names),
                              detail=f"selected stream: {stream.lsl_name}")
            elif mode == "test":
                stream.SOURCE = "lsl"
                stream.SYNTHETIC = False
                try:
                    stream.connect()  # any stream: a dummy makes a transport rehearsal
                    source.update(connected=True, stream=stream.lsl_name,
                                  detail=f"dummy LSL stream: {stream.lsl_name}")
                except Exception:
                    stream.SYNTHETIC = True  # no dummy around: built-in generator
                    source.update(connected=True, stream=None, detail="synthetic generator")
                source.update(fs=stream.fs, channels=len(stream.ch_names))
            else:
                stream.SYNTHETIC = False
                stream.SOURCE = "lsl"
                stream.connect(name_prefix=LIVE_PREFIX)
                source.update(connected=True, stream=stream.lsl_name,
                              fs=stream.fs, channels=len(stream.ch_names), detail="")
        except Exception as exc:
            source.update(connected=False, stream=None, detail=str(exc))
        finally:
            source["attempting"] = False
        if source["mode"] != mode:
            # Mode flipped while we were connecting: our result describes the
            # wrong mode, so mark it stale rather than lie.
            source.update(connected=False, detail="connecting...")
    if mode == "live" and not source["connected"] and source["mode"] == "live":
        # Keep looking: the amp usually appears seconds after someone fixes
        # the checklist item the detail names.
        threading.Timer(5.0, _attempt, args=("live",)).start()


def set_mode(mode: str, selected: str | None = None) -> None:
    source["mode"] = mode
    source["selected"] = selected
    source["connected"] = False
    source["detail"] = "connecting..."
    threading.Thread(target=_attempt, args=(mode,), daemon=True).start()


@asynccontextmanager
async def _lifespan(app: FastAPI):
    if stream.SOURCE == "brainflow" and not stream.SYNTHETIC:
        # Fallback path: the amp is plugged into THIS machine (Windows).
        stream.connect()
    else:
        # LSL/synthetic: never block startup; apply the default mode and let
        # the manager connect in the background.
        set_mode("live" if not stream.SYNTHETIC else "test")
    yield
    stream.release()


app = FastAPI(title="Kaira", description="Adaptive cognitive assessment - demo API", lifespan=_lifespan)

# The UI reaches us through Vite's /api proxy, so its requests arrive
# same-origin and never consult this list. It stays for a client that calls
# this port directly, and keeping it scoped means such a call fails loudly.
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
        # "Demo signal" shows unless the connected stream IS the real amp,
        # however it was chosen (live auto-rule or explicit pick).
        "synthetic": not (source["connected"] and (source["stream"] or "").startswith(LIVE_PREFIX)),
        "domains": {d: tasks.has_tasks(d) for d in tasks.domains()},
        # No global band anymore: thresholds are z-scaled per patient, so the
        # live-load response carries each session's own display band.
    }


@app.get("/stream/status")
def stream_status() -> dict:
    return source


class ModeRequest(BaseModel):
    mode: Literal["test", "live"]
    # Exact stream name from /stream/list to pin; omitted = auto rules.
    name: str | None = None


@app.post("/stream/mode")
def stream_mode(req: ModeRequest) -> dict:
    set_mode(req.mode, req.name)
    return source


@app.get("/stream/list")
def stream_list() -> list[dict]:
    """Every LSL broadcast visible right now (a ~3 s scan), for the picker."""
    from pylsl import resolve_streams
    return [
        {"name": s.name(), "type": s.type(), "channels": s.channel_count(),
         "srate": int(s.nominal_srate()), "host": s.hostname()}
        for s in resolve_streams(wait_time=3.0)
    ]


@app.get("/net/info")
def net_info() -> dict:
    return {"ip": _lan_ip()}


@app.get("/patient/status")
def patient_status() -> dict:
    return {"connected": _patient_connected()}


@app.get("/session/current")
def session_current() -> dict:
    # Only the patient display polls this - it doubles as its heartbeat.
    global _patient_seen
    _patient_seen = time.time()
    for s in reversed(list(sessions.values())):
        if not s.ended:
            return {"session_id": s.id}
    return {"session_id": None}


@app.post("/session/start")
def start(req: StartRequest) -> dict:
    if source["mode"] == "live" and not source["connected"]:
        raise SessionStateError("live mode is selected but the amplifier is not connected yet")
    if not _patient_connected():
        raise SessionStateError("no patient screen is connected - scan the QR code on any device on this network")
    s = session_mod.begin(req.patient_ref, req.domain)
    sessions[s.id] = s
    return {"session_id": s.id, "baseline_seconds": session_mod.BASELINE_SECONDS}


@app.get("/session/{session_id}/baseline-status")
def baseline_status(session_id: str) -> dict:
    st = _get(session_id).baseline_status()
    st["previous_available"] = any(
        s.id != session_id and s._baseline_done for s in sessions.values()
    )
    return st


@app.post("/session/{session_id}/baseline-skip")
def baseline_skip(session_id: str) -> dict:
    # Demo-only: a real patient's baseline is protocol, not a waiting screen.
    if source["mode"] == "live":
        raise HTTPException(status_code=400, detail="baseline skip is only available in test mode")
    return _get(session_id).skip_baseline()


@app.get("/session/{session_id}/next-task")
def next_task(session_id: str) -> dict:
    return _get(session_id).next_task()


class TaskStartRequest(BaseModel):
    task_id: str


@app.post("/session/{session_id}/task-start")
def task_start(session_id: str, req: TaskStartRequest) -> dict:
    _get(session_id).start_task(req.task_id)
    return {"ok": True}


@app.post("/session/{session_id}/baseline-file")
async def baseline_file(session_id: str, file: UploadFile) -> dict:
    """Adopt a baseline from an uploaded resting recording (.cnt from the
    eego software, .npz from tools/record.py): run it through the real
    pipeline and take its mean/wobble as this session's baseline."""
    me = _get(session_id)
    raw = await file.read()
    suffix = Path(file.filename or "").suffix.lower()
    tmp = Path(tempfile.gettempdir()) / f"kaira-baseline{suffix}"
    tmp.write_bytes(raw)
    try:
        if suffix == ".npz":
            d = np.load(tmp, allow_pickle=False)
            windows, fs, names = d["windows"], int(d["fs"]), [str(c) for c in d["ch_names"]]
            data = np.concatenate(list(windows), axis=1)
        elif suffix == ".cnt":
            try:
                import mne
            except ImportError:
                raise HTTPException(status_code=400, detail="reading .cnt needs mne on this machine: pip install mne")
            r = mne.io.read_raw_ant(tmp, preload=True, verbose="ERROR")
            data, fs, names = r.get_data() * 1e6, int(r.info["sfreq"]), r.ch_names
        else:
            raise HTTPException(status_code=400, detail=f"unsupported file type {suffix!r} - drop a .cnt or .npz recording")

        preprocess.calibrate(data[:, : min(fs * 20, data.shape[1])], fs, names)
        win = fs * 2
        loads = []
        for start in range(0, data.shape[1] - win + 1, win):
            cleaned, trusted = preprocess.clean(data[:, start : start + win], fs, names)
            if trusted:
                loads.append(features.cognitive_load(cleaned, fs, names))
        if len(loads) < 5:
            raise HTTPException(status_code=400, detail=f"only {len(loads)} trusted windows in that file - too little to be a baseline")
        import statistics
        return me.adopt_baseline_values(
            statistics.fmean(loads), statistics.stdev(loads), data.shape[1] / fs
        )
    finally:
        tmp.unlink(missing_ok=True)


@app.post("/session/{session_id}/baseline-reuse")
def baseline_reuse(session_id: str) -> dict:
    me = _get(session_id)
    # The most recent other session whose baseline finished.
    for other in reversed(list(sessions.values())):
        if other.id != session_id and other._baseline_done:
            return me.adopt_baseline(other)
    raise HTTPException(status_code=404, detail="no earlier baseline exists in this server session")


@app.post("/session/{session_id}/answer")
def answer(session_id: str, req: AnswerRequest) -> dict:
    return _get(session_id).submit_answer(req.task_id, req.result, req.elapsed_seconds)


@app.get("/session/{session_id}/report")
def report(session_id: str) -> dict:
    return _get(session_id).report()


@app.get("/session/{session_id}/live-load")
def live_load(session_id: str) -> dict:
    return _get(session_id).live_load()


@app.get("/session/{session_id}/patient-view")
def patient_view(session_id: str) -> dict:
    global _patient_seen
    _patient_seen = time.time()
    return _get(session_id).patient_view()


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
    parser.add_argument("--source", choices=["lsl", "brainflow"], default=stream.SOURCE,
                        help="how real EEG arrives when --no-synthetic (default: lsl)")
    parser.add_argument("--host", default="127.0.0.1")
    # 8300, not 8000: Django dev servers (UQwest included) squat on 8000.
    parser.add_argument("--port", type=int, default=8300)
    args = parser.parse_args()

    stream.SYNTHETIC = args.synthetic
    stream.SOURCE = args.source
    uvicorn.run(app, host=args.host, port=args.port)
