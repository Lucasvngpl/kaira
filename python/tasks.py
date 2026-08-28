"""The task bank: domain -> difficulty level (1-5) -> tasks.

Each task is what the CLINICIAN needs on screen: a prompt they read aloud
verbatim (instructions plus stimulus) and the scoring criterion they check
the patient's answer against. The patient never sees the screen, so the
prompt carries the full administration script.

Demo domain is Memory. Difficulty scales on classic memory-span grounds:
digit spans run from 3 (well under typical adult span) to 7 forward /
5 backward (at or past it), word lists from 3 to 8 items, and paired
associates from 2 related pairs to 6 mostly unrelated ones - unrelated pairs
are the standard "hard associates" manipulation. Backward span only appears
from level 3 because it adds a manipulation cost on top of storage.

Attention and Language exist as empty structures so the extension path is
obvious, but only Memory is populated for the buildathon demo.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Task:
    id: str
    domain: str
    level: int  # 1 (easiest) .. 5 (hardest)
    kind: str  # word_list | digit_span | digit_span_backward | paired_associates
    prompt: str  # read aloud verbatim by the clinician
    answer: str  # scoring criterion the clinician checks against


LEVEL_MIN = 1
LEVEL_MAX = 5

# Administration scripts repeated across tasks, kept in one place so every
# task of a kind is administered identically.
_WORDS_INTRO = (
    'Say: "I am going to read a short list of words. When I finish, repeat '
    'back as many as you can, in any order." Read at one word per second: '
)
_DIGITS_FWD_INTRO = (
    'Say: "I will say some numbers. When I stop, repeat them in the same '
    'order." Read at one digit per second: '
)
_DIGITS_BWD_INTRO = (
    'Say: "I will say some numbers. When I stop, repeat them BACKWARDS, '
    'last number first." Read at one digit per second: '
)
_PAIRS_INTRO = (
    'Say: "I will read pairs of words that belong together. Listen '
    'carefully." Read the pairs at one pair per two seconds: '
)
_PAIRS_ASK = ' Then say: "Now I give you the first word of each pair; tell me its partner." Ask: '


def _words(task_id: str, level: int, items: str, count: int) -> Task:
    return Task(
        id=task_id, domain="Memory", level=level, kind="word_list",
        prompt=_WORDS_INTRO + items + ".",
        answer=f"{items.lower().replace(' - ', ', ')} (any order, all {count} required)",
    )


def _digits(task_id: str, level: int, seq: str, backward: bool = False) -> Task:
    intro = _DIGITS_BWD_INTRO if backward else _DIGITS_FWD_INTRO
    digits = seq.split(" - ")
    expected = " ".join(reversed(digits)) if backward else " ".join(digits)
    return Task(
        id=task_id, domain="Memory", level=level,
        kind="digit_span_backward" if backward else "digit_span",
        prompt=intro + seq + ".",
        answer=f"{expected} (exact order)",
    )


def _pairs(task_id: str, level: int, pairs: list[tuple[str, str]]) -> Task:
    read = ", ".join(f"{a} - {b}" for a, b in pairs)
    ask = " ... ".join(f"{a}?" for a, b in pairs)
    key = "; ".join(f"{a} -> {b.lower()}" for a, b in pairs)
    return Task(
        id=task_id, domain="Memory", level=level, kind="paired_associates",
        prompt=_PAIRS_INTRO + read + "." + _PAIRS_ASK + ask,
        answer=f"{key} (all {len(pairs)} required, any order of pairs)",
    )


_MEMORY: dict[int, list[Task]] = {
    1: [
        _words("mem_l1_001", 1, "CANDLE - RIVER - SHOE", 3),
        _words("mem_l1_002", 1, "BUTTON - CLOUD - FORK", 3),
        _digits("mem_l1_003", 1, "5 - 8 - 2"),
        _digits("mem_l1_004", 1, "3 - 9 - 6"),
        _pairs("mem_l1_005", 1, [("DOG", "LEASH"), ("CUP", "SAUCER")]),
    ],
    2: [
        _words("mem_l2_001", 2, "GARDEN - PENCIL - STORM - BREAD", 4),
        _words("mem_l2_002", 2, "MIRROR - TRAIN - APPLE - GLOVE", 4),
        _digits("mem_l2_003", 2, "7 - 2 - 8 - 5"),
        _digits("mem_l2_004", 2, "4 - 1 - 9 - 3"),
        _pairs("mem_l2_005", 2, [("KEY", "LOCK"), ("BABY", "CRADLE"), ("PEN", "INK")]),
    ],
    3: [
        _words("mem_l3_001", 3, "ANCHOR - VELVET - PIANO - LANTERN - WHEAT", 5),
        _words("mem_l3_002", 3, "TUNNEL - ORANGE - HAMMER - ISLAND - WOOL", 5),
        _digits("mem_l3_003", 3, "6 - 1 - 9 - 4 - 7"),
        _digits("mem_l3_004", 3, "8 - 3 - 5 - 2 - 9", backward=True),
        _pairs("mem_l3_005", 3, [("NORTH", "BUTTER"), ("CHAIR", "OCEAN"), ("SILVER", "GRAPE"), ("WINDOW", "TIGER")]),
    ],
    4: [
        _words("mem_l4_001", 4, "MARBLE - FOREST - TRUMPET - CANDLE - RIBBON - HARBOR", 6),
        _words("mem_l4_002", 4, "SADDLE - WINTER - COPPER - MEADOW - JACKET - ONION", 6),
        _digits("mem_l4_003", 4, "2 - 9 - 4 - 7 - 1 - 6"),
        _digits("mem_l4_004", 4, "5 - 8 - 1 - 6 - 3", backward=True),
        _pairs("mem_l4_005", 4, [("CLOUD", "PENCIL"), ("RIVER", "HELMET"), ("SUGAR", "ENGINE"), ("MOUNTAIN", "SPOON"), ("LETTER", "FROG")]),
    ],
    5: [
        _words("mem_l5_001", 5, "COMPASS - THUNDER - BLANKET - ORCHARD - NEEDLE - GRANITE - PARROT - VINEGAR", 8),
        _words("mem_l5_002", 5, "LADDER - CRYSTAL - MUSTARD - FALCON - CARPET - WHISTLE - WALNUT - PILLOW", 8),
        _digits("mem_l5_003", 5, "9 - 2 - 6 - 3 - 8 - 1 - 5"),
        _digits("mem_l5_004", 5, "7 - 1 - 8 - 4 - 2", backward=True),
        _pairs("mem_l5_005", 5, [("VELVET", "THUNDER"), ("CACTUS", "MIRROR"), ("BRIDGE", "LEMON"), ("SOLDIER", "TEAPOT"), ("GARLIC", "PIANO"), ("CURTAIN", "ANVIL")]),
    ],
}

# TODO(team): populate after the buildathon; the structure is identical to
# _MEMORY. Attention wants sustained/selective tasks (digit cancellation read
# aloud, serial subtraction); Language wants naming, fluency and sentence
# repetition, scaled by frequency and length.
_ATTENTION: dict[int, list[Task]] = {}
_LANGUAGE: dict[int, list[Task]] = {}

BANK: dict[str, dict[int, list[Task]]] = {
    "Memory": _MEMORY,
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
