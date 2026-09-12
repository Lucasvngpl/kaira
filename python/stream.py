"""EEG acquisition: synthetic noise, LSL receive, or BrainFlow direct.

Owner: Aarnav (LSL plumbing wired by the scaffold, 2026-09-12).

The venue path is LSL: the eego host software broadcasts, we receive on
any OS. BrainFlow direct-to-amp stays as a Windows-only fallback. The
synthetic generator keeps everything runnable with no hardware at all.

Interface (fixed - session.py, features.py and the API build against it):
    get_window(seconds) -> np.ndarray   # (n_channels, n_samples), microvolts
    connect() / release()
    ch_names: list[str]
    fs: int
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from brainflow.board_shim import BoardIds, BoardShim, BrainFlowInputParams

# Flipping this single constant (or passing --synthetic/--no-synthetic to the
# API) is the whole synthetic -> real switch. api/main.py writes it at startup.
SYNTHETIC: bool = True

# How real data arrives when SYNTHETIC is off. "lsl" receives the stream the
# eego host software broadcasts (Network operations -> enable LSL) and works
# on any OS; "brainflow" drives the amp directly and is Windows-only. The
# organizers' guidance (Discord, 2026-09-12: the venue amp is an eego 24
# EE-511, "if you're an LSL wizard, you can stream in real time", ANT likely
# not BrainFlow compatible) makes LSL the primary path. api/main.py sets
# this from KAIRA_SOURCE / --source.
SOURCE: str = "lsl"

fs: int = 512  # confirmed by the rig's own .cnt recordings; LSL overrides from stream metadata

# The 64-channel order as the rig itself writes it (read from the EO-EC
# .cnt header, 2026-09-12). LSL replaces this with the live stream's own
# labels at connect - the EE-511 sends 24.
ch_names: list[str] = [
    "Fp1", "Fpz", "Fp2", "F7", "F3", "Fz", "F4", "F8",
    "FC5", "FC1", "FC2", "FC6", "M1", "T7", "C3", "Cz",
    "C4", "T8", "M2", "CP5", "CP1", "CP2", "CP6", "P7",
    "P3", "Pz", "P4", "P8", "POz", "O1", "O2", "EOG",
    "AF7", "AF3", "AF4", "AF8", "F5", "F1", "F2", "F6",
    "FC3", "FCz", "FC4", "C5", "C1", "C2", "C6", "CP3",
    "CP4", "P5", "P1", "P2", "P6", "PO5", "PO3", "PO4",
    "PO6", "FT7", "FT8", "TP7", "TP8", "PO7", "PO8", "Oz",
]

_rng = np.random.default_rng()  # noise source for the synthetic path only

_board: BoardShim | None = None
_eeg_rows: list[int] | None = None  # row indices of ch_names within BrainFlow's raw data array (real path only)


def _connect_lsl(name_prefix: str | None = None) -> None:
    """Receive the eego host's LSL broadcast: resolve the EEG stream, adopt
    ITS geometry (fs, channel count, labels - the EE-511 has 24 channels,
    not our recorded 64, so nothing here may assume a count), and pull
    samples into a ring buffer on a background thread. get_window() then
    reads the most recent slice, same contract as every other source.

    name_prefix narrows to streams whose name starts with it - the UI's
    LIVE mode passes "EE511" so a dummy rehearsal stream can never pass
    as the real amplifier."""
    global fs, ch_names, _lsl_ring, _lsl_write, _lsl_filled, _lsl_generation, lsl_name
    from pylsl import StreamInlet, resolve_streams

    # Full scan, never first-answer: resolve_streams waits out the whole
    # window and returns EVERY broadcast, so a dummy answering fast can
    # never shadow the real amp when both are on the air. Prefer streams
    # that declare type EEG; accept any multi-channel one otherwise (the
    # eego host may label its type differently).
    streams = resolve_streams(wait_time=3.0)
    names = [s.name() for s in streams]
    if name_prefix:
        found = [s for s in streams if s.name().startswith(name_prefix)]
        if not found:
            seen = f"saw {names}" if names else "saw no streams at all"
            raise RuntimeError(f"no LSL stream named {name_prefix}* - {seen}. Is the eego software streaming with LSL enabled, on this network?")
    else:
        eeg = [s for s in streams if s.type() == "EEG" and s.channel_count() >= 8]
        found = eeg or [s for s in streams if s.channel_count() >= 8]
        if not found:
            raise RuntimeError("no LSL stream found - is 'enable LSL' on in the eego software, and are both machines on the same network?")
    inlet = StreamInlet(found[0], max_buflen=60)
    lsl_name = found[0].name()
    info = inlet.info()
    fs = int(round(info.nominal_srate()))
    n_ch = info.channel_count()
    if fs <= 0:
        raise RuntimeError(f"stream {found[0].name()!r} declares no fixed sampling rate - cannot window it; check the eego LSL settings")
    labels = []
    ch = info.desc().child("channels").child("channel")
    while not ch.empty():
        labels.append(ch.child_value("label"))
        ch = ch.next_sibling("channel")
    if len(labels) == n_ch:
        ch_names = labels
    else:
        raise RuntimeError(f"LSL stream has {n_ch} channels but {len(labels)} labels - need the pinout metadata to pick channels by name")
    missing = [c for c in ("F3", "Fz", "F4", "P3", "Pz", "P4") if c not in ch_names]
    if missing:
        raise RuntimeError(f"LSL montage is missing {missing} - features.py needs them; check the cap pinout and adjust features.FRONTAL/PARIETAL with the team")
    print(f"LSL connected: {n_ch} ch @ {fs} Hz, labels {ch_names[:6]}...")

    _lsl_ring = np.zeros((n_ch, fs * 60))  # 60 s of history, plenty for a 2 s window
    _lsl_write = 0
    _lsl_filled = 0
    _lsl_generation += 1  # a reconnect makes every older pull thread retire itself
    my_generation = _lsl_generation

    # Insurance recorder: everything received is also written to disk, so a
    # forgotten LabRecorder never costs the team a recording. One file per
    # session (the API rotates on session start/end); "idle" covers the
    # stretches in between, so the record stays gap-free.
    _open_recording("idle")

    def _pull() -> None:
        global _lsl_write, _lsl_filled
        import time as _t
        last_data = _t.monotonic()
        while my_generation == _lsl_generation:
            chunk, _ = inlet.pull_chunk(timeout=1.0)
            if not chunk:
                if _t.monotonic() - last_data > 3.0:
                    print(f"LSL: no samples from {lsl_name} for {_t.monotonic() - last_data:.0f}s - stream stalled?")
                    last_data = _t.monotonic()  # log every ~3s, not every loop
                continue
            last_data = _t.monotonic()
            arr = np.asarray(chunk, dtype=float).T  # (n_ch, n_new)
            with _rec_lock:
                if _rec["file"] is not None:
                    arr.T.astype(np.float32).tofile(_rec["file"])
                    _rec["file"].flush()  # a crash loses at most the in-flight chunk
            n_new = arr.shape[1]
            cap = _lsl_ring.shape[1]
            for k in range(n_new):  # ring write; chunks are small (<= a few hundred samples)
                _lsl_ring[:, (_lsl_write + k) % cap] = arr[:, k]
            _lsl_write = (_lsl_write + n_new) % cap
            _lsl_filled = min(cap, _lsl_filled + n_new)
        with _rec_lock:
            if _rec["file"] is not None:
                _rec["file"].close()
                _rec["file"] = None

    import threading
    threading.Thread(target=_pull, daemon=True).start()


_lsl_ring = None
_lsl_write = 0
_lsl_filled = 0
_lsl_generation = 0
lsl_name: str | None = None  # name of the connected LSL stream, for display

import threading

_rec_lock = threading.Lock()
_rec: dict = {"file": None}


def _open_recording(tag: str) -> None:
    import json
    import time as _time
    rec_dir = Path(__file__).resolve().parent.parent / "data" / "recordings"
    rec_dir.mkdir(parents=True, exist_ok=True)
    base = f"{lsl_name}-{_time.strftime('%Y%m%d-%H%M%S')}-{tag}"
    (rec_dir / f"{base}.json").write_text(json.dumps(
        {"stream": lsl_name, "fs": fs, "ch_names": ch_names, "tag": tag,
         "t0_unix": _time.time(), "layout": "frames (n_samples, n_ch) float32"}))
    _rec["file"] = open(rec_dir / f"{base}.f32", "ab")
    print(f"tee-recording to {base}.f32")


def rotate_recording(tag: str) -> None:
    """Close the current tee file and start a new one - the API calls this
    at session start (tag = patient ref) and end (back to idle). No-op when
    nothing is being received."""
    with _rec_lock:
        if _rec["file"] is None:
            return
        _rec["file"].close()
        _open_recording(tag)


def connect(name_prefix: str | None = None) -> None:
    """Open the signal source per SYNTHETIC/SOURCE. Synthetic needs nothing:
    get_window() generates directly (BrainFlow's own synthetic board has the
    wrong geometry, 16 ch @ 250 Hz, so we do not route through it)."""
    global _board, _eeg_rows, fs
    if SYNTHETIC:
        return  # nothing to open; get_window() generates data directly
    if SOURCE == "lsl":
        _connect_lsl(name_prefix)
        return
    # Integration fix (2026-09-12): the board id must be chosen HERE, not at
    # import - api/main.py flips SYNTHETIC after importing this module, so a
    # module-level constant would freeze the wrong board on the real path.
    board_id = BoardIds.ANT_NEURO_EE_225_BOARD
    params = BrainFlowInputParams()
    _board = BoardShim(board_id, params)
    _board.prepare_session()
    try:
        _board.config_board("sampling_rate:512")  # UNVERIFIED - see unresolved item 1
    except Exception as exc:
        _board.release_session()
        _board = None
        raise RuntimeError(
            "config_board('sampling_rate:512') failed - confirm the exact "
            "config string against the ANT Neuro / eego SDK manual before "
            "retrying (see HANDOFF and unresolved item 1 in this file's docstring)"
        ) from exc
    _board.start_stream()
    fs = BoardShim.get_sampling_rate(board_id)
    if fs != 512:
        _board.stop_stream()
        _board.release_session()
        _board = None
        raise RuntimeError(
            f"expected 512 Hz after config_board, board reports {fs} Hz - "
            "stop and confirm with HANDOFF before proceeding (unresolved item 1)"
        )
    _eeg_rows = BoardShim.get_eeg_channels(board_id)
    if len(_eeg_rows) != len(ch_names):
        _board.stop_stream()
        _board.release_session()
        _board = None
        raise RuntimeError(
            f"BrainFlow reports {len(_eeg_rows)} EEG rows for this board id, "
            f"but ch_names has {len(ch_names)} entries - the board id, cap "
            "config, or ch_names placeholder disagree; do not proceed blind"
        )


def release() -> None:
    """Stop and release the real board session. No-op for SYNTHETIC."""
    global _board
    if _board is None:
        return
    try:
        _board.stop_stream()
    finally:
        _board.release_session()
        _board = None


def get_window(seconds: float) -> np.ndarray:
    """The most recent `seconds` of EEG, (n_channels, n_samples), microvolts.

    Early in a session the buffer may hold less than requested; callers get
    a shorter window. Values are NOT zero-centred (the eego is DC-coupled,
    ~+4800 uV offset); preprocess owns the high-pass."""
    n_samples = int(round(seconds * fs))
    if not SYNTHETIC and SOURCE == "lsl" and _lsl_ring is not None:
        cap = _lsl_ring.shape[1]
        n = min(n_samples, _lsl_filled)
        idx = (np.arange(_lsl_write - n, _lsl_write) % cap)
        return _lsl_ring[:, idx]
    if SYNTHETIC or _board is None:
        return 4800.0 + _rng.normal(0.0, 10.0, size=(len(ch_names), n_samples))
    raw = _board.get_current_board_data(n_samples)
    return raw[_eeg_rows, :]


def pick(data: np.ndarray, names: list[str]) -> np.ndarray:
    """Return only the rows of `data` whose channel names are in `names`.

    Indexes via the module-level ch_names (assumes `data`'s rows are still in
    that order, i.e. this is meant to run on a stream.get_window() output
    before preprocess.clean() reorders/drops anything - see preprocess.py's
    own docstring about clean()'s output shape, which is a separate open
    question).
    """
    unknown = [n for n in names if n not in ch_names]
    if unknown:
        raise ValueError(f"unknown channel name(s): {unknown}")
    rows = [ch_names.index(n) for n in names]
    return data[rows, :]
