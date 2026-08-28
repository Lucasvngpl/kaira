"""Spectral features and the cognitive load index.

Team <TODO team number> - <TODO full member names>
(The buildathon requires the algorithm file to carry team number and member
names at the top; fill in before submission.)

Owner: Lucas. Hand-written implementation (buildathon AI policy: every line
here is the team's to defend).

The index: log(frontal theta power / parietal alpha power). Frontal theta
rises and parietal alpha suppresses with working-memory load; the log makes
the ratio symmetric and lets baselines subtract instead of divide.
Band powers come from a Welch PSD (2 s segments, 50% overlap) integrated
over each band with Simpson's rule.

Interface (fixed - session.py and the API are built against it):
    cognitive_load(window, fs, ch_names) -> float
    relative_load(current: float, baseline: float) -> float

Validation targets (offline, against the ~/NOVA_ANT example recordings):
  - EO-EC recording: occipital alpha ~33x higher with eyes closed, peak 10.2 Hz.
  - Flip-cup sessions: the index should separate success from failure in the
    -2 to 0 s window before trigger code 2.
"""

import numpy as np
from scipy import signal
from scipy.integrate import simpson

BANDS = {
    "theta": (4, 8),
    "alpha": (8, 12),
}

FRONTAL = ["F3", "Fz", "F4"]
PARIETAL = ["P3", "Pz", "P4"]


def band_powers(window, fs, bands=BANDS):
    segment_length = min(int(fs * 2.0), window.shape[1])
    overlap = segment_length // 2

    freqs, psd = signal.welch(window, fs=fs,
                              nperseg=segment_length,
                              noverlap=overlap,
                              axis=1)

    out = {}
    for name, (lo, hi) in bands.items():
        mask = (freqs >= lo) & (freqs <= hi)
        out[name] = simpson(psd[:, mask], x=freqs[mask], axis=1)
    return out


def cognitive_load(window, fs, ch_names, frontal=FRONTAL, parietal=PARIETAL):
    bp = band_powers(window, fs)

    f_idx = [ch_names.index(c) for c in frontal if c in ch_names]
    p_idx = [ch_names.index(c) for c in parietal if c in ch_names]

    theta = bp["theta"][f_idx].mean()
    alpha = bp["alpha"][p_idx].mean()

    return float(np.log(theta + 1e-12) - np.log(alpha + 1e-12))


def relative_load(current, baseline):
    return float(current - baseline)

