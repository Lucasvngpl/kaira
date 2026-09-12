"""Filtering and artifact rejection.

Owner: Aarnav.

This module turns a raw window from stream.get_window() into something
features.py is allowed to trust. clean() is the seam the scaffold proposes
(not part of the fixed four-function interface - see stream.py) because the
report contract needs a per-task `trusted` flag and artifact rejection is the
only honest source of it. session.py calls clean() between get_window() and
cognitive_load() - if the team changes this shape, update
session._clean_window() to match.

calibrate() is new (added here, not in the original scaffold) - it's the
missing seam for persisting an EOG regression estimate across clean() calls,
since clean()'s fixed-looking (window, fs, ch_names) signature has nowhere to
carry state. It's cached at module scope, which works but is a design choice,
not something forced by the interface. session.py needs to call it once
before the main loop starts, on some baseline window - see unresolved item 7
below for what that baseline actually should be.

*** UNRESOLVED - CONFIRM BEFORE SHIPPING (see chat writeup for full list) ***
  3. EOG_CHANNEL below is just "whatever name currently sits at index 32 in
     stream.py's PLACEHOLDER ch_names list" (index 31, 0-based). Once the
     real CA-208 order replaces that placeholder, re-derive this constant
     from the verified montage sheet, not from array position alone. Also
     confirm this position doesn't collide with a channel features.py
     independently wants for frontal theta / parietal alpha - if it does,
     that channel needs to be excluded from features.py's picks too, since
     post-regression it's an ocular reference, not brain signal.
  4. It's also unconfirmed whether the droplead is even inside the 64-channel
     EEG bank at all. BrainFlow's board descriptor for this board id shows a
     separate 24-channel "emg_channels" bank (rows 65-88, generic
     bipolar/AUX inputs per BrainFlow's schema) alongside the 64 EEG rows.
     If the droplead is actually wired to one of those AUX inputs instead of
     sitting inside the 64-channel bank, stream.py's get_window() needs to
     surface that row too (it currently only returns the 64 EEG rows) and
     EOG_CHANNEL/calibrate()/clean() below need to read from that separate
     array instead. Cannot resolve this without the montage sheet or
     hardware.
  6. TRUST_PEAK_TO_PEAK_UV is a generic EEG artifact-rejection heuristic, not
     derived from this amp's actual configured input range
     (reference_range/bipolar_range, both configurable per-session per the
     eego SDK docs). Revisit once that configured range is known.
  7. No calibration protocol exists yet for calibrate()'s baseline_window.
     The provided cup-flip/basketball .cnt files are a motor-artifact test
     set, not a deliberate-blink recording, and are probably not the right
     source for estimating EOG regression coefficients. Need either a
     dedicated "sit still, blink normally/deliberately a few times" baseline
     at session start, or confirmation that an existing recording already
     covers this.
  8. _highpass() below uses zero-phase filtfilt per pulled window rather than
     a continuous causal filter with persisted state - simpler given the
     pull-window architecture (get_window returns overlapping windows, not
     exclusive chunks), but it means samples near each window's edges are
     less reliable than the middle/end. Flag if the team needs true
     continuous causal filtering instead.

TODO(team) - the pipeline this file must implement, in order, and why:
  1. 1 Hz HIGH-PASS FIRST. The eego is DC-coupled; raw values sit around
     +4800 uV. Every amplitude threshold in the literature assumes
     zero-centred data, so nothing downstream means anything before this.
  2. Handle M1/M2. They are recorded but were never connected in the
     provided dataset; left in, they poison the average reference. Chosen
     here: mask them out of the average-reference and trust calculations
     rather than physically delete their rows, so the output array's row
     order always matches the ch_names it was given - see unresolved item 5.
  3. Handle EOG. Channel 32 is a dedicated droplead ring electrode; use it to
     detect (or regress out) blinks and eye movement.
  4. Re-reference (average reference across the surviving channels; the
     hardware reference is CPz and never appears as a data channel).
  5. Artifact decision. If the window is contaminated (blink, movement,
     amplitude blow-up), return trusted=False rather than a cleaned lie -
     decide.py must know when the load number cannot be believed.

Validation baseline (HANDOFF section 4): after this pipeline plus
features.py, the EO-EC recording must show occipital alpha ~33x higher with
eyes closed, peaking at 10.2 Hz. If a change here breaks that, the change is
wrong. NOTE: not yet checked against this file - needs the actual EO-EC
recording, which may be a separate file from the cup-flip/basketball data
(see unresolved item 7).
"""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfiltfilt

DEAD_CHANNELS = ("M1", "M2")

# VERIFIED (2026-09-12): the EO-EC .cnt header names the droplead "EOG",
# inside the 64-channel bank at position 32 - unresolved items 3 and 4 are
# answered by the rig's own recording. Found by name, so it cannot collide
# with features.py's frontal/parietal picks.
EOG_CHANNEL = "EOG"

HPF_HZ = 1.0
HPF_ORDER = 4

# UNVERIFIED PLACEHOLDER - see unresolved item 6 above.
TRUST_PEAK_TO_PEAK_UV = 150.0

# Calibrated Gratton & Coles-style regression coefficients, one per surviving
# EEG channel: EEG_ch_corrected = EEG_ch - gain[ch] * EOG. None until
# calibrate() has been called once - see unresolved item 7 for what data that
# should run on.
_eog_gain: dict[str, float] | None = None


def _highpass(window: np.ndarray, fs: int) -> np.ndarray:
    """Zero-phase 1 Hz high-pass across the whole pulled window. See
    unresolved item 8 for the causality tradeoff this implies."""
    sos = butter(HPF_ORDER, HPF_HZ, btype="highpass", fs=fs, output="sos")
    return sosfiltfilt(sos, window, axis=1)


def _reference_rows(ch_names: list[str]) -> list[int]:
    """Rows that are legitimate scalp EEG for referencing/trust purposes:
    excludes the dead mastoids and the EOG channel itself (not a brain
    signal)."""
    exclude = set(DEAD_CHANNELS) | {EOG_CHANNEL}
    return [i for i, name in enumerate(ch_names) if name not in exclude]


def calibrate(baseline_window: np.ndarray, fs: int, ch_names: list[str]) -> None:
    """Estimate one EOG regression coefficient per surviving EEG channel from
    a baseline recording that should contain a handful of blinks. Must be
    called once (by session.py, at session start) before clean() will do
    anything beyond high-pass + reference + gross-artifact rejection - see
    unresolved item 7 for what that baseline recording actually should be.
    """
    global _eog_gain
    if EOG_CHANNEL not in ch_names:
        # Integration fix (2026-09-12): the venue amp is an eego 24 (EE-511)
        # whose cap may carry no EOG droplead. No EOG means no regression to
        # calibrate - fall back to threshold-only trust (blinks still trip
        # the peak-to-peak check) instead of refusing to run.
        _eog_gain = {}
        return
    hp = _highpass(baseline_window, fs)
    eog_idx = ch_names.index(EOG_CHANNEL)
    eog = hp[eog_idx, :]
    eog_var = float(np.var(eog))
    if eog_var == 0.0:
        raise RuntimeError("EOG channel is flat during calibration - can't estimate a regression coefficient; check the recording")
    gains: dict[str, float] = {}
    for i in _reference_rows(ch_names):
        name = ch_names[i]
        gains[name] = float(np.cov(hp[i, :], eog)[0, 1] / eog_var)
    _eog_gain = gains


def _remove_eog(window: np.ndarray, ch_names: list[str]) -> np.ndarray:
    if _eog_gain is None or EOG_CHANNEL not in ch_names:
        return window  # not calibrated yet, or channel missing - pass through rather than fabricate a coefficient
    eog_idx = ch_names.index(EOG_CHANNEL)
    eog = window[eog_idx, :]
    out = window.copy()
    for i, name in enumerate(ch_names):
        gain = _eog_gain.get(name)
        if gain is not None:
            out[i, :] = out[i, :] - gain * eog
    return out


def _average_reference(window: np.ndarray, ch_names: list[str]) -> np.ndarray:
    rows = _reference_rows(ch_names)
    ref = window[rows, :].mean(axis=0, keepdims=True)
    out = window.copy()
    out[rows, :] = out[rows, :] - ref
    return out


def _is_trusted(window: np.ndarray, ch_names: list[str]) -> bool:
    if _eog_gain is None:
        return False  # pre-calibration windows are uncorrected for blinks - don't let decide.py trust them
    rows = _reference_rows(ch_names)
    ptp = np.ptp(window[rows, :], axis=1)
    return bool(np.all(ptp < TRUST_PEAK_TO_PEAK_UV))


def clean(window: np.ndarray, fs: int, ch_names: list[str]) -> tuple[np.ndarray, bool]:
    """Return (cleaned_window, trusted).

    Row order/count of cleaned_window matches the input ch_names exactly -
    M1/M2 and the EOG channel are masked out of referencing/trust math rather
    than physically dropped, so callers can keep indexing by the same
    ch_names they passed in. See unresolved item 5 (this file's own docstring
    header) if the team would rather clean() return a shortened array plus an
    updated name list instead - that's a real, currently-undecided fork.
    """
    hp = _highpass(window, fs)
    corrected = _remove_eog(hp, ch_names)
    referenced = _average_reference(corrected, ch_names)
    trusted = _is_trusted(referenced, ch_names)
    return referenced, trusted
