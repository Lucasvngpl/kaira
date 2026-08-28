"""Spectral features and the cognitive load index - SKELETON, hand-written by the team.

Team <TODO team number> - <TODO full member names>
(The buildathon requires the algorithm file to carry team number and member
names at the top; fill in before submission.)

Owner: Lucas. Deliberately empty of real code (buildathon AI policy): this is
the algorithm the judges grade, so every line must be hand-written and
defensible on the spot.

Interface (fixed - session.py and the API are built against it):
    load_index(window, fs, ch_names) -> float          # log(frontal theta / parietal alpha)
    relative_load(current: float, baseline: float) -> float

TODO(team) - what load_index must do and why:
  - Input is a CLEANED window from preprocess.clean(); never feed it raw data
    (DC offset ~+4800 uV would swamp every band estimate).
  - Welch PSD per channel (scipy.signal.welch), window length chosen for
    stable estimates at fs=512.
  - Frontal theta power (4-7 Hz, midline frontal channels such as Fz/F1/F2 -
    pick via stream.pick) and parietal alpha power (8-12 Hz, Pz and
    neighbours).
  - Return log(theta_frontal / alpha_parietal). Frontal theta rises and
    parietal alpha suppresses with working-memory load; the log makes the
    ratio symmetric and lets baselines subtract instead of divide.
  - Validate against the EO-EC recording: occipital alpha 33x higher with
    eyes closed, peak 10.2 Hz. Then check the flip-cup sessions (analysis
    window -2 to 0 s before trigger code 2) separate success from failure.
"""

from __future__ import annotations

import numpy as np


def load_index(window: np.ndarray, fs: int, ch_names: list[str]) -> float:
    """Cognitive load for one window: log(frontal theta power / parietal alpha power).

    TODO(team): Welch -> band powers -> log ratio, per the module docstring.
    """
    return 0.5  # placeholder: constant fake load so the stack runs end-to-end

def relative_load(current: float, baseline: float) -> float:
    """Load relative to the patient's own resting baseline.

    A subtraction, because both values are logs: log(a/b) = log a - log b.
    (Body given by the interface spec itself; exp() of this is the "1.68x"
    multiple the clinician sees.)
    """
    return current - baseline
