"""Session orchestrator: owns one assessment session's state and sequencing.

This is scaffold-owned plumbing (fully implemented, unlike the four skeleton
modules). It never interprets EEG and never chooses difficulty on its own:
signal work lives in stream/preprocess/features, adaptation policy in
decide. This file only wires them together and keeps the books:

    stream.get_window -> preprocess.clean -> features.load_index
                                   |
    clinician result  ->  decide.decide(state, trial)  ->  apply action

Lifecycle: begin() -> poll baseline_status() until done -> loop
[next_task() -> live_load() while the clinician runs it -> submit_answer()]
-> ends when decide.converged() says the level is established (the stopping
rule is part of the graded algorithm, so it lives in decide.py) or on the
task cap here -> report().

Shared types (Trial, DomainState, ACTIONS) are defined here and referenced by
decide.py via lazy annotations, so the skeleton needs no imports and there is
no circular import (session imports decide, never the reverse).
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

# Resting-baseline recording length. A real protocol wants 60 s or more of
# quiet rest; 15 s keeps the demo clickable. One constant to change.
BASELINE_SECONDS = 15.0

# Window length per load sample. 2 s gives the (future, real) Welch estimate
# enough samples at 512 Hz for stable low-frequency bands.
SAMPLE_SECONDS = 2.0

# Hard cap so a session that never converges still ends and reports.
MAX_TASKS = 12

# Deliberately BELOW the CAT midpoint (3): the target population is patients
# monitored for cognitive decline, so ability skews low - a spare trial of
# downward headroom is worth more than symmetric information gain. A
# high-functioning patient just spends one easy trial advancing.
LEVEL_START = 2

# The stopping rule and the effort band belong to the adaptive logic, so
# they live in decide.py (decide.CONSECUTIVE_TO_CONVERGE, decide.LOAD_BAND).

# Actions decide.py may return; session applies them mechanically.
ACTIONS = ("advance", "hold", "ease", "flag")

CONVERGED_REASON = "Three consecutive correct at stable load"
MAXED_REASON = "Maximum task count reached without convergence"


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
    trusted: bool
    # Filled in after decide.decide() runs:
    action: str = ""
    reason: str = ""
    flag: bool = False  # wrong answer with no measurable effort = disengagement


@dataclass
class DomainState:
    """Everything decide.py may condition on."""

    domain: str
    level: int
    baseline: float  # resting load index, log units
    band: tuple[float, float] = decide.LOAD_BAND
    level_min: int = tasks.LEVEL_MIN
    level_max: int = tasks.LEVEL_MAX
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
        self.state = DomainState(domain=domain, level=LEVEL_START, baseline=0.0)
        # Baseline recording starts at creation; progress is wall-clock.
        self._baseline_t0 = time.monotonic()
        self._baseline_samples: list[float] = []
        self._baseline_done = False
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
        return features.load_index(cleaned, stream.fs, stream.ch_names), trusted

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
                self._baseline_samples.append(value)
            if elapsed >= BASELINE_SECONDS:
                self._finalize_baseline()
        return {"done": self._baseline_done, "progress": min(1.0, elapsed / BASELINE_SECONDS)}

    def _finalize_baseline(self) -> None:
        if not self._baseline_samples:  # client never polled; one sample beats none
            self._baseline_samples.append(self._sample()[0])
        self.state.baseline = statistics.fmean(self._baseline_samples)
        self._baseline_done = True

    def _require_baseline(self) -> None:
        # Tolerate clients that slept through the baseline without polling.
        if not self._baseline_done:
            if time.monotonic() - self._baseline_t0 >= BASELINE_SECONDS:
                self._finalize_baseline()
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
            "total_max": MAX_TASKS,
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
            provisional = statistics.fmean(self._baseline_samples) if self._baseline_samples else value
            multiple = math.exp(features.relative_load(value, provisional))
        return {"load": round(multiple, 2), "trusted": trusted}

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
            trusted=trusted,
        )

        action, reason = decide.decide(self.state, trial)
        if action not in ACTIONS:
            raise ValueError(f"decide returned unknown action {action!r}")
        trial.action = action
        trial.reason = reason
        trial.flag = action == "flag"  # disengagement: hold the level, mark the trial
        if action == "advance":
            self.state.level = min(self.state.level_max, self.state.level + 1)
        elif action == "ease":
            self.state.level = max(self.state.level_min, self.state.level - 1)

        self.state.history.append(trial)
        self._current = None
        self._task_samples = []

        self._check_end(trial)
        return {
            "action": action,
            "next_level": self.state.level,
            "load": trial.load,
            "converged": self.converged,
            "reason": reason,
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

    def _check_end(self, last: Trial) -> None:
        """decide.converged() owns the stopping rule - when a level counts as
        measured is part of the graded algorithm, not plumbing. Only the
        never-converged task cap is scaffold policy and stays here.
        """
        level = decide.converged(self.state)
        if level is not None:
            self.ended = True
            self.converged = True
            self.final_level = level  # the level they proved, not any post-action level
            self.end_reason = CONVERGED_REASON
        elif len(self.state.history) >= MAX_TASKS:
            self.ended = True
            self.converged = False
            self.final_level = last.level
            self.end_reason = MAXED_REASON

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
            "final_level": self.final_level if self.final_level is not None else self.state.level,
            "level_max": tasks.LEVEL_MAX,  # additive to the contract: the UI shows "Level N of MAX"
            "reason": self.end_reason or "Session in progress",
            "converged": self.converged,
            "band": list(decide.LOAD_BAND),
            "mean_rt": round(statistics.fmean(t.rt for t in answered), 1) if answered else None,
            "accuracy": round(sum(t.result == "correct" for t in h) / len(h), 2) if h else None,
            "disengaged_count": sum(t.flag for t in h),
            "tasks": [
                {
                    "n": t.n,
                    "task_id": t.task_id,
                    "kind": t.kind,
                    "level": t.level,
                    "result": t.result,
                    "load": t.load,
                    "trusted": t.trusted,
                    "rt": t.rt,
                    "action": t.action,
                    "reason": t.reason,
                    "flag": t.flag,
                }
                for t in h
            ],
        }


def begin(patient_ref: str, domain: str) -> Session:
    """Create a session and start its baseline clock. The API stores the object."""
    return Session(patient_ref=patient_ref, domain=domain)
