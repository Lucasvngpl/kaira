"""Headless smoke test of the whole orchestration loop, no server involved.

Run it any time the stubs change:  .venv/bin/python python/smoke_test.py
It must stay green with the placeholder stubs AND with the real
implementations - it asserts plumbing (sequencing, state, report shape),
never signal values.
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


def run() -> None:
    # Shrink the baseline so the test runs in under a second.
    session_mod.BASELINE_SECONDS = 0.3

    # --- happy path: ease down once, then converge with three corrects ------
    s = session_mod.begin("PT-TEST", "Memory")
    status = s.baseline_status()
    assert not status["done"] and 0 <= status["progress"] < 1
    time.sleep(0.35)
    status = s.baseline_status()
    assert status["done"] and status["progress"] == 1.0

    start = session_mod.LEVEL_START  # asserts track the policy constant, not a literal
    t1 = s.next_task()
    assert t1["n"] == 1 and t1["level"] == start and t1["total_max"] == session_mod.MAX_TASKS
    assert t1 == s.next_task(), "next_task must be idempotent until answered"
    live = s.live_load()
    assert live["trusted"] and live["load"] == 1.0, "placeholder load must be exactly baseline"
    r1 = s.submit_answer(t1["task_id"], "incorrect", 12.0)
    assert r1["action"] == "ease" and r1["next_level"] == start - 1 and not r1["converged"]

    for expected_n in (2, 3, 4):
        t = s.next_task()
        assert t["n"] == expected_n and t["level"] == start - 1
        r = s.submit_answer(t["task_id"], "correct", 5.0)
    assert r["converged"] and s.ended

    rep = s.report()
    assert rep["final_level"] == start - 1 and rep["level_max"] == 5
    assert rep["reason"] == session_mod.CONVERGED_REASON
    assert rep["accuracy"] == 0.75 and rep["disengaged_count"] == 0
    assert len(rep["tasks"]) == 4 and rep["mean_rt"] == 6.8
    assert {"n", "task_id", "level", "result", "load", "trusted", "rt", "action", "reason", "flag"} <= set(rep["tasks"][0])

    # --- four-quadrant wiring: injected loads through a quadrant stand-in ----
    # The placeholder decide ignores load, so until the real algorithm lands,
    # prove the wiring (load -> trial -> action -> level/flag/report) with a
    # stand-in that implements the four quadrants and hand-made load values.
    lo, hi = decide.LOAD_BAND

    def quadrant(state, trial):
        if trial.result == "correct":
            return ("advance", "correct_easy") if trial.load < lo else ("hold", "correct_engaged")
        return ("flag", "incorrect_disengaged") if trial.load < lo else ("ease", "incorrect_engaged")

    current = [0.0]  # absolute log-load the injected load_index reports
    real_decide, real_load_index = decide.decide, features.load_index
    decide.decide = quadrant
    features.load_index = lambda window, fs, ch_names: current[0]
    try:
        s2 = session_mod.begin("PT-TEST2", "Memory")
        time.sleep(0.35)
        s2.baseline_status()  # baseline log = 0.0, so multiples come out as exp(sample)
        quadrants = [
            # (load multiple, result, expected action, level after, flagged)
            (0.6, "correct", "advance", start + 1, False),  # right without effort -> harder
            (1.5, "correct", "hold", start + 1, False),  # right at useful effort -> hold
            (2.0, "incorrect", "ease", start, False),  # wrong while working -> easier
            (0.5, "incorrect", "flag", start, True),  # wrong without effort -> disengaged, hold
        ]
        for multiple, result, action, level_after, flagged in quadrants:
            current[0] = math.log(multiple)
            t = s2.next_task()
            r = s2.submit_answer(t["task_id"], result, 4.0)
            assert (r["action"], r["next_level"]) == (action, level_after), (r, action, level_after)
        rep2 = s2.report()
        assert rep2["disengaged_count"] == 1 and rep2["tasks"][3]["flag"]
        assert [round(t["load"], 1) for t in rep2["tasks"]] == [0.6, 1.5, 2.0, 0.5]
        assert not s2.ended, "no three-correct run happened, so no convergence"
    finally:
        decide.decide = real_decide
        features.load_index = real_load_index

    # --- cap path: timeouts bounce off level 1 until the task cap ends it ---
    s3 = session_mod.begin("PT-TEST3", "Memory")
    time.sleep(0.35)
    s3.baseline_status()
    for _ in range(session_mod.MAX_TASKS):
        t = s3.next_task()
        r = s3.submit_answer(t["task_id"], "timeout", 30.0)
    assert s3.ended and not r["converged"]
    rep3 = s3.report()
    assert rep3["reason"] == session_mod.MAXED_REASON
    assert rep3["final_level"] == 1 and rep3["mean_rt"] is None, "timeouts are not times-to-answer"

    # --- guards ---------------------------------------------------------------
    for fn in (s3.next_task, lambda: s3.submit_answer("x", "correct", 1.0)):
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

    print("smoke test OK")


if __name__ == "__main__":
    run()
