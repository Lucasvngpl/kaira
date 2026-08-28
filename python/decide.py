"""Adaptive staircase - SKELETON, hand-written by the team.

Owner: Lucas. Deliberately empty of real code (buildathon AI policy): the
effort-gated adaptation IS the product, so the team writes and defends it.

Interface (fixed - session.py is built against it):
    decide(state: DomainState, trial: Trial) -> tuple[Action, str]

Types live in session.py (DomainState, Trial). Action is one of the strings
in session.ACTIONS, and session.py applies it mechanically:
    "advance" -> difficulty level +1 (capped at 5)
    "hold"    -> level unchanged
    "ease"    -> level -1 (floored at 1)
    "flag"    -> level unchanged AND the trial is marked flag=True:
                 wrong with no measurable effort behind it - disengagement,
                 not deficit. This flag is the product's differentiator; the
                 report surfaces it separately.
The second element of the tuple is a short machine-readable reason
("correct_engaged", "incorrect_disengaged", ...) stored per task and shown in
the report table.

TODO(team) - the logic this file exists for (HANDOFF section 1):
  - Right without effort (load well below band): the task was too easy -> advance.
  - Right at normal effort (load inside band): working level -> hold; three of
    these in a row at one level is convergence (session.py checks that).
  - Wrong while working hard (load inside/above band): genuine limit -> ease.
  - Wrong without effort (load well below band): do NOT assume deficit ->
    flag disengagement, hold the level.
  - Timeout arrives as result="timeout": treat like a wrong answer here;
    session.py already records it separately (slow-but-correct and wrong are
    clinically different and must not collapse).
  - Respect trial.trusted: an artifact-contaminated load number should not
    drive a level change.
"""

from __future__ import annotations


def decide(state: "DomainState", trial: "Trial") -> tuple[str, str]:
    """Pick the next action from the answered trial and the session state.

    TODO(team): replace the placeholder with the effort-gated rules in the
    module docstring. The placeholder below IGNORES THE EEG ENTIRELY - it
    exists only so the demo adapts and converges before this file is real.
    """
    # PLACEHOLDER - not the algorithm:
    if trial.result == "correct":
        return "hold", "placeholder_correct"
    return "ease", "placeholder_not_correct"
