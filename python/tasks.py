"""The task bank: domain -> difficulty level (1-5) -> tasks.

Each task holds what the CLINICIAN reads and checks; the stimulus itself
shows on the patient display (the `image` field).

Visuospatial is Alice's set (2026-09-11): ten everyday objects, each drawn
at five degradation levels - level 1 complete, level 5 fragments. The
patient names the object; recognising it from less is what makes higher
levels harder. PNGs live in ui/public/tasks, spliced from her grid; a new
grid means re-splicing and nothing else.

Known trade-off: a patient who climbs meets an object again, more degraded,
having already named it. Accepted for a 10-object buildathon set.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Task:
    id: str
    domain: str
    level: int  # 1 (easiest) .. 5 (hardest)
    kind: str
    prompt: str  # read aloud verbatim by the clinician
    answer: str  # scoring criterion the clinician checks against
    # Path under ui/public (e.g. "/tasks/vis_chair_l3.png") shown on the
    # PATIENT display; empty for spoken-only tasks.
    image: str = ""


LEVEL_MIN = 1
LEVEL_MAX = 5

# One script for every visuospatial item: the level changes the drawing,
# never the instructions, so no level gets a verbal hint the others lack.
_VIS_PROMPT = 'Say: "Look at the drawing on the screen. What object is it?"'

# (file stem, what the clinician accepts as right)
_OBJECTS = [
    ("chair", "chair"),
    ("umbrella", "umbrella"),
    ("car", "car (any car word counts)"),
    ("tree", "tree"),
    ("cup", "cup (mug counts)"),
    ("fish", "fish"),
    ("key", "key"),
    ("flower", "flower"),
    ("book", "book"),
    ("clock", "clock (alarm clock counts)"),
]

_VISUOSPATIAL: dict[int, list[Task]] = {
    level: [
        Task(
            id=f"vis_l{level}_{n:03d}",
            domain="Visuospatial",
            level=level,
            kind="degraded_object",
            prompt=_VIS_PROMPT,
            answer=answer,
            image=f"/tasks/vis_{stem}_l{level}.png",
        )
        for n, (stem, answer) in enumerate(_OBJECTS, start=1)
    ]
    for level in range(LEVEL_MIN, LEVEL_MAX + 1)
}

# TODO(team): populate after the buildathon; the structure is identical to
# _VISUOSPATIAL. Attention wants sustained/selective tasks; Language wants
# naming, fluency and sentence repetition.
_ATTENTION: dict[int, list[Task]] = {}
_LANGUAGE: dict[int, list[Task]] = {}

BANK: dict[str, dict[int, list[Task]]] = {
    "Visuospatial": _VISUOSPATIAL,
    "Attention": _ATTENTION,
    "Language": _LANGUAGE,
}


def domains() -> list[str]:
    """All domains the bank knows, populated or not."""
    return list(BANK)


def has_tasks(domain: str) -> bool:
    """True when a domain has at least one task at some level (i.e. is runnable)."""
    return any(BANK.get(domain, {}).values())


def get_tasks(domain: str, level: int) -> list[Task]:
    """Tasks for one domain at one level; empty list when none exist."""
    return BANK.get(domain, {}).get(level, [])
