"""Session orchestrator: owns one assessment session's state and sequencing.

This is scaffold-owned plumbing (fully implemented, unlike the four skeleton
modules). It never interprets EEG and never chooses difficulty on its own:
signal work lives in stream/preprocess/features, adaptation policy in
decide. This file only wires them together and keeps the books:

    stream.get_window -> preprocess.clean -> features.cognitive_load
                                   |
    clinician result  ->  decide.decide(state, trial)  ->  apply action

Lifecycle: begin() -> poll baseline_status() until done -> loop
[next_task() -> live_load() while the clinician runs it -> submit_answer()]
-> ends when decide.should_end() says so (termination is part of the graded
algorithm, so ALL of it lives in decide.py) -> report().

Trial and DomainState are defined here; decide.py reads them duck-typed, so
there is no circular import (session imports decide, never the reverse).
"""

from __future__ import annotations

import math
import statistics
import time
import uuid
from dataclasses import dataclass, field
from datetime import date

import decide
import features
import preprocess
import stream
import tasks

# --- Tunables (session-level policy, not signal processing) -----------------

# Resting baseline, team protocol (2026-09-02): record at least 90 s, then
# stop as soon as the signal has settled - the last two 30 s means within
# 10% of each other - capped at 3 minutes. A baseline that never settles
# falls back to the plain 3-minute average, flagged so the clinician can
# check electrodes and decide whether to redo it. For rehearsal the API
# honours KAIRA_BASELINE_SECONDS; an override at or below the minimum skips
# the settling logic (plain average over that time, no flag).
BASELINE_SECONDS = 180.0  # the cap
BASELINE_MIN_SECONDS = 90.0
BASELINE_CHECK_SECONDS = 30.0
# "Within 10%" on a ratio scale is a log distance, same units as the loads.
BASELINE_TOLERANCE = math.log(1.10)

# Window length per load sample. 2 s gives the (future, real) Welch estimate
# enough samples at 512 Hz for stable low-frequency bands.
SAMPLE_SECONDS = 2.0

# All decision policy (start level, task cap, thresholds, termination) lives
# in decide.py - session only holds state and applies Decisions mechanically.
# One sanity check keeps decide's level range honest against the task bank.
assert (decide.MIN_LEVEL, decide.MAX_LEVEL) == (tasks.LEVEL_MIN, tasks.LEVEL_MAX)

# Floor for the baseline's standard deviation (log units). z divides by the
# SD, and a patient who sat unusually still would otherwise get a tiny SD
# and absurdly inflated z-scores; the floor caps how much stillness can
# amplify. Team-tunable once real recordings show typical resting spread.
BASELINE_SD_FLOOR = 0.05

# The movement word shown in the report's action column, bucketed from
# decide's richer reason keys (clamps read as their stationary movement).
ACTION_WORD = {"up": "up", "down": "down", "hold": "hold", "ceiling": "hold",
               "repeat": "repeat", "floor": "repeat"}


class SessionStateError(RuntimeError):
    """Raised when a call arrives in the wrong phase (baseline not done, session over)."""


@dataclass
class Trial:
    """One administered task, as decide.py sees it and as the report records it."""

    n: int
    task_id: str
    kind: str  # word_list | digit_span | ... - the report shows humans a name, not an id
    level: int
    result: str  # "correct" | "incorrect" | "timeout"
    rt: float  # seconds, from the clinician's stopwatch
    load: float  # multiple of baseline (exp of load_log) - what humans read
    load_log: float  # relative load in log units - what the math uses
    z: float  # load_log / baseline SD: how unusual this reading is FOR THIS patient
    trusted: bool
    # Filled in from the Decision after decide.decide() runs:
    action: str = ""  # movement word: up | down | hold | repeat
    reason: str = ""  # decide's machine key: up | down | hold | repeat | ceiling | floor
    reason_text: str = ""  # the clinician-facing sentence, straight from decide
    quadrant: str = ""  # efficient | effortful | struggling | disengaged
    bars: int | None = None  # 1-5 effort meter, None when untrusted
    flags: list[str] = field(default_factory=list)
    flag: bool = False  # kept for the report contract: True iff "disengaged" in flags


@dataclass
class DomainState:
    """The session's running state; decide.py reads only the history."""

    domain: str
    level: int
    baseline: float  # resting load index, log units (the mean of the rest samples)
    baseline_sd: float = 0.0  # spread of those samples - this patient's own noise floor
    history: list[Trial] = field(default_factory=list)


class Session:
    """State and sequencing for one patient session. The API wraps these methods 1:1."""

    def __init__(self, patient_ref: str, domain: str):
        if domain not in tasks.domains():
            raise ValueError(f"unknown domain: {domain!r}")
        if not tasks.has_tasks(domain):
            raise ValueError(f"domain {domain!r} has no tasks yet (only Memory is populated)")
        self.id = uuid.uuid4().hex[:12]
        self.patient_ref = patient_ref
        self.date = date.today().isoformat()
        self.state = DomainState(domain=domain, level=decide.START_LEVEL, baseline=0.0)
        # Baseline recording starts at creation; progress is wall-clock.
        self._baseline_t0 = time.monotonic()
        self._baseline_samples: list[tuple[float, float]] = []  # (seconds since start, load)
        self._baseline_done = False
        self.baseline_seconds = 0.0  # how long the baseline actually ran
        self.baseline_stable = True  # False only when the settling check ran and never passed
        # Task bookkeeping.
        self._current: tasks.Task | None = None
        self._task_samples: list[tuple[float, bool]] = []  # (load_log_abs, trusted) polled during a task
        self._used_ids: list[str] = []  # in administration order, for least-recently-used reuse
        self.ended = False
        self.converged = False
        self.end_reason = ""
        self.final_level: int | None = None

    # --- signal sampling ----------------------------------------------------

    def _sample(self) -> tuple[float, bool]:
        """One absolute load reading through the (stub) signal chain."""
        window = stream.get_window(SAMPLE_SECONDS)
        cleaned, trusted = preprocess.clean(window, stream.fs, stream.ch_names)
        return features.cognitive_load(cleaned, stream.fs, stream.ch_names), trusted

    def _relative(self, load_log_abs: float) -> tuple[float, float]:
        """(load_log, multiple) of an absolute reading vs this patient's baseline."""
        rel = features.relative_load(load_log_abs, self.state.baseline)
        return rel, math.exp(rel)

    # --- baseline -----------------------------------------------------------

    def baseline_status(self) -> dict:
        """Poll during the resting baseline; each poll also takes one load sample.

        Sampling on poll (rather than a background thread) keeps the session
        loop single-threaded and works identically for stub and real stream.
        The mean is taken in log units - that is the whole point of the log.
        """
        elapsed = time.monotonic() - self._baseline_t0
        if not self._baseline_done:
            value, trusted = self._sample()
            if trusted:
                self._baseline_samples.append((elapsed, value))
            adaptive = BASELINE_SECONDS > BASELINE_MIN_SECONDS  # rehearsal overrides skip settling
            if adaptive and elapsed >= BASELINE_MIN_SECONDS and self._settled(elapsed):
                self._finalize_baseline(elapsed, stable=True)
            elif elapsed >= BASELINE_SECONDS:
                # Cap reached: plain average of everything. If the settling
                # check was on and never passed, flag it for the clinician.
                self._finalize_baseline(elapsed, stable=not adaptive)
        return {
            "done": self._baseline_done,
            "progress": min(1.0, elapsed / BASELINE_SECONDS),
            "stable": self.baseline_stable,
            "seconds": round(self.baseline_seconds if self._baseline_done else elapsed, 1),
        }

    def _settled(self, now: float) -> bool:
        """Has the signal settled? The last 30 s vs the 30 s before that."""
        recent = [v for t, v in self._baseline_samples if t >= now - BASELINE_CHECK_SECONDS]
        previous = [v for t, v in self._baseline_samples
                    if now - 2 * BASELINE_CHECK_SECONDS <= t < now - BASELINE_CHECK_SECONDS]
        if min(len(recent), len(previous)) < 5:  # too few polls to judge either half
            return False
        return abs(statistics.fmean(recent) - statistics.fmean(previous)) < BASELINE_TOLERANCE

    def _finalize_baseline(self, elapsed: float, stable: bool) -> None:
        values = [v for _, v in self._baseline_samples]
        if not values:  # client never polled; one sample beats none
            values = [self._sample()[0]]
        self.state.baseline = statistics.fmean(values)
        # The baseline's spread is the patient's personal yardstick: decide.py
        # can express effort as z = load_log / baseline_sd, i.e. "how many of
        # THIS patient's own resting wobbles above THEIR resting level".
        spread = statistics.stdev(values) if len(values) >= 2 else 0.0
        self.state.baseline_sd = max(spread, BASELINE_SD_FLOOR)
        self.baseline_seconds = elapsed
        self.baseline_stable = stable
        self._baseline_done = True

    def _require_baseline(self) -> None:
        # Tolerate clients that slept through the baseline without polling.
        # No polls means no settling verdict, so no instability flag either.
        if not self._baseline_done:
            elapsed = time.monotonic() - self._baseline_t0
            if elapsed >= BASELINE_SECONDS:
                self._finalize_baseline(elapsed, stable=True)
            else:
                raise SessionStateError("baseline recording still in progress")

    # --- task flow ----------------------------------------------------------

    def next_task(self) -> dict:
        """The task the clinician should administer now. Idempotent until answered."""
        if self.ended:
            raise SessionStateError("session has ended; fetch the report")
        self._require_baseline()
        if self._current is None:
            self._current = self._pick_task()
            self._used_ids.append(self._current.id)
            self._task_samples = []  # load buffer belongs to exactly one task
        t = self._current
        return {
            "task_id": t.id,
            "level": t.level,
            "prompt": t.prompt,
            "answer": t.answer,
            "n": len(self.state.history) + 1,
            "total_max": decide.MAX_TASKS,
        }

    def _pick_task(self) -> tasks.Task:
        """Prefer an unseen task at the current level; reuse least-recently-used when exhausted."""
        pool = tasks.get_tasks(self.state.domain, self.state.level)
        if not pool:
            raise SessionStateError(f"no tasks at level {self.state.level} for {self.state.domain}")
        for t in pool:
            if t.id not in self._used_ids:
                return t
        return min(pool, key=lambda t: self._used_ids.index(t.id))

    def live_load(self) -> dict:
        """Current load as a multiple of baseline, polled ~1 Hz by the UI.

        While a task is active the sample is also buffered: the task's
        recorded load is the mean of what was measured while the patient
        actually worked on it, not one lucky window at submit time.
        """
        value, trusted = self._sample()
        if self._baseline_done:
            if self._current is not None:
                self._task_samples.append((value, trusted))
            _, multiple = self._relative(value)
        else:
            # Mid-baseline there is no reference yet; compare against the
            # provisional mean so the readout is defined and drifts to ~1.0x.
            provisional = statistics.fmean(v for _, v in self._baseline_samples) if self._baseline_samples else value
            multiple = math.exp(features.relative_load(value, provisional))
        # The 1-5 meter is server-computed from decide's own constants; the
        # UI renders it and computes nothing.
        bars = decide.load_bars(math.log(multiple)) if trusted else None
        return {"load": round(multiple, 2), "trusted": trusted, "bars": bars}

    def submit_answer(self, task_id: str, result: str, elapsed_seconds: float) -> dict:
        """Record the clinician's verdict, let decide.py act on it, apply the action."""
        if self.ended:
            raise SessionStateError("session has ended; fetch the report")
        if self._current is None:
            raise SessionStateError("no task is active; call next-task first")
        if task_id != self._current.id:
            raise ValueError(f"answer is for {task_id!r} but the active task is {self._current.id!r}")
        if result not in ("correct", "incorrect", "timeout"):
            raise ValueError(f"result must be correct|incorrect|timeout, got {result!r}")

        load_log, load, trusted = self._task_load()
        trial = Trial(
            n=len(self.state.history) + 1,
            task_id=task_id,
            kind=self._current.kind,
            level=self.state.level,
            result=result,
            rt=round(float(elapsed_seconds), 1),
            load=round(load, 2),
            load_log=load_log,
            z=round(load_log / self.state.baseline_sd, 2),
            trusted=trusted,
        )

        d = decide.decide(trial, self.state.history)
        trial.action = ACTION_WORD[d.reason]
        trial.reason = d.reason
        trial.reason_text = d.reason_text
        trial.quadrant = d.quadrant
        trial.bars = d.load_bars
        trial.flags = d.flags
        trial.flag = "disengaged" in d.flags

        self.state.level = d.next_level
        self.state.history.append(trial)
        self._current = None
        self._task_samples = []

        if d.ended:
            self.ended = True
            self.converged = d.end_reason == "converged"
            self.end_reason = d.end_reason
            self.final_level = d.final_level
        return {
            "action": trial.action,
            "next_level": self.state.level,
            "load": trial.load,
            "ended": self.ended,  # the server fact; the UI never infers session end
            "converged": self.converged,
            "reason": d.reason,
            "reason_text": d.reason_text,
            "bars": d.load_bars,
            "flags": d.flags,
        }

    def _task_load(self) -> tuple[float, float, bool]:
        """This task's load: mean of trusted samples buffered while it ran.

        Falls back to one fresh sample when nothing was buffered (client that
        never polled live-load), so a load number always exists.
        """
        trusted_values = [v for v, ok in self._task_samples if ok]
        if trusted_values:
            load_log, load = self._relative(statistics.fmean(trusted_values))
            return load_log, load, True
        value, trusted = self._sample()
        load_log, load = self._relative(value)
        return load_log, load, trusted

    # --- report -------------------------------------------------------------

    def report(self) -> dict:
        """The report object per the data contract (HANDOFF section 7).

        Valid mid-session too (converged=false, reason says in progress), so
        nothing crashes if the report screen is opened early.
        """
        h = self.state.history
        answered = [t for t in h if t.result != "timeout"]  # timeouts never answered; their rt is not a time-to-answer
        return {
            "domain": self.state.domain,
            "patient_ref": self.patient_ref,
            "date": self.date,
            # None when the session ended without supporting a level claim
            # (no_effort); mid-session it shows the current working level.
            "final_level": self.final_level if self.ended else self.state.level,
            "level_max": tasks.LEVEL_MAX,  # additive to the contract: the UI shows "Level N of MAX"
            "reason": decide.END_TEXT.get(self.end_reason, "Session in progress"),
            "end_reason": self.end_reason,  # converged | ceiling | floor | max_tasks | no_effort | ""
            "converged": self.converged,
            # Display band derived from decide's thresholds (never stored twice).
            "band": [round(math.exp(decide.LOW_LOAD), 2), round(math.exp(decide.HIGH_LOAD), 2)],
            "baseline_sd": round(self.state.baseline_sd, 3),  # the patient's yardstick behind each z
            "baseline_seconds": round(self.baseline_seconds),
            "baseline_stable": self.baseline_stable,  # False = never settled; clinician judgement call
            "mean_rt": round(statistics.fmean(t.rt for t in answered), 1) if answered else None,
            "accuracy": round(sum(t.result == "correct" for t in h) / len(h), 2) if h else None,
            "disengaged_count": sum(t.flag for t in h),
            # Above ~30% untrusted the whole session's loads deserve caution.
            "untrusted_rate": round(sum(not t.trusted for t in h) / len(h), 2) if h else 0.0,
            "tasks": [
                {
                    "n": t.n,
                    "task_id": t.task_id,
                    "kind": t.kind,
                    "level": t.level,
                    "result": t.result,
                    "load": t.load,
                    "z": t.z,
                    "trusted": t.trusted,
                    "rt": t.rt,
                    "action": t.action,
                    "reason": t.reason,
                    "reason_text": t.reason_text,
                    "quadrant": t.quadrant,
                    "bars": t.bars,
                    "flag": t.flag,
                }
                for t in h
            ],
        }


def begin(patient_ref: str, domain: str) -> Session:
    """Create a session and start its baseline clock. The API stores the object."""
    return Session(patient_ref=patient_ref, domain=domain)
