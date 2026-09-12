"""Pretend to be the eego host: broadcast a NOVA_ANT recording over LSL.

    .venv/bin/python tools/lsl_fake_amp.py

Lets the whole LSL path rehearse on one machine with real brain signal
before the venue's amp exists. Loops the EO-EC recording forever; labels,
rate and units come from the file, so the receiver sees exactly what the
real host would send (just 64 channels instead of the EE-511's 24).
"""

from __future__ import annotations

import argparse
import time

import mne
import numpy as np
from pylsl import StreamInfo, StreamOutlet

CNT = "/Users/Lucas/NOVA_ANT/Eyes open eyes closed/Ewing_Patrick_2026-08-10_13-07-25_EO-EC.cnt"
CHUNK = 32  # samples per push: 16 pushes/s at 512 Hz, LSL-typical


def main() -> None:
    p = argparse.ArgumentParser(description="Broadcast the EO-EC recording over LSL")
    # Default name is deliberately NOT EE511*: the UI's LIVE mode only accepts
    # the real amp's prefix. Pass --name EE511-REHEARSAL to drill the live path.
    p.add_argument("--name", default="kaira-fake-eego")
    args = p.parse_args()

    raw = mne.io.read_raw_ant(CNT, preload=True, verbose="ERROR")
    fs = int(raw.info["sfreq"])
    data = raw.get_data() * 1e6  # volts -> microvolts, like the eego host streams
    n_ch = data.shape[0]

    info = StreamInfo(args.name, "EEG", n_ch, fs, "float32", "kaira-fake")
    chans = info.desc().append_child("channels")
    for name in raw.ch_names:
        chans.append_child("channel").append_child_value("label", name)
    outlet = StreamOutlet(info, chunk_size=CHUNK)

    print(f"broadcasting {n_ch} ch @ {fs} Hz from {CNT.split('/')[-1]} (loops forever, ctrl-c to stop)")
    pos = 0
    period = CHUNK / fs
    while True:
        t0 = time.monotonic()
        chunk = data[:, pos : pos + CHUNK]
        if chunk.shape[1] < CHUNK:
            pos = 0
            continue
        outlet.push_chunk(chunk.T.tolist())
        pos += CHUNK
        time.sleep(max(0.0, period - (time.monotonic() - t0)))


if __name__ == "__main__":
    main()
