"""Turn a capture from tools/record.py into tuning numbers.

    python tools/inspect_capture.py rest_eo.npz [task.npz] [eyes_closed.npz]

Prints, per file: per-window peak-to-peak percentiles (sets the trust
threshold), the load distribution in log units (checks the +-0.30 bands
and the baseline SD floor), and occipital alpha power (eyes-open vs
eyes-closed files should differ by an order of magnitude - the channel-
order proof). With a rest file AND a task file it also runs
decide.calibrate_bands() on the combined loads to propose new thresholds.
Read-only: prints suggestions, changes nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))
import decide  # noqa: E402
import features  # noqa: E402
import preprocess  # noqa: E402

OCCIPITAL = ["O1", "Oz", "O2", "POz"]


def analyse(path: str):
    d = np.load(path, allow_pickle=False)
    windows, fs, ch_names = d["windows"], int(d["fs"]), [str(c) for c in d["ch_names"]]
    note = str(d["note"]) if "note" in d else ""
    print(f"\n== {path}  ({windows.shape[0]} windows, fs={fs}, note={note!r})")

    loads, p2ps, occ_alpha, untrusted = [], [], [], 0
    for w in windows:
        cleaned, trusted = preprocess.clean(w, fs, ch_names)
        if not trusted:
            untrusted += 1
            continue
        loads.append(features.cognitive_load(cleaned, fs, ch_names))
        p2ps.append(float((cleaned.max(axis=1) - cleaned.min(axis=1)).max()))
        bp = features.band_powers(cleaned, fs)
        occ = [ch_names.index(c) for c in OCCIPITAL if c in ch_names]
        occ_alpha.append(float(bp["alpha"][occ].mean()))

    loads, p2ps = np.array(loads), np.array(p2ps)
    print(f"  untrusted windows: {untrusted}")
    print(f"  worst-channel p2p uV   p50={np.percentile(p2ps, 50):.0f}  p90={np.percentile(p2ps, 90):.0f}  p99={np.percentile(p2ps, 99):.0f}")
    print(f"  load (log units)       mean={loads.mean():+.3f}  sd={loads.std(ddof=1):.3f}  min={loads.min():+.3f}  max={loads.max():+.3f}")
    print(f"  occipital alpha power  mean={np.mean(occ_alpha):.3g}")
    return loads, np.mean(occ_alpha)


def main() -> None:
    results = [(p, *analyse(p)) for p in sys.argv[1:]]
    if len(results) >= 2:
        all_loads = np.concatenate([r[1] for r in results])
        lo, hi = decide.calibrate_bands(all_loads.tolist())
        print(f"\ncalibrate_bands over all files: LOW={lo:+.3f}  HIGH={hi:+.3f}  (current {decide.LOW_LOAD:+.2f}/{decide.HIGH_LOAD:+.2f})")
        alphas = {p: a for p, _, a in results}
        print("occipital alpha ratios between files (eyes-closed / eyes-open should be >> 1):")
        base = results[0]
        for p, _, a in results[1:]:
            print(f"  {p} / {base[0]} = {a / base[2]:.1f}x")


if __name__ == "__main__":
    main()
