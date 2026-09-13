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

## Verified against real hardware (2026-09-12)

- The venue amp is an eego 24 (EE-511) with the NA-246 net: 24 channels @ 512 Hz, verified from its own .cnt recordings. All six formula channels (F3 Fz F4 P3 Pz P4) present; NO EOG channel. The old 64-ch facts (CA-208, EOG at ch 32) apply only to the NOVA_ANT example recordings.
- Validation both ran and passed: `tools/validate_eoec.py` shows ~52x eyes-closed occipital alpha at 10.0 Hz THROUGH the full pipeline (the gate for any preprocess change). James's 3-minute baseline: 96% trusted, wobble sd 0.76, resting task-loads 93% mid under z bands.
- `~/NOVA_ANT` recordings stay offline-validation only; Kaira live sessions run on the LSL stream.

## Effort thresholds are z-scores (merged to main 2026-09-12)

- decide's bands read `trial.z` at +-1.0: load in units of THIS patient's own resting wobble (`baseline_sd`), measured fresh each baseline. Fixed +-0.30 misread 38% of resting tasks on the venue amp; z reads 0% (task loads average ~5 windows, so +-1.0 z sits near two standard errors).
- The display band is personal: exp(z * sd), carried on every live-load response; the report band field likewise.
- `BASELINE_SD_FLOOR` (0.05) guards a patient who sat unnaturally still.
- Live baselines average everything collected (team call - one simple reference; the settle-check already guards the finish). FILE baselines (uploads + the bundled default) trim to the settled last 90 s, because no settle-check ran while they recorded and James's file drifted +0.7 log units early.

## Key resources

- Challenge handout: `~/Downloads/Challenge Handout (2).pdf` (requirements, judging, deliverables).
- Hardware: eego amplifier EE-22x user manual `~/Downloads/UDO-SM-0120_ENrev11 eego amplifier EE-22x User Manual 2025-07-01_02 (1).pdf`; waveguard CA-208 cap datasheet `~/Downloads/UDO-SM-0215rev09 CA-208 Datasheet 2020-12-14 (1).pdf`.
- Example recordings and stimulus material (offline validation only, never the live loop): `~/NOVA_ANT`.
- Load-index literature (the science behind `features.cognitive_load`):
  - Dan and Reiner 2017, Int J Psychophysiol (PMID 27592084): defines the cognitive load index as frontal theta (Fz) power over parietal alpha (Pz) power - the ratio Kaira uses.
  - Borghini et al. 2015, IEEE EMBC (PMID 26737704): the same frontal-theta / parietal-alpha ratio as a mental workload index, validated on helicopter pilots.
  - Juras, Hromatko and Vranic 2025, Front Aging Neurosci (PMID 40182761): parietal alpha and theta power predict cognitive training gains in middle-aged adults - supports the aging/decline framing.
- Worked EEG notebooks: github.com/Ildaron/EEG-Signal-Processing-with-Python (band-pass, artefact analysis, real-time processing examples the team can crib from by hand).

## Brand system (team, 2026-09-05)

- KAIRA - "Where the brain guides what's next." Essence: Sense -> Understand -> Adapt -> Progress. Personality: intelligent, human, calm, adaptive, forward.
- Colors: Deep Slate `#263238` (ink AND primary actions), Neural Blue `#489fce` (anything showing the live measurement), Adaptive Green `#87cc9a` (the parietal-alpha half of the live spectrum), Cool Mist `#EAF3F5` (soft surfaces), Warm Sand `#D8A66A` (flags only - the "sparingly" colour). Mostly white + slate; blue/green are the accents.
- Status colors (good/warn/bad) stay un-themed - a result must always read the same.
- Typography: DM Sans for all text (no serif anywhere). The KAIRA wordmark is drawn SVG paths (`ui/src/components/Wordmark.jsx`), recreated from the brand slide: thin geometric caps, wide tracking, crossbar-less A's, always Deep Slate. Slides pair it with Inter, but the UI loads no second font.
- Graphic language: circle + pulse + direction (closed loop, neural signal, adaptation). Diagrams show signals converging -> insight -> adaptation.
- UI mapping: `--accent` = slate (buttons, focus, decisions), `--signal` = Neural Blue (live pulse, effort meter, baseline progress, chart bars, spectrum frontal curve); the load sparkline is slate - the formula OUTPUT pairs with the slate number, blue/green stay the raw bands, chart level line = slate pen, flagged bars = Warm Sand.

## Build day (2026-09-12) - standing prep

- Thresholds/ratio are ON STANDBY for a switch: Saturday's live testing may change them, Lucas will prompt the change and it must land in minutes. Every knob is a single named constant: `decide.LOW_LOAD/HIGH_LOAD` (band), `START_LEVEL`, `MAX_TASKS`, `CONVERGENCE_RUN`; `session.BASELINE_*`, `SAMPLE_SECONDS`; the formula itself (bands/channels) lives in `features.BANDS/FRONTAL/PARIETAL` (Lucas's file - he edits or dictates). After ANY python edit: restart the API, rerun both suites.
- Friday: Aarnav pushes real `stream.py`/`preprocess.py`. Pressure-test against the checklist in his integration message: exact channel names (session now asserts at import), rows never deleted in clean(), high-pass before handoff, trusted flag, `get_window(2.0)` returns the LATEST 2 s non-blocking (ring buffer >= 1024 samples at 512 Hz; must handle the first seconds before the buffer fills). Then `python/smoke_test.py` with SYNTHETIC off-path, and a live baseline watch.
- Friday: Alice delivers the real Visuospatial questions + grid images to splice into individual stimuli, with level AND expected answer per question. Pipeline: crop -> `ui/public/tasks/` -> task bank entries get `image` refs.
- Cleaning is ASR (2026-09-12, team decision): calibrate() fits meegkit's Artifact Subspace Reconstruction on ~20 s of the resting baseline; clean() = high-pass -> ASR repair -> average reference -> trust gate. Post-ASR the gate is deliberately loose (300 uV on the formula channels - rely on the repair, discard only the unsalvageable); without ASR (short rehearsal baselines fall back) the strict 150 applies. EOG regression is deleted - the EE-511 cap has no EOG and ASR eats blinks anyway. Gate for any preprocess change: tools/validate_eoec.py must keep the eyes-closed alpha ratio (currently 51.8x, peak 10.0 Hz). Dependency: pip install meegkit (asrpy is broken on numpy 2).
- Patient display joins by QR (2026-09-12): the start screen shows a QR of this machine's LAN IP + `?role=patient` (server reports its IP via `/net/info`; qrcode renders locally, no internet needed). The patient screen auto-attaches to the newest running session, its polling doubles as a heartbeat, and `/session/start` 409s until one is alive. The stimulus shows only between the clinician's Start press and their verdict (server-side `task_running`).
- Signal source is a UI toggle plus a picker: Test (any LSL stream, else synthetic - never blocks) vs Live, and "Scan for streams" lists every broadcast for explicit selection. `LIVE_PREFIX` is "" (Aarnav, venue call): live auto-connect takes any stream and the human verifies by name in the dropdown/status line, so KILL the dummy during the real demo. The Demo pill clears for any connected stream now.
- LSL receiver is hardened against the REAL eego shape (2026-09-12, reproduced with `dummylsl_problem.py`): ANT streams carry non-EEG rows (TRIG/counter/EDA per their docs) - the receiver keeps only electrode-like rows by label/type metadata, tolerates more channels than labels, refuses rate-less streams, and the pull thread survives bad chunks. The venue freeze ("will start when the task does" during a task) was empty/degenerate windows -> filter ValueError -> 400 on every poll, swallowed by the UI; windows under 0.5 s now read untrusted instead of crashing, and 400/409s print their cause to the API console.
- Never lose a recording: every received LSL chunk is teed to `data/recordings/<stream>-<ts>-<tag>.f32` + json header (numpy-replayable), rotated per session (tag = patient ref, idle between). `KairaMarkers` broadcasts session/task/answer events as an LSL stream - tick it plus the amp in LabRecorder and the .xdf carries signal and question timing on one clock.
- Baselines three ways: live (adaptive protocol), "Use James's baseline" (bundled `baselines/H_James_...cnt`, the demo-day default), or drop/upload a `.cnt`/`.xdf`/`.npz` on the baseline screen. "Use previous baseline" reuses the last finished one in this server. Fallback demo pairing: dummy signal + Skip baseline, never dummy + James (the dummy reads below a real brain's rest and the veto cells never fire).
- Task picker never serves the same object twice in a row (level changes reuse objects, ids share the trailing item number). START_LEVEL is 3 (team call 2026-09-12).

- API on `127.0.0.1:8300` (8000 collides with Django dev servers). UI is Vite on 5173; CORS is pinned to that port.
- Restart the API after editing `python/` (it does not run with --reload).
- Keep both suites green: `.venv/bin/python python/smoke_test.py` and `.venv/bin/python tests/test_decide.py`.
- The UI follows the UQwest staff house STRUCTURE (`~/Side-Projects/UEP/frontend`): plain CSS with tokens, hairline cards at 12px radius, `kr-`/`sn-`/`rp-` class prefixes, axios behind `src/api.js`, hand-rolled chart legends, why-comments everywhere. Colors and type come from the Kaira brand system above, not from UQwest.
- Live load is polled at 4 Hz (matches the real pipeline's 250 ms window step); the run screen's 1-5 effort meter and every clinician sentence (`reason_text`) are computed server-side - the UI computes nothing.
- The live periodogram (frontal theta blue, parietal alpha green, 2-20 Hz) rides the live-load response; `session._spectrum` mirrors features.py's Welch settings without touching the hand-written file, and the decision never reads it - display only. The signal column is deliberately not a card.
- The resting baseline is adaptive (team protocol, 2026-09-02): record at least 90 s, then stop as soon as the last two 30 s mean-CLI windows agree within 10% (a log distance, `session.BASELINE_TOLERANCE`), capped at 3 minutes. Never settles -> plain 3-minute average plus a `baseline_stable=false` flag (UI tells the clinician to check electrodes and consider redoing). Rehearse with `KAIRA_BASELINE_SECONDS=15`; overrides at or below 90 s skip the settling logic. Never shorten the constants themselves.
- `http://localhost:5173/?demo=report` deep-links to the report screen with fabricated PT-SAMPLE data (`ui/src/sampleReport.js`) for UI work without running a session.
- No em dashes anywhere, including UI copy and comments; use a plain dash.
- Everyone pushes main; pull before working (Aarnav lands directly on main too). Venue machine catch-up: `git pull` + `pip install -r python/requirements.txt`.
