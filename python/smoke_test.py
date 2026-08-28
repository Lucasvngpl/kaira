"""Headless smoke test of the whole orchestration loop, no server involved.

Run it any time the stubs change:  .venv/bin/python python/smoke_test.py
It must stay green with the placeholder stubs AND with the real
implementations - it asserts plumbing (sequencing, state, report shape),
never signal values.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import decide
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

    t1 = s.next_task()
    assert t1["n"] == 1 and t1["level"] == 3 and t1["total_max"] == session_mod.MAX_TASKS
    assert t1 == s.next_task(), "next_task must be idempotent until answered"
    live = s.live_load()
    assert live["trusted"] and live["load"] == 1.0, "placeholder load must be exactly baseline"
    r1 = s.submit_answer(t1["task_id"], "incorrect", 12.0)
    assert r1["action"] == "ease" and r1["next_level"] == 2 and not r1["converged"]

    for expected_n in (2, 3, 4):
        t = s.next_task()
        assert t["n"] == expected_n and t["level"] == 2
        r = s.submit_answer(t["task_id"], "correct", 5.0)
    assert r["converged"] and s.ended

    rep = s.report()
    assert rep["final_level"] == 2
    assert rep["reason"] == session_mod.CONVERGED_REASON
    assert rep["accuracy"] == 0.75 and rep["disengaged_count"] == 0
    assert len(rep["tasks"]) == 4 and rep["mean_rt"] == 6.8
    assert {"n", "task_id", "level", "result", "load", "trusted", "rt", "action", "reason", "flag"} <= set(rep["tasks"][0])

    # --- flag plumbing: a disengagement verdict must hold level and be counted
    real_decide = decide.decide
    decide.decide = lambda state, trial: ("flag", "incorrect_disengaged")
    try:
        s2 = session_mod.begin("PT-TEST2", "Memory")
        time.sleep(0.35)
        s2.baseline_status()
        t = s2.next_task()
        r = s2.submit_answer(t["task_id"], "incorrect", 3.0)
        assert r["action"] == "flag" and r["next_level"] == 3, "flag must not move the level"
        assert s2.report()["disengaged_count"] == 1 and s2.report()["tasks"][0]["flag"]
    finally:
        decide.decide = real_decide

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
