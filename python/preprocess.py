"""Filtering and artifact cleaning.

Owner: Aarnav. ASR wired by the scaffold (2026-09-12, team decision),
using meegkit's implementation (asrpy is broken on numpy 2).

calibrate() runs once per session on ~20 s of resting baseline; clean()
then processes every window:
  1. 1 Hz high-pass (the eego is DC-coupled, ~+4800 uV offset).
  2. ASR repair: calibration learned this patient's clean-signal envelope;
     any component that blows past it (blink, clench, cable tug) is rebuilt
     from the components that stayed clean. The cap has no EOG channel, so
     repair replaces blink regression.
  3. Average reference (M1/M2 masked, never deleted - row order always
     matches the caller's ch_names).
  4. Trust gate on the six formula channels. Loose post-ASR (rely on the
     repair), strict when ASR could not fit (short rehearsal baselines).

Gate for changes here: tools/validate_eoec.py must keep the eyes-closed
occipital alpha ratio (~50x) - proof we clean artifacts, not brain signal.
"""

from __future__ import annotations

import copy

import numpy as np
from scipy.signal import butter, sosfiltfilt

DEAD_CHANNELS = ("M1", "M2")

# Kept out of reference/trust math on the 64-channel rig; the EE-511 cap
# simply has no such channel and this name never matches.
EOG_CHANNEL = "EOG"

HPF_HZ = 1.0
HPF_ORDER = 4

# EEGLAB's default aggressiveness: components beyond 20 calibration standard
# deviations get reconstructed. Conservative on purpose - repairing real
# brain signal would flatten the load index. Tunable from live recordings.
ASR_CUTOFF = 20

# Trust thresholds (worst formula-channel peak-to-peak, microvolts).
# Post-ASR the gate is deliberately loose: we rely on the repair and only
# discard what ASR visibly could not save. Raw (no ASR fitted) stays strict.
TRUST_PTP_UV_ASR = 300.0
TRUST_PTP_UV_RAW = 150.0

# (fitted meegkit ASR, fitted row indices) or None. None means calibrate()
# ran but ASR could not fit (too little data) - threshold-only trust.
_asr = None
_calibrated = False


def _highpass(window: np.ndarray, fs: int) -> np.ndarray:
    """Zero-phase 1 Hz high-pass across the whole pulled window."""
    sos = butter(HPF_ORDER, HPF_HZ, btype="highpass", fs=fs, output="sos")
    return sosfiltfilt(sos, window, axis=1)


def _reference_rows(ch_names: list[str]) -> list[int]:
    """Rows that are legitimate scalp EEG for referencing/trust purposes."""
    exclude = set(DEAD_CHANNELS) | {EOG_CHANNEL}
    return [i for i, name in enumerate(ch_names) if name not in exclude]


def calibrate(baseline_window: np.ndarray, fs: int, ch_names: list[str]) -> None:
    """Fit ASR on resting data - session.py calls this once, ~20 s into the
    baseline (or on an uploaded resting recording). A fit that cannot work
    (rehearsal baselines are far too short) degrades to threshold-only
    trust instead of blocking the session."""
    global _asr, _calibrated
    _calibrated = True
    try:
        from meegkit.asr import ASR
        rows = _reference_rows(ch_names)
        asr = ASR(sfreq=fs, cutoff=ASR_CUTOFF)
        # meegkit's distribution fit sprays benign divide-by-zero warnings
        # from its histogram internals; silence just those.
        with np.errstate(divide="ignore", invalid="ignore"):
            asr.fit(_highpass(baseline_window, fs)[rows, :])
        _asr = (asr, tuple(rows))  # kept PRISTINE; _repair works on copies
    except Exception as exc:
        print(f"ASR calibration unavailable ({exc}); threshold-only trust")
        _asr = None  # raw mode: the strict threshold does all the gating


def _repair(window: np.ndarray, ch_names: list[str]) -> np.ndarray:
    if _asr is None:
        return window
    asr, fitted_rows = _asr
    if fitted_rows != tuple(_reference_rows(ch_names)):
        return window  # montage changed since calibration; do not guess
    # meegkit's transform is a STREAMING object: it carries filter tails and
    # a covariance memory between calls, assuming contiguous chunks. Our
    # windows overlap 87.5% poll to poll, so every repair starts from a
    # fresh copy of the fitted state instead - stateless and deterministic,
    # at the cost of a sub-millisecond deepcopy.
    out = window.copy()
    out[list(fitted_rows), :] = copy.deepcopy(asr).transform(window[list(fitted_rows), :])
    return out


def _average_reference(window: np.ndarray, ch_names: list[str]) -> np.ndarray:
    rows = _reference_rows(ch_names)
    ref = window[rows, :].mean(axis=0, keepdims=True)
    out = window.copy()
    out[rows, :] = out[rows, :] - ref
    return out


def _is_trusted(window: np.ndarray, ch_names: list[str]) -> bool:
    if not _calibrated:
        return False  # nothing is trusted before the baseline calibrates the pipeline
    # Judged on the channels the load index actually reads: a flaky
    # electrode the decision never sees (the first venue recording had a
    # ~350 uVpp bad-contact C3) must not veto the whole session.
    import features
    used = set(features.FRONTAL + features.PARIETAL)
    rows = [i for i, n in enumerate(ch_names) if n in used] or _reference_rows(ch_names)
    limit = TRUST_PTP_UV_ASR if _asr is not None else TRUST_PTP_UV_RAW
    return bool(np.all(np.ptp(window[rows, :], axis=1) < limit))


def clean(window: np.ndarray, fs: int, ch_names: list[str]) -> tuple[np.ndarray, bool]:
    """Return (cleaned_window, trusted).

    Row order/count of cleaned_window matches the input ch_names exactly -
    bad channels are masked out of the math, never dropped, so callers keep
    indexing by the names they passed in.
    """
    if window.shape[1] < fs // 2:
        # Too little signal to filter (stream just connected, or stalled):
        # say "don't trust this" instead of crashing the request.
        return window, False
    hp = _highpass(window, fs)
    repaired = _repair(hp, ch_names)
    referenced = _average_reference(repaired, ch_names)
    trusted = _is_trusted(referenced, ch_names)
    return referenced, trusted
