"""Adaptive staircase - SKELETON, hand-written by the team.

Owner: Lucas. Deliberately empty of real code (buildathon AI policy): the
effort-gated adaptation IS the product, so the team writes and defends it.

Interface (fixed - session.py is built against it):
    decide(state: DomainState, trial: Trial) -> tuple[Action, str]   # per-trial difficulty policy
    converged(state: DomainState) -> int | None                      # stopping rule

Both halves of the adaptive logic live here on purpose: when the session
ends is a claim about when you have MEASURED someone's level, and a judge
will ask the team to justify it - so it belongs in the hand-written file,
not in the scaffold. session.py applies whatever this module returns,
mechanically.

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
  - z is plumbed and waiting: trial.z = trial.load_log / state.baseline_sd,
    i.e. effort in units of THIS patient's own resting variability. Write
    the real thresholds in z (per the team doc) and calibrate the values on
    the flip-cup recordings; LOAD_BAND in multiples then retires.
"""

from __future__ import annotations

# How many consecutive correct answers, at one level, prove that level.
CONSECUTIVE_TO_CONVERGE = 3

# The useful-effort band, as multiples of the patient's own resting baseline.
# DEMO VALUE: the synthetic stream is white noise, so cognitive_load hovers
# around 1.00x baseline and the floor must sit below 1.0 or the demo could
# never converge. Once real recordings drive the pipeline, retighten to
# something like (1.3, 3.0): with a floor below 1.0 the "wrong without
# effort" branch can never fire, and that flag is the product's
# differentiator. The band in force is written into every report, so a
# stale value stays visible.
LOAD_BAND = (0.8, 3.0)


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


def converged(state: "DomainState") -> int | None:
    """The stopping rule: has this session measured the patient's level?

    Returns the established level, or None to keep testing. The session ends
    when the last CONSECUTIVE_TO_CONVERGE trials are all correct, at one
    difficulty level, with trusted load readings inside LOAD_BAND.

    Why each condition earns its place:
      - Three in a row: one correct answer can be a guess or a good day;
        a run at the same level is the standard staircase evidence bar.
      - One level: correct answers scattered across levels prove range,
        not a level. The claim is "functions AT level N".
      - Inside the band: a correct answer with no effort behind it says the
        task was too easy, not that the level is established; effort in the
        useful range is what validates the measurement. That validation is
        what a pen-and-paper test cannot do.
      - Trusted only: an artifact-contaminated load reading cannot validate
        anything.
    """
    tail = state.history[-CONSECUTIVE_TO_CONVERGE:]
    if len(tail) < CONSECUTIVE_TO_CONVERGE:
        return None
    lo, hi = LOAD_BAND
    if all(
        t.result == "correct" and t.level == tail[0].level and t.trusted and lo <= t.load <= hi
        for t in tail
    ):
        return tail[0].level
    return None
