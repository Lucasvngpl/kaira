"""Unit tests for decide.py - every function is pure, so no mocks.

Run:  .venv/bin/python tests/test_decide.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))

import decide as d


@dataclass
class T:
    """The duck-typed slice of session.Trial that decide actually reads."""

    result: str
    level: int
    load_log: float = 0.0
    trusted: bool = True


LOW = d.LOW_LOAD - 0.1
MID = 0.0
HIGH = d.HIGH_LOAD + 0.1


def run() -> None:
    # 1. All six cells of the decision table.
    assert d.next_level(True, 2, "low") == (3, "up")
    assert d.next_level(True, 2, "mid") == (3, "up")
    assert d.next_level(True, 2, "high") == (2, "hold")
    assert d.next_level(False, 2, "low") == (2, "repeat")
    assert d.next_level(False, 2, "mid") == (1, "down")
    assert d.next_level(False, 2, "high") == (1, "down")

    # 2. Untrusted input takes the mid column, both correct and wrong,
    #    and blanks the load fields.
    up = d.decide(T("correct", 2, HIGH, trusted=False), [])
    assert (up.next_level, up.reason) == (3, "up")
    assert up.load_bars is None and up.load_multiple is None and "untrusted" in up.flags
    dn = d.decide(T("incorrect", 2, LOW, trusted=False), [])
    assert (dn.next_level, dn.reason) == (1, "down")

    # 3. Ceiling: correct + low at MAX clamps with its OWN reason, not "hold".
    assert d.next_level(True, d.MAX_LEVEL, "low") == (d.MAX_LEVEL, "ceiling")

    # 4. Floor: wrong at MIN clamps as "floor"; a run of them ends as floor,
    #    never as converged (three same-level failures are not stability).
    assert d.next_level(False, d.MIN_LEVEL, "mid") == (d.MIN_LEVEL, "floor")
    assert d.should_end([T("incorrect", 1), T("timeout", 1), T("incorrect", 1)]) == (True, "floor", 1)

    # 5. The convergence run resets on a level change and on a wrong answer.
    assert d.should_end([T("correct", 2), T("correct", 3), T("correct", 3)])[0] is False
    assert d.should_end([T("correct", 3), T("incorrect", 3), T("correct", 3)])[0] is False
    assert d.should_end([T("correct", 3)] * 3) == (True, "converged", 3)
    # At MAX with low effort throughout the same run reads ceiling instead.
    assert d.should_end([T("correct", 5, LOW)] * 3) == (True, "ceiling", 5)
    assert d.should_end([T("correct", 5, MID)] * 3) == (True, "converged", 5)

    # 6. max_tasks modal tie-break resolves to the LOWER level.
    hist = [T("correct", 2), T("incorrect", 3)] * (d.MAX_TASKS // 2)
    assert d.should_end(hist) == (True, "max_tasks", 2)

    # 7. Bars and band agree at both boundaries, asserted FROM the constants
    #    so changing a constant cannot silently desync display from rule.
    eps = 1e-9
    for rel in (d.LOW_LOAD - eps, d.LOW_LOAD, MID, d.HIGH_LOAD, d.HIGH_LOAD + eps):
        band, bars = d.load_band(rel), d.load_bars(rel)
        assert (bars == 1) == (band == "low"), (rel, band, bars)
        assert (bars == 5) == (band == "high"), (rel, band, bars)

    # Disengaged flags on the SECOND consecutive no-effort miss, not the first.
    first = d.decide(T("incorrect", 2, LOW), [])
    second = d.decide(T("incorrect", 2, LOW), [T("incorrect", 2, LOW)])
    assert "disengaged" not in first.flags and "disengaged" in second.flags
    assert first.quadrant == "disengaged" and first.reason == "repeat"

    print("decide tests OK")


if __name__ == "__main__":
    run()
