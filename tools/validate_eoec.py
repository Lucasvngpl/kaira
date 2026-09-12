"""The HANDOFF validation gate, run for real: push the EO-EC recording
through preprocess.clean + features.band_powers and check that occipital
alpha is an order of magnitude higher with eyes closed, peaking near 10 Hz.

    .venv/bin/python tools/validate_eoec.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))
import features  # noqa: E402
import preprocess  # noqa: E402

import mne  # noqa: E402

CNT = "/Users/Lucas/NOVA_ANT/Eyes open eyes closed/Ewing_Patrick_2026-08-10_13-07-25_EO-EC.cnt"
OCCIPITAL = ["O1", "Oz", "O2", "POz"]


def main() -> None:
    raw = mne.io.read_raw_ant(CNT, preload=True, verbose="ERROR")
    fs = int(raw.info["sfreq"])
    ch_names = raw.ch_names
    data_uv = raw.get_data() * 1e6  # mne loads volts; the pipeline speaks microvolts
    print(f"recording: {data_uv.shape[1] / fs:.0f} s, fs={fs}, {len(ch_names)} channels")
    print("annotations:", [(a["onset"], a["duration"], a["description"]) for a in raw.annotations])

    preprocess.calibrate(data_uv[:, : fs * 30], fs, ch_names)

    occ = [ch_names.index(c) for c in OCCIPITAL if c in ch_names]
    win = fs * 2
    rows = []
    for start in range(0, data_uv.shape[1] - win, win):
        w = data_uv[:, start : start + win]
        cleaned, trusted = preprocess.clean(w, fs, ch_names)
        bp = features.band_powers(cleaned, fs)
        rows.append((start / fs, float(bp["alpha"][occ].mean()), trusted))

    alphas = np.array([a for _, a, _ in rows])
    # No usable annotations? Split empirically: the strongest quartile of
    # occipital alpha is eyes-closed time, the weakest is eyes-open.
    hi = np.percentile(alphas, 75)
    lo = np.percentile(alphas, 25)
    ec = alphas[alphas >= hi].mean()
    eo = alphas[alphas <= lo].mean()
    print(f"trusted windows: {sum(t for _, _, t in rows)}/{len(rows)}")
    print(f"occipital alpha, top-quartile (eyes closed) vs bottom-quartile (eyes open): {ec / eo:.1f}x")

    # Peak frequency during the strongest-alpha stretch.
    from scipy import signal as sg
    best_t = rows[int(np.argmax(alphas))][0]
    w = data_uv[:, int(best_t * fs) : int(best_t * fs) + fs * 10]
    cleaned, _ = preprocess.clean(w, fs, ch_names)
    f, psd = sg.welch(cleaned[occ].mean(axis=0), fs=fs, nperseg=fs * 2)
    band = (f >= 7) & (f <= 13)
    print(f"alpha peak during strongest stretch: {f[band][np.argmax(psd[band])]:.1f} Hz (target ~10.2)")


if __name__ == "__main__":
    main()
