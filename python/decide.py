"""The decision maker - hand-written by the team.

The flow, in one breath: EEG becomes one load number per task (features.py),
session.py subtracts the patient's resting baseline and hands the result
here. This file buckets that effort into low / mid / high, looks at whether
the answer was right, picks the next task's difficulty, and says when the
session is over. Pure Python, a handful of numbers, no EEG, no I/O.

The honest claim: this is a normal adaptive staircase (right = harder,
wrong = easier) with exactly TWO cells changed by the EEG:
  - right at HIGH effort holds (they are at their working edge, not past it)
  - wrong at LOW effort repeats (no effort means disengaged, not "too hard")
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# Thresholds live in log units; the "0.67x / 1.50x" people see are derived,
# never stored, so the rule and the display cannot drift apart. Symmetric in
# log because that is what symmetry means for a ratio: 0.67 and 1.50 are
# reciprocals. Guesses until real sessions exist - see calibrate_bands().
LOW_LOAD = -0.405   # below this: not really trying (0.67x baseline)
HIGH_LOAD = +0.405  # above this: working hard (1.50x baseline)

START_LEVEL = 2  # our patients skew low-functioning, so start below the middle
MIN_LEVEL = 1
MAX_LEVEL = 5
STEP = 1  # one level at a time; bigger jumps are hard to justify clinically
MAX_TASKS = 12
CONVERGENCE_RUN = 3  # one right answer can be a guess; three in a row is evidence


def calibrate_bands(relative_loads, lo_pct=25, hi_pct=75):
    """The successor to the guesses above: once real sessions exist, take the
    bottom and top quartile of observed loads as the new LOW / HIGH."""
    xs = sorted(relative_loads)
    pick = lambda p: xs[min(len(xs) - 1, max(0, round(p / 100 * (len(xs) - 1))))]
    return pick(lo_pct), pick(hi_pct)


def load_band(relative_load: float) -> str:
    """One effort word: low, mid, or high."""
    if relative_load < LOW_LOAD:
        return "low"
    if relative_load > HIGH_LOAD:
        return "high"
    return "mid"


def load_bars(relative_load: float) -> int:
    """The 1-5 meter for the UI. Bar 1 always means low, bar 5 always means
    high (same comparisons as load_band, so they can never disagree); bars
    2-4 just split the middle into thirds."""
    third = (HIGH_LOAD - LOW_LOAD) / 3
    return (
        1
        + (relative_load >= LOW_LOAD)
        + (relative_load > LOW_LOAD + third)
        + (relative_load > LOW_LOAD + 2 * third)
        + (relative_load > HIGH_LOAD)
    )


def next_level(correct: bool, level: int, band: str) -> tuple[int, str]:
    """The six-cell table. Hitting the top or bottom gets its own word
    (ceiling / floor) because a run of those means something clinical."""
    if correct:
        if band == "high":
            return level, "hold"  # EEG cell: right, but working hard - stay here
        return (level, "ceiling") if level == MAX_LEVEL else (level + STEP, "up")
    if band == "low":
        return level, "repeat"  # EEG cell: no effort behind the miss - same level, new item
    return (level, "floor") if level == MIN_LEVEL else (level - STEP, "down")


# What the clinician reads for each way a session can end.
END_TEXT = {
    "converged": "Three consecutive correct at one level",
    "ceiling": "May exceed the range of this task set",
    "floor": "Could not perform at the lowest level",
    "max_tasks": "Maximum task count reached without convergence",
}


def should_end(history) -> tuple[bool, str | None, int | None]:
    """Is the session over, and what may we claim? Four different endings,
    kept separate because flattening them lies: three failures at level 1
    is a floor, not "converged at level 1"."""
    tail = history[-CONVERGENCE_RUN:]
    if len(tail) == CONVERGENCE_RUN and all(t.level == tail[0].level for t in tail):
        if all(t.result == "correct" for t in tail):
            # All three right at the top WITHOUT effort: the test ran out of
            # difficulty, so say "may exceed", not "converged".
            if tail[0].level == MAX_LEVEL and all(
                t.trusted and load_band(t.load_log) == "low" for t in tail
            ):
                return True, "ceiling", MAX_LEVEL
            return True, "converged", tail[0].level
        if tail[0].level == MIN_LEVEL and all(t.result != "correct" for t in tail):
            return True, "floor", MIN_LEVEL
    if len(history) >= MAX_TASKS:
        # Cap reached: report the most-visited level, and when two levels tie,
        # claim the LOWER one - the cautious statement wins.
        counts: dict[int, int] = {}
        for t in history:
            counts[t.level] = counts.get(t.level, 0) + 1
        best = max(counts.values())
        return True, "max_tasks", min(l for l, c in counts.items() if c == best)
    return False, None, None


@dataclass
class Decision:
    """Everything the UI needs after one task; the UI computes nothing."""

    next_level: int
    reason: str  # up | down | hold | repeat | ceiling | floor
    reason_text: str  # the sentence the clinician reads
    load_bars: int | None  # 1-5 meter, None when the window was untrusted
    load_multiple: float | None  # the "1.4x baseline" number, None when untrusted
    quadrant: str  # efficient | effortful | struggling | disengaged
    flags: list[str] = field(default_factory=list)  # "disengaged", "untrusted"
    ended: bool = False
    end_reason: str | None = None
    final_level: int | None = None


_MOVE = {
    "up": "stepping up to level {new}",
    "down": "easing to level {new}",
    "hold": "holding at level {new}",
    "repeat": "repeating level {new} with a new item",
    "ceiling": "already at the top level, holding at {new}",
    "floor": "already at the lowest level, staying at {new}",
}

_VERDICT = {"correct": "Correct", "incorrect": "Wrong", "timeout": "Timed out"}


def decide(trial, history) -> Decision:
    """One answered task in, one Decision out. `history` is everything before
    this task. Timeouts count as wrong (no answer is not a right answer)."""
    correct = trial.result == "correct"
    # Can't trust the window? Use the mid column - plain adaptive testing.
    band = load_band(trial.load_log) if trial.trusted else "mid"
    new_level, reason = next_level(correct, trial.level, band)

    # Name the cell instead of inventing a blended score with no units.
    quadrant = ("effortful" if band == "high" else "efficient") if correct else (
        "disengaged" if band == "low" else "struggling"
    )

    flags = [] if trial.trusted else ["untrusted"]
    # One no-effort miss can be a fluke; two in a row is worth telling the clinician.
    prev = history[-1] if history else None
    if reason == "repeat" and prev and prev.result != "correct" and prev.trusted \
            and load_band(prev.load_log) == "low":
        flags.append("disengaged")

    effort = f"{band} effort" if trial.trusted else "untrusted signal"
    text = f"{_VERDICT[trial.result]} at {effort} - {_MOVE[reason].format(new=new_level)}."

    ended, end_reason, final_level = should_end(list(history) + [trial])
    return Decision(
        next_level=new_level,
        reason=reason,
        reason_text=text,
        load_bars=load_bars(trial.load_log) if trial.trusted else None,
        load_multiple=round(math.exp(trial.load_log), 2) if trial.trusted else None,
        quadrant=quadrant,
        flags=flags,
        ended=ended,
        end_reason=end_reason,
        final_level=final_level,
    )
