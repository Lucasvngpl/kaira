"""EEG acquisition via BrainFlow.

Owner: Aarnav.

Verified hardware facts (HANDOFF.md section 3 - do not re-derive these):
  - Amplifier: ANT Neuro eego mylab 64, product code EE-225.
  - BrainFlow board id 36 = BoardIds.ANT_NEURO_EE_225_BOARD.
  - BrainFlow's ANT Neuro boards run on WINDOWS ONLY.
  - Cap: waveguard original CA-208, 64 channels, 10/10 layout.
  - Reference CPz (hardware, never a data channel), ground AFz, EOG on ch 32.
  - Sampling rate 512 Hz, 24-bit, one A/D converter per channel.
  - BrainFlow's SYNTHETIC_BOARD emits plausible fake data through the
    identical API, so everything downstream develops with no hardware.

*** UNRESOLVED - CONFIRM BEFORE SHIPPING (see chat writeup for full list) ***
  1. BrainFlow's static descriptor for BoardIds.ANT_NEURO_EE_225_BOARD reports
     a default sampling_rate of 16000 Hz, not 512 Hz. 512 Hz is presumably
     reachable via config_board(), but the exact config string and whether
     get_sampling_rate() reflects it afterward is UNVERIFIED - never tested
     against real hardware. connect() below asserts fs == 512 after
     configuring and raises loudly if that assertion fails; don't remove that
     guard until this is confirmed on the real amp.
  2. BoardShim.get_eeg_names(ANT_NEURO_EE_225_BOARD) raises
     UNSUPPORTED_BOARD_ERROR - BrainFlow's board description has no channel
     names for this board at all. Real channel order MUST come from the
     CA-208 wiring/montage sheet, not from BrainFlow. REAL_CH_NAMES below is
     still the old placeholder order - swap it for the verified order before
     trusting any by-name channel logic downstream (this file's pick(),
     preprocess.py's EOG_CHANNEL constant, features.py's frontal/parietal
     picks).

Interface (fixed - session.py, features.py and the API are built against it;
changing it needs both branches, see HANDOFF section 8):
    get_window(seconds: float) -> np.ndarray   # (n_channels, n_samples), microvolts
    pick(data: np.ndarray, names: list[str]) -> np.ndarray
    ch_names: list[str]
    fs: int
"""

from __future__ import annotations

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

fs: int = 512  # verified sampling rate of the EE-225; see unresolved item 1 above

# VERIFIED ORDER (2026-09-12): read from the header of the EO-EC .cnt in
# ~/NOVA_ANT via mne.io.read_raw_ant - a recording made on this exact amp
# and cap, so this is the montage as the rig itself writes it. sfreq in the
# same header is 512.0, and "EOG" sits at position 32 (index 31), matching
# HANDOFF. Residual risk: BrainFlow's row order could differ from the .cnt
# driver's - proven on the day by the eyes-closed alpha check (O1/O2/POz).
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


def _connect_lsl() -> None:
    """Receive the eego host's LSL broadcast: resolve the EEG stream, adopt
    ITS geometry (fs, channel count, labels - the EE-511 has 24 channels,
    not our recorded 64, so nothing here may assume a count), and pull
    samples into a ring buffer on a background thread. get_window() then
    reads the most recent slice, same contract as every other source."""
    global fs, ch_names, _lsl_ring, _lsl_write, _lsl_filled
    from pylsl import StreamInlet, resolve_byprop, resolve_streams

    # The eego host SHOULD declare type EEG; if it labels itself differently
    # (LabRecorder showed the stream named "EE511-..."), fall back to any
    # multi-channel stream rather than failing on a metadata nicety.
    found = resolve_byprop("type", "EEG", timeout=10.0)
    if not found:
        found = [s for s in resolve_streams(wait_time=5.0) if s.channel_count() >= 8]
    if not found:
        raise RuntimeError("no LSL stream found - is 'enable LSL' on in the eego software, and are both machines on the same network?")
    inlet = StreamInlet(found[0], max_buflen=60)
    info = inlet.info()
    fs = int(round(info.nominal_srate()))
    n_ch = info.channel_count()
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

    def _pull() -> None:
        global _lsl_write, _lsl_filled
        while True:
            chunk, _ = inlet.pull_chunk(timeout=1.0)
            if not chunk:
                continue
            arr = np.asarray(chunk, dtype=float).T  # (n_ch, n_new)
            n_new = arr.shape[1]
            cap = _lsl_ring.shape[1]
            for k in range(n_new):  # ring write; chunks are small (<= a few hundred samples)
                _lsl_ring[:, (_lsl_write + k) % cap] = arr[:, k]
            _lsl_write = (_lsl_write + n_new) % cap
            _lsl_filled = min(cap, _lsl_filled + n_new)

    import threading
    threading.Thread(target=_pull, daemon=True).start()


_lsl_ring = None
_lsl_write = 0
_lsl_filled = 0


def connect() -> None:
    """Open the board (synthetic or real per SYNTHETIC) and start streaming.

    Real path only - the synthetic path never touches BrainFlow's board
    object at all (see get_window). Deliberate simplification: BrainFlow's
    own SYNTHETIC_BOARD exposes just 16 generic channels
    (['Fz','C3','Cz','C4','Pz','PO7','Oz','PO8','F5','F7','F3','F1','F2','F4',
    'F6','F8'] at 250 Hz) which doesn't line up with our 64-channel/512 Hz
    montage, so routing fake data through it would mean either faking a
    64-channel remap on top of BrainFlow's own fake data (extra complexity
    for no real benefit) or shrinking every downstream by-name channel pick
    to whatever's in that list of 16. Keeping get_window's existing
    self-contained numpy generator for SYNTHETIC=True avoids both problems.
    CONFIRM with the team if a more realistic synthetic source (e.g.
    BrainFlow's PLAYBACK_FILE_BOARD replaying converted .cnt data) is wanted
    for a later pass - not implemented here, see chat writeup.
    """
    global _board, _eeg_rows, fs
    if SYNTHETIC:
        return  # nothing to open; get_window() generates data directly
    if SOURCE == "lsl":
        _connect_lsl()
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
    """Return the most recent `seconds` of EEG as (n_channels, n_samples) in microvolts.

    Real path: pulls from BrainFlow's own ring buffer via
    get_current_board_data, which always returns the latest N samples (zero
    rows are NOT inserted by BrainFlow if fewer than N samples exist yet -
    the array is simply shorter until the buffer fills; callers this early in
    a session should be prepared for a shorter-than-requested window).
    BrainFlow's default internal buffer capacity is 450,000 samples/channel,
    far more than the 1024 samples (2 s @ 512 Hz) the API needs at its 4 Hz
    poll rate, so no explicit buffer-size override is needed to avoid
    overflow between polls.

    Synthetic path: self-contained white noise around the eego's DC offset
    (+4800 uV) - flat band power, so downstream load index hovers near
    baseline and jitters. Fake data, real analysis. Does not go through
    BrainFlow at all (see connect() docstring for why).

    Per HANDOFF: the eego is DC-COUPLED, raw values sit around +4800 uV, not
    zero. Do NOT zero-center here; preprocess.py owns the 1 Hz high-pass that
    makes amplitudes meaningful.
    """
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
