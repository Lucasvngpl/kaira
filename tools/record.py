"""Capture real signal to a file, for tuning constants off-hardware.

Run on the machine connected to the amp (Windows on the day; works against
the synthetic board anywhere):

    python tools/record.py --seconds 60 --out rest_eo.npz --note "rest, eyes open"

Polls stream.get_window(2.0) back to back and stacks the windows, so the
file holds (n_windows, n_channels, n_samples) plus fs and ch_names -
everything inspect_capture.py needs. Send the .npz to whoever is tuning.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))
import stream  # noqa: E402

WINDOW_SECONDS = 2.0  # same as session.SAMPLE_SECONDS - tune on what we run


def main() -> None:
    p = argparse.ArgumentParser(description="Record stacked 2 s windows to .npz")
    p.add_argument("--seconds", type=float, default=60.0)
    p.add_argument("--out", required=True)
    p.add_argument("--note", default="", help="what the subject was doing")
    args = p.parse_args()

    n = int(args.seconds / WINDOW_SECONDS)
    windows = []
    print(f"recording {n} windows of {WINDOW_SECONDS} s ...")
    for i in range(n):
        t0 = time.monotonic()
        windows.append(stream.get_window(WINDOW_SECONDS))
        print(f"  {i + 1}/{n}", end="\r")
        # Pace to real time so consecutive windows do not overlap.
        time.sleep(max(0.0, WINDOW_SECONDS - (time.monotonic() - t0)))
    np.savez_compressed(
        args.out,
        windows=np.stack(windows),
        fs=stream.fs,
        ch_names=np.array(stream.ch_names),
        note=args.note,
    )
    print(f"\nwrote {args.out}: {np.stack(windows).shape}, fs={stream.fs}, note={args.note!r}")


if __name__ == "__main__":
    main()
