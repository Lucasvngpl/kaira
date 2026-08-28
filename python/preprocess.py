"""Filtering and artifact rejection - SKELETON, hand-written by the team.

Owner: Aarnav. Deliberately empty of real code (buildathon AI policy).

This module turns a raw window from stream.get_window() into something
features.py is allowed to trust. Its signature is NOT part of the fixed
four-function interface in HANDOFF section 5; clean() below is the seam the
scaffold proposes, because the report contract (section 7) needs a per-task
`trusted` flag and artifact rejection is the only honest source of it.
session.py calls clean() between get_window() and load_index() - if the team
changes this shape, update session._sample_load() to match.

TODO(team) - the pipeline this file must implement, in order, and why:
  1. 1 Hz HIGH-PASS FIRST. The eego is DC-coupled; raw values sit around
     +4800 uV. Every amplitude threshold in the literature assumes
     zero-centred data, so nothing downstream means anything before this.
  2. Drop M1 and M2. They are recorded but were never connected in the
     provided dataset; left in, they poison the average reference.
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
wrong.
"""

from __future__ import annotations

import numpy as np


def clean(window: np.ndarray, fs: int, ch_names: list[str]) -> tuple[np.ndarray, bool]:
    """Return (cleaned_window, trusted).

    TODO(team): implement the five steps in the module docstring.
    `trusted=False` means artifacts made this window unusable; the caller
    keeps the sample out of baselines and flags it in the live readout.
    """
    return window, True  # placeholder: passthrough, always trusted - obviously fake
