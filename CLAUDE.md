# Kaira - working notes for Claude

Buildathon project (NOVA Biotech McGill "NeuroLoop", build day 2026-09-12, judging 2026-09-13).
Full brief: `~/Downloads/HANDOFF.md`. Setup and run commands: `README.md`.

## Hard scope boundary

`python/stream.py`, `preprocess.py`, `features.py`, `decide.py` are HAND-WRITTEN by the team.
The competition AI policy requires every line of the algorithm to be defensible on the spot, so Claude does not implement them beyond the existing skeletons unless Lucas explicitly says otherwise.
(Standing exception, Lucas-approved: the stopping rule `decide.converged()` is implemented.)
Everything else (`session.py`, `tasks.py`, `api/`, `ui/`) is scaffold and fair game.

## The data is fake until the real pipeline lands

- `features.load_index` placeholder returns a constant, so every load reads exactly 1.00x baseline: the live sparkline is flat and the report bars are uniform. This is expected, not a bug.
- Kaira is a LIVE closed loop: a session's EEG is recorded from the eego amplifier in real time and feeds the next-task decision as it happens. No prerecorded file ever drives a session.
- `~/NOVA_ANT` (`EEG_flipcup`, `Eyes open eyes closed`, `Behavioral Data`, `Video`) holds EXAMPLE recordings from the same hardware, for validating the signal code offline only: the EO-EC 33x occipital-alpha check, and whether the load metric separates flip-cup outcomes. Copy what is needed into `data/` (gitignored).
- So "proper data to test with" arrives in two steps: first the offline validation against those examples once `features.py` is real, then live closed-loop runs (synthetic board anywhere, the real amplifier on Windows).
- Until then, never judge visuals or adaptive behaviour by the flat values; verify wiring with injected values instead (`python/smoke_test.py`, four-quadrant section).
- `decide.LOAD_BAND`'s 0.8 floor exists only so the placeholder can converge. Retighten to ~1.3-3.0 once real data lands, or the disengagement flag can never fire.

## Key resources

- Challenge handout: `~/Downloads/Challenge Handout (2).pdf` (requirements, judging, deliverables).
- Hardware: eego amplifier EE-22x user manual `~/Downloads/UDO-SM-0120_ENrev11 eego amplifier EE-22x User Manual 2025-07-01_02 (1).pdf`; waveguard CA-208 cap datasheet `~/Downloads/UDO-SM-0215rev09 CA-208 Datasheet 2020-12-14 (1).pdf`.
- Example recordings and stimulus material (offline validation only, never the live loop): `~/NOVA_ANT`.
- Load-index literature (the science behind `features.load_index`):
  - Dan and Reiner 2017, Int J Psychophysiol (PMID 27592084): defines the cognitive load index as frontal theta (Fz) power over parietal alpha (Pz) power - the ratio Kaira uses.
  - Borghini et al. 2015, IEEE EMBC (PMID 26737704): the same frontal-theta / parietal-alpha ratio as a mental workload index, validated on helicopter pilots.
  - Juras, Hromatko and Vranic 2025, Front Aging Neurosci (PMID 40182761): parietal alpha and theta power predict cognitive training gains in middle-aged adults - supports the aging/decline framing.
- Worked EEG notebooks: github.com/Ildaron/EEG-Signal-Processing-with-Python (band-pass, artefact analysis, real-time processing examples the team can crib from by hand).

## Conventions

- API on `127.0.0.1:8300` (8000 collides with Django dev servers). UI is Vite on 5173; CORS is pinned to that port.
- Restart the API after editing `python/` (it does not run with --reload).
- Keep `python/smoke_test.py` green: `.venv/bin/python python/smoke_test.py`.
- The UI follows the UQwest staff house style (`~/Side-Projects/UEP/frontend`): plain CSS with tokens, DM Sans + Source Serif 4, hairline cards at 12px radius, `kr-`/`sn-`/`rp-` class prefixes, axios behind `src/api.js`, hand-rolled chart legends, why-comments everywhere.
- Live load is polled at 4 Hz (matches the real pipeline's 250 ms window step).
- `http://localhost:5173/?demo=report` deep-links to the report screen with fabricated PT-SAMPLE data (`ui/src/sampleReport.js`) for UI work without running a session.
- No em dashes anywhere, including UI copy and comments; use a plain dash.
- Work happens on branches `lucas` and `aarnav`; changes to the fixed Python interface need both.
