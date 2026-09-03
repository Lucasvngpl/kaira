# Kaira - working notes for Claude

Buildathon project (NOVA Biotech McGill "NeuroLoop", build day 2026-09-12, judging 2026-09-13).
Full brief: `~/Downloads/HANDOFF.md`. Setup and run commands: `README.md`.

## Hard scope boundary

`python/stream.py`, `preprocess.py`, `features.py`, `decide.py` are HAND-WRITTEN by the team.
The competition AI policy requires every line of the algorithm to be defensible on the spot, so Claude does not implement them beyond the existing skeletons unless Lucas explicitly says otherwise.
(Standing exceptions, Lucas-approved: `features.py` is his hand-written implementation (2026-08-28, interface name `cognitive_load`), and `decide.py` was implemented 2026-08-31 from his written spec (`~/Downloads/decide_py_prompt.md`) - a six-cell table where only two cells use the EEG, plus termination via `should_end` (five endings: converged / ceiling / floor / no_effort / max_tasks; the no-effort ladder is 2 misses = disengaged flag, 3 = stop and ask for a redo).)
Everything else (`session.py`, `tasks.py`, `api/`, `ui/`) is scaffold and fair game.

## Judges read this repo line by line

The AI policy means the team defends every line on stage.
So all code, scaffold included, must read like a careful human wrote it: short humanized comments that say why, simple elegant flow, no boilerplate, no cleverness that needs a paragraph to excuse.
Anything that smells generated is a liability in the room.

## The data is fake until the real pipeline lands

- `features.cognitive_load` is real (Welch theta/alpha), but the stub stream feeds it white noise, so loads hover near 1.00x with small jitter: near-uniform bars and a wiggling sparkline are expected until real acquisition lands.
- Kaira is a LIVE closed loop: a session's EEG is recorded from the eego amplifier in real time and feeds the next-task decision as it happens. No prerecorded file ever drives a session.
- `~/NOVA_ANT` (`EEG_flipcup`, `Eyes open eyes closed`, `Behavioral Data`, `Video`) holds EXAMPLE recordings from the same hardware, for validating the signal code offline only: the EO-EC 33x occipital-alpha check, and whether the load metric separates flip-cup outcomes. Copy what is needed into `data/` (gitignored).
- So "proper data to test with" arrives in two steps: first the offline validation of `features.cognitive_load` against those examples (still to run), then live closed-loop runs (synthetic board anywhere, the real amplifier on Windows).
- Until then, never judge visuals or adaptive behaviour by the noise-driven values; verify wiring with injected values instead (`python/smoke_test.py`, four-quadrant section).
- decide's thresholds are fixed log units, `LOW_LOAD`/`HIGH_LOAD` = +-0.30 (0.74x-1.35x), picked by the 2026-08-31 band-width sweep on the oddball recording (same right-level accuracy as +-0.405, more convergence, one task faster). One person's noise, so `calibrate_bands()` on real sessions stays the settled answer. With noise-driven load hovering at 1.0x, most demo tasks land mid: corrects climb, wrongs ease.
- The pipeline is already natural-log end to end (2026-09-02 review): `cognitive_load` returns ln(theta)-ln(alpha), the baseline is subtracted in log space (== ln(current/baseline), the team doc's formula), thresholds are ln of a multiplier. The team doc still says T = ln(1.5) = 0.405; Lucas is updating it to the sweep's +-0.30.

## The z-score plumbing, in plain words

- Everyone's brain signal wobbles a different amount even at rest. A fixed threshold like "1.4x baseline" treats a naturally twitchy signal and a naturally steady one the same, which is unfair in both directions.
- So during the resting baseline the session now measures two things: the patient's average load (the zero point) and how much it wobbles around that average (`baseline_sd`, their personal yardstick).
- Every task then gets a z-score: how many of THIS patient's own wobbles above THEIR resting level the effort was. The same shout is loud in a library and inaudible at a concert; z measures against the room the patient's brain actually is.
- Division of labour: the scaffold computes and carries z (`trial.z`, `baseline_sd` in the report). Lucas chose (2026-08-31) to ship decide.py on FIXED log thresholds for now; z stays plumbed and dormant until flip-cup calibration says which units win.
- `BASELINE_SD_FLOOR` in session.py guards the degenerate case: a patient who sat unnaturally still would get a near-zero yardstick and absurd z-scores.
- The clinician display does not change: humans keep seeing "1.4x baseline"; z is for the algorithm and the report JSON.

## Key resources

- Challenge handout: `~/Downloads/Challenge Handout (2).pdf` (requirements, judging, deliverables).
- Hardware: eego amplifier EE-22x user manual `~/Downloads/UDO-SM-0120_ENrev11 eego amplifier EE-22x User Manual 2025-07-01_02 (1).pdf`; waveguard CA-208 cap datasheet `~/Downloads/UDO-SM-0215rev09 CA-208 Datasheet 2020-12-14 (1).pdf`.
- Example recordings and stimulus material (offline validation only, never the live loop): `~/NOVA_ANT`.
- Load-index literature (the science behind `features.cognitive_load`):
  - Dan and Reiner 2017, Int J Psychophysiol (PMID 27592084): defines the cognitive load index as frontal theta (Fz) power over parietal alpha (Pz) power - the ratio Kaira uses.
  - Borghini et al. 2015, IEEE EMBC (PMID 26737704): the same frontal-theta / parietal-alpha ratio as a mental workload index, validated on helicopter pilots.
  - Juras, Hromatko and Vranic 2025, Front Aging Neurosci (PMID 40182761): parietal alpha and theta power predict cognitive training gains in middle-aged adults - supports the aging/decline framing.
- Worked EEG notebooks: github.com/Ildaron/EEG-Signal-Processing-with-Python (band-pass, artefact analysis, real-time processing examples the team can crib from by hand).

## Conventions

- API on `127.0.0.1:8300` (8000 collides with Django dev servers). UI is Vite on 5173; CORS is pinned to that port.
- Restart the API after editing `python/` (it does not run with --reload).
- Keep both suites green: `.venv/bin/python python/smoke_test.py` and `.venv/bin/python tests/test_decide.py`.
- The UI follows the UQwest staff house style (`~/Side-Projects/UEP/frontend`): plain CSS with tokens, DM Sans + Source Serif 4, hairline cards at 12px radius, `kr-`/`sn-`/`rp-` class prefixes, axios behind `src/api.js`, hand-rolled chart legends, why-comments everywhere.
- Live load is polled at 4 Hz (matches the real pipeline's 250 ms window step); the run screen's 1-5 effort meter and every clinician sentence (`reason_text`) are computed server-side - the UI computes nothing.
- The resting baseline is adaptive (team protocol, 2026-09-02): record at least 90 s, then stop as soon as the last two 30 s mean-CLI windows agree within 10% (a log distance, `session.BASELINE_TOLERANCE`), capped at 3 minutes. Never settles -> plain 3-minute average plus a `baseline_stable=false` flag (UI tells the clinician to check electrodes and consider redoing). Rehearse with `KAIRA_BASELINE_SECONDS=15`; overrides at or below 90 s skip the settling logic. Never shorten the constants themselves.
- `http://localhost:5173/?demo=report` deep-links to the report screen with fabricated PT-SAMPLE data (`ui/src/sampleReport.js`) for UI work without running a session.
- No em dashes anywhere, including UI copy and comments; use a plain dash.
- Work happens on branches `lucas` and `aarnav`; changes to the fixed Python interface need both.
