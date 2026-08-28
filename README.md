# Kaira

Adaptive cognitive assessment driven by real-time EEG effort.
A clinician administers tasks; the system measures cognitive load from a 64-channel EEG and adapts the next task's difficulty to the patient, ending at the level they can hold with normal effort.
Built for the NOVA Biotech McGill Buildathon 2026 ("NeuroLoop", sponsored by ANT Neuro).

The scaffold (orchestrator, API, UI, task bank) is complete and runs end-to-end on synthetic data.
The four signal-chain modules are hand-written by the team and currently contain skeletons only; see "Scope" below.

## Layout

```
kaira/
├── python/
│   ├── stream.py        SKELETON - BrainFlow acquisition          [Aarnav]
│   ├── preprocess.py    SKELETON - filtering, artifact rejection  [Aarnav]
│   ├── features.py      SKELETON - Welch, band power, load index  [Lucas]
│   ├── decide.py        SKELETON - adaptive staircase             [Lucas]
│   ├── session.py       orchestrator: one session's state and sequencing
│   ├── tasks.py         task bank (Memory populated, levels 1-5)
│   ├── smoke_test.py    headless check of the whole loop
│   └── requirements.txt
├── api/
│   └── main.py          FastAPI wrapper around session.py (port 8300)
├── ui/                  React + Vite clinician UI (port 5173)
└── data/                gitignored; put the ANT Neuro .cnt files here
```

## Setup

Python 3.11+ and Node 18+.

```bash
python3 -m venv .venv
.venv/bin/pip install -r python/requirements.txt
cd ui && npm install
```

## Run

API (from the repo root; synthetic signal is the default):

```bash
.venv/bin/python api/main.py
```

UI (second terminal):

```bash
cd ui && npm run dev
```

Open http://localhost:5173, enter a patient reference, and run a session: baseline records for 15 s, then tasks adapt until convergence (three consecutive correct at one level, inside the effort band) or the 12-task cap.
The port is 8300 rather than 8000 because Django dev servers tend to occupy 8000.

Quick health check without the UI:

```bash
curl http://127.0.0.1:8300/
.venv/bin/python python/smoke_test.py
```

## API surface

```
POST /session/start                {patient_ref, domain} -> {session_id, baseline_seconds}
GET  /session/{id}/baseline-status -> {done, progress}
GET  /session/{id}/next-task       -> {task_id, level, prompt, answer, n, total_max}
POST /session/{id}/answer          {task_id, result, elapsed_seconds} -> {action, next_level, load, converged, reason}
GET  /session/{id}/report          -> report object (see HANDOFF.md section 7)
GET  /session/{id}/live-load       -> {load, trusted}   polled at 4 Hz by the UI
```

Sessions live in process memory; restarting the API forgets them.

## Synthetic vs real hardware

Everything runs against fake data by default so no amplifier is needed.
The switch is one constant: `SYNTHETIC` in `python/stream.py`, set by the API at startup.

```bash
.venv/bin/python api/main.py                  # synthetic (default)
.venv/bin/python api/main.py --no-synthetic   # real eego EE-225
```

Real hardware notes: BrainFlow's ANT Neuro boards are Windows-only, board id 36 (`ANT_NEURO_EE_225_BOARD`), 512 Hz, reference CPz, ground AFz, EOG on channel 32.
The eego is DC-coupled (raw values around +4800 uV), M1/M2 are dead in the provided dataset, and `.cnt` files need `mne.io.read_raw_ant` (package `antio`), not `read_raw_cnt`.

## Scope: what is hand-written

Buildathon AI policy: the team must be able to defend every line of the graded algorithm, so the four signal-chain files are skeletons with docstrings and TODOs, written by hand by the team.
Their placeholder bodies return obviously fake values (`return 0.5`) that keep the demo running.

The interface between the halves is fixed in each skeleton's docstring (and HANDOFF.md section 5).
Changing it requires agreement on both branches.

`python/smoke_test.py` asserts the plumbing, never signal values.
Keep it green while filling in the skeletons.

## Dataset

ANT Neuro supplied recordings from the exact competition hardware (25-29 MB each, so `data/` is gitignored).
Get them from the team drive and drop them in `data/`.
`*_EO-EC.cnt` is the validation baseline: occipital alpha must come out ~33x higher with eyes closed, peaking at 10.2 Hz.
`*_session-0*.cnt` are the labelled flip-cup trials for testing whether the load metric separates outcomes.

## Branches

Work happens on `lucas` and `aarnav`, off `main`.
Changes to the fixed interface need both.
