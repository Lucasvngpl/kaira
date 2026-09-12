# The ANTI-dummy: reproduces the ways the REAL eego broadcast can differ
# from our clean dummylsl.py, so each suspected venue failure can be
# tested on purpose instead of argued about.
#
#   python dummylsl_problem.py --mode extras    # 24 EEG + TRIG + COUNTER rows (ANT's documented shape)
#   python dummylsl_problem.py --mode srate0    # declares NO sampling rate (irregular stream)
#   python dummylsl_problem.py --mode nolabels  # 26 channels, only 24 labelled
import argparse
import random
import time

from pylsl import StreamInfo, StreamOutlet

EEG = ["Fp1", "Fp2", "F9", "F7", "F3", "Fz", "F4", "F8", "F10", "T7", "C3", "Cz",
       "C4", "T8", "P7", "P3", "Pz", "P4", "P8", "O1", "Oz", "O2", "CPz", "M1"]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["extras", "srate0", "nolabels"], default="extras")
    args = p.parse_args()

    labels = EEG + ["TRIG", "COUNTER"]
    srate = 0.0 if args.mode == "srate0" else 512.0
    info = StreamInfo(f"EE511-PROBLEM-{args.mode}", "EEG", len(labels), srate, "float32", "ee511problem")
    chs = info.desc().append_child("channels")
    labelled = EEG if args.mode == "nolabels" else labels
    for lab in labelled:
        c = chs.append_child("channel")
        c.append_child_value("label", lab)
        c.append_child_value("type", "TRIG" if lab == "TRIG" else ("COUNTER" if lab == "COUNTER" else "EEG"))

    out = StreamOutlet(info, chunk_size=32)
    print(f"problem stream up: mode={args.mode}, {len(labels)} rows, srate={srate}")
    n = 0
    while True:
        chunk = []
        for _ in range(32):
            n += 1
            # the counter row is a huge monotonic ramp, like a real sample counter
            chunk.append([random.uniform(-25.0, 25.0) for _ in EEG] + [0.0, float(n)])
        out.push_chunk(chunk)
        time.sleep(32 / 512.0)


if __name__ == "__main__":
    main()
