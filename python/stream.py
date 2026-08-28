"""EEG acquisition via BrainFlow - SKELETON, hand-written by the team.

Owner: Aarnav. This file is deliberately empty of real code (buildathon AI
policy: the team must be able to defend every line of the signal chain).

Verified hardware facts (HANDOFF.md section 3 - do not re-derive these):
  - Amplifier: ANT Neuro eego mylab 64, product code EE-225.
  - BrainFlow board id 36 = BoardIds.ANT_NEURO_EE_225_BOARD.
  - BrainFlow's ANT Neuro boards run on WINDOWS ONLY.
  - Cap: waveguard original CA-208, 64 channels, 10/10 layout.
  - Reference CPz (hardware, never a data channel), ground AFz, EOG on ch 32.
  - Sampling rate 512 Hz, 24-bit, one A/D converter per channel.
  - BrainFlow's SYNTHETIC_BOARD emits plausible fake data through the
    identical API, so everything downstream develops with no hardware.

Interface (fixed - session.py, features.py and the API are built against it;
changing it needs both branches, see HANDOFF section 8):
    get_window(seconds: float) -> np.ndarray   # (n_channels, n_samples), microvolts
    pick(data: np.ndarray, names: list[str]) -> np.ndarray
    ch_names: list[str]
    fs: int
"""

from __future__ import annotations

import numpy as np

# Flipping this single constant (or passing --synthetic/--no-synthetic to the
# API) is the whole synthetic -> real switch. api/main.py writes it at startup.
SYNTHETIC: bool = True

# TODO(team): board selection belongs here, roughly:
#   BOARD_ID = BoardIds.SYNTHETIC_BOARD if SYNTHETIC else BoardIds.ANT_NEURO_EE_225_BOARD  # 36
# plus a connect()/release() pair around BoardShim (prepare_session, start_stream).

fs: int = 512  # verified sampling rate of the EE-225; SYNTHETIC_BOARD is resampled/treated as this by the team's acquisition code

# TODO(team): populate from the board at connect time (BoardShim.get_eeg_names
# or the CA-208 montage). Real 10/10 names (Fz, Pz, O1, ...) matter because
# features.py picks frontal/parietal channels by name. Remember M1 and M2 are
# dead in the provided dataset and must be dropped before any average reference.
# Placeholder names below are obviously fake so nobody mistakes them for the montage.
ch_names: list[str] = [f"FAKE{i:02d}" for i in range(1, 65)]


def get_window(seconds: float) -> np.ndarray:
    """Return the most recent `seconds` of EEG as (n_channels, n_samples) in microvolts.

    TODO(team):
      - Read from the BrainFlow ring buffer (get_current_board_data) so this
        never blocks; the API polls it at ~1 Hz for the live load readout.
      - Return microvolts. The eego is DC-COUPLED: raw values sit around
        +4800 uV, not zero. Do NOT zero-center here; preprocess.py owns the
        1 Hz high-pass that makes amplitudes meaningful.
      - Rows must line up with ch_names.
    """
    # Placeholder: an obviously fake flatline with the right shape, so the
    # orchestrator, API and UI run end-to-end before this file is written.
    n_samples = int(round(seconds * fs))
    return np.zeros((len(ch_names), n_samples))


def pick(data: np.ndarray, names: list[str]) -> np.ndarray:
    """Return only the rows of `data` whose channel names are in `names`.

    TODO(team): index rows via ch_names; raise on unknown names rather than
    silently returning the wrong channels. Used by features.py to grab the
    frontal and parietal groups.
    """
    raise NotImplementedError("TODO(team): channel picking - nothing calls this until features.py is real")
