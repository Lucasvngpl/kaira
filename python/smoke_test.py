"""Headless smoke test of the whole orchestration loop, no server involved.

Run it any time the modules change:  .venv/bin/python python/smoke_test.py
It asserts plumbing (sequencing, state, report shape) end to end through the
REAL decide.py; signal values are injected where a scenario needs a specific
effort band. decide's own cell-by-cell logic lives in tests/test_decide.py.
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import decide
import features
import session as session_mod
import stream

# Band-representative injected loads (log units, relative to a 0.0 baseline).
LOW, MID, HIGH = decide.LOW_LOAD - 0.1, 0.0, decide.HIGH_LOAD + 0.1


def run() -> None:
    # Shrink the baseline so the test runs in under a second.
    session_mod.BASELINE_SECONDS = 0.3
    # Real features over placeholder noise jitter; seed for a deterministic run.
    stream._rng = __import__("numpy").random.default_rng(7)

    # --- real-pipeline sanity: noise through the hand-written load index ----
    value = features.cognitive_load(stream.get_window(2.0), stream.fs, stream.ch_names)
    assert isinstance(value, float) and math.isfinite(value)
    s0 = session_mod.begin("PT-TEST0", "Memory")
    time.sleep(0.35)
    s0.baseline_status()
    s0.next_task()
    live0 = s0.live_load()
    assert live0["trusted"] and 0.5 < live0["load"] < 2.0, "white-noise load should hover near baseline"
    assert 1 <= live0["bars"] <= 5, "live meter must be server-computed"
    assert s0.state.baseline_sd >= session_mod.BASELINE_SD_FLOOR, "baseline must yield a usable SD"

    # From here scenarios need exact effort bands, so inject the load and let
    # the REAL decide.py act on it. current[0] is the absolute log load; a
    # flat baseline of 0.0 makes the relative load exactly the band value.
    current = [0.0]
    real_cognitive_load = features.cognitive_load
    features.cognitive_load = lambda window, fs, ch_names: current[0]

    def begin_calibrated(ref):
        s = session_mod.begin(ref, "Memory")
        current[0] = 0.0  # flat baseline -> mean 0.0, SD floored
        time.sleep(0.35)
        s.baseline_status()
        return s

    def play(s, rel, result, rt=5.0):
        current[0] = rel
        t = s.next_task()
        return t, s.submit_answer(t["task_id"], result, rt)

    try:
        # --- happy path: hold at high effort, ease once, converge low -------
        s = begin_calibrated("PT-TEST1")
        t1 = s.next_task()
        assert t1["n"] == 1 and t1["level"] == decide.START_LEVEL and t1["total_max"] == decide.MAX_TASKS
        assert t1 == s.next_task(), "next_task must be idempotent until answered"

        _, r = play(s, HIGH, "correct")  # correct at high effort: the EEG cell
        assert (r["action"], r["next_level"], r["reason"]) == ("hold", 2, "hold")
        assert "high effort" in r["reason_text"] and r["bars"] == 5
        _, r = play(s, MID, "incorrect", rt=12.0)
        assert (r["reason"], r["next_level"]) == ("down", 1)
        for _ in range(3):
            _, r = play(s, HIGH, "correct")
        assert r["converged"] and s.ended

        rep = s.report()
        assert rep["final_level"] == 1 and rep["end_reason"] == "converged"
        assert rep["reason"] == decide.END_TEXT["converged"]
        assert rep["accuracy"] == 0.8 and rep["disengaged_count"] == 0 and rep["untrusted_rate"] == 0.0
        assert rep["band"] == [round(math.exp(decide.LOW_LOAD), 2), round(math.exp(decide.HIGH_LOAD), 2)]
        assert {"n", "task_id", "kind", "level", "result", "load", "z", "trusted", "rt",
                "action", "reason", "reason_text", "quadrant", "bars", "flag"} <= set(rep["tasks"][0])
        assert rep["tasks"][0]["quadrant"] == "effortful" and rep["tasks"][0]["bars"] == 5

        # --- the other cells + the disengaged flag on the SECOND repeat -----
        s2 = begin_calibrated("PT-TEST2")
        _, r = play(s2, LOW, "correct")  # efficient -> up
        assert (r["reason"], r["next_level"]) == ("up", 3)
        _, r = play(s2, HIGH, "incorrect")  # struggling -> down
        assert (r["reason"], r["next_level"]) == ("down", 2)
        _, r = play(s2, LOW, "incorrect")  # first no-effort miss: repeat, no flag yet
        assert (r["reason"], r["next_level"], r["flags"]) == ("repeat", 2, [])
        _, r = play(s2, LOW, "incorrect")  # second in a row: disengaged
        assert r["reason"] == "repeat" and "disengaged" in r["flags"]
        assert s2.report()["disengaged_count"] == 1

        # --- floor: a run of failures at level 1 is NOT convergence ---------
        s3 = begin_calibrated("PT-TEST3")
        play(s3, MID, "timeout", rt=30.0)  # 2 -> 1
        for _ in range(3):
            _, r = play(s3, MID, "timeout", rt=30.0)  # stuck at 1
        assert s3.ended and not r["converged"]
        rep3 = s3.report()
        assert rep3["end_reason"] == "floor" and rep3["final_level"] == 1
        assert rep3["reason"] == decide.END_TEXT["floor"]
        assert rep3["mean_rt"] is None, "timeouts are not times-to-answer"

        # --- max_tasks: ping-pong to the cap; modal tie breaks LOW ----------
        s4 = begin_calibrated("PT-TEST4")
        for i in range(decide.MAX_TASKS):
            _, r = play(s4, MID, "correct" if i % 2 == 0 else "incorrect")
        assert s4.ended and not r["converged"]
        rep4 = s4.report()
        assert rep4["end_reason"] == "max_tasks" and rep4["final_level"] == 2

        # --- guards ---------------------------------------------------------
        for fn in (s4.next_task, lambda: s4.submit_answer("x", "correct", 1.0)):
            try:
                fn()
                raise AssertionError("ended session must refuse task calls")
            except session_mod.SessionStateError:
                pass
        try:
            session_mod.begin("PT-X", "Attention")
            raise AssertionError("unpopulated domain must be rejected")
        except ValueError:
            pass
    finally:
        features.cognitive_load = real_cognitive_load

    print("smoke test OK")


if __name__ == "__main__":
    run()
