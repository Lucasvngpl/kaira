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

# Brain activity is a mix of rhythms; this index cares about two. Theta
# (4-8 Hz) is a slow rhythm that grows over the forehead when you
# concentrate. Alpha (8-12 Hz) is an "idling" rhythm at the back of the
# head that fades as soon as you start working.
BANDS = {
    "theta": (4, 8),
    "alpha": (8, 12),
}

# The electrodes where each rhythm shows most clearly: three across the
# forehead for theta, three over the parietal cortex (upper back of the
# head) for alpha.
FRONTAL = ["F3", "Fz", "F4"]
PARIETAL = ["P3", "Pz", "P4"]


def band_powers(window, fs, bands=BANDS):
    segment_length = min(int(fs * 2.0), window.shape[1])
    overlap = segment_length // 2

    # Welch's method: chop the window into overlapping 2 s chunks, take each
    # chunk's frequency spectrum, and average them - one noisy snapshot
    # becomes a stable "how much power at each frequency" curve per channel.
    freqs, psd = signal.welch(window, fs=fs,
                              nperseg=segment_length,
                              noverlap=overlap,
                              axis=1)

    # Total power inside each band = area under that curve between the band's
    # frequency limits (Simpson's rule). One number per channel per band.
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

    # The index itself: working hard means MORE frontal theta and LESS
    # parietal alpha, so theta/alpha rises with mental effort. Taking logs
    # (log(a/b) = log a - log b) makes it symmetric around zero and lets a
    # resting baseline be subtracted later instead of divided. The tiny
    # 1e-12 only guards log(0) on a dead-silent channel.
    return float(np.log(theta + 1e-12) - np.log(alpha + 1e-12))


def relative_load(current, baseline):
    # Subtracting logs is dividing the raw ratios, so exp() of this is the
    # "1.4x of this patient's own resting baseline" the clinician sees.
    return float(current - baseline)

