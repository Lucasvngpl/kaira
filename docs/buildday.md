# Build day: path to a live demo

Build day Sat 12 Sep 2026, judging Sun 13 Sep.
The visual version of this page: https://claude.ai/code/artifact/eedec9ca-d173-48dd-af57-8c8465a78430

Seven steps, each with a gate.
Do not start the next step until the gate before it passes, because a failure carried forward costs more than the hour spent proving the step.

**Decided: no synthetic demo.**
The amplifier runs on stage or nothing does.
That makes step 2 the whole day's priority, and everything after it downstream of one 60-second test.

## Phase A: no hardware needed

### 0. Prep on Aarnav's laptop

On normal internet, while it still has internet.
Clone, venv, `npm install`, API on 8300.
Windows is not optional: BrainFlow's ANT Neuro boards only run there.

```
.venv/bin/python python/smoke_test.py
.venv/bin/python tests/test_decide.py
```

**Done when:** both suites pass on his machine, not just on Lucas's.

### 1. Merge, then pressure-test the contract

Pull Aarnav's `stream.py` and `preprocess.py`, resolve conflicts, then walk his checklist against the fixed interface:

- Exact channel names, which `session.py` asserts at import.
- `get_window(2.0)` returns the *latest* 2 s, non-blocking.
- The first seconds behave, before the ring buffer has filled.
- `clean()` never deletes rows.
- High-pass applied before handoff, and the trusted flag set.

Synthetic board here on purpose.
A merge bug and a hardware bug arriving together is how you lose an afternoon to a question that has two answers.

**Done when:** `smoke_test.py` passes on synthetic, including the injected-value quadrant section.

## Phase B: live signal chain

### 2. Amplifier up: the go/no-go

Cap on a real head, `KAIRA_SYNTHETIC=0`.
One minute of rest with eyes open, one with eyes closed.
Occipital alpha should leap when the eyes close, and that single contrast proves the cap, the channel order and the Welch maths in one shot.

```
python tools/record.py --seconds 60 --out rest_eo.npz --note "rest, eyes open"
python tools/record.py --seconds 60 --out rest_ec.npz --note "rest, eyes closed"
python tools/inspect_capture.py rest_eo.npz rest_ec.npz
```

**Go / no-go:** eyes-closed occipital alpha is roughly an order of magnitude higher.
If it is not, stop and fix electrodes or channel order.
Nothing downstream of this means anything until it passes, and no amount of code will fix a cap.

**The moment it streams, freeze that machine.**
Pause Windows Update, change no drivers, install nothing, note which USB port worked and keep using that port.

### 3. Labeled captures for tuning

Same subject, three captures: rest, an easy item, a hard item.
Write which is which into `--note`.
Thresholds are a contrast between conditions, so an unlabeled blob of signal cannot tell you where to put them.

```
python tools/record.py --seconds 60 --out task_easy.npz --note "visuospatial level 2, easy"
python tools/record.py --seconds 60 --out task_hard.npz --note "visuospatial level 4, hard"
python tools/inspect_capture.py rest_eo.npz task_easy.npz task_hard.npz
```

**Done when:** the `.npz` files and the `inspect_capture.py` output are shared, and `LOW_LOAD` / `HIGH_LOAD` are chosen.
One sweep, pick, move on.

If the numbers refuse to separate, ship the current +-0.30 bands.
They came from the 31 Aug sweep and they are defensible on stage.

### 4. Live closed loop, laptop screen only

One real session end to end: the baseline settles, tasks adapt, the report renders.
Restart the API and rerun both suites after every Python edit, since it does not reload itself.

**Done when:** a full session completes with nobody nudging it.

## Phase C: presentation

### 5. Hotspot, then the iPad

iPhone hotspot, laptop and iPad both on it.
The iPad's requests are addressed to the laptop on that little network, so they never go out over cellular and the venue's refusal to let devices see each other stops mattering.

```
Laptop:  npm run dev -- --host   # only Vite listens on the network
         ipconfig                -> the Wi-Fi adapter's IPv4 (iPhone hands out 172.20.10.2-.4)
iPad:    http://172.20.10.x:5173/?patient=<session id>
```

The API stays on 127.0.0.1 and needs no flags.
Vite relays `/api` to it from inside the laptop, so there is no address to configure and no second thing exposed to the room.
Windows will ask once to let Node through the firewall: say yes.

Switch to the hotspot only now.
Joining it takes that laptop off the internet, and every step above needed git and npm.

**Done when:** the iPad shows the right stimulus and follows every phase change for a whole session, with auto-lock off and Guided Access on.

### 6. Full rehearsal, then the runbook

Real cap, iPad in the patient's hands, someone on the clinician screen, timed end to end.
Then write down who clicks what, in which order, and what they do when it misbehaves.

**Done when:** two clean run-throughs and a written runbook the team has read.

## Standing risks, and what you do instead

| Risk | Instead |
| --- | --- |
| Bad cap fit on the patient | A teammate with known-good impedance takes the chair. |
| Noisy channels | The load index needs Fz and Pz. Know which electrodes you cannot afford to lose. |
| Tuning will not converge | Ship +-0.30 and say where it came from. |
| iPad will not connect | Second window on the laptop, external monitor facing the patient. Presentation, never the loop. |
| 90 seconds of resting baseline, on stage, unassigned | Live means a real baseline: at least 90 s of a judge watching a progress bar. Somebody narrates the science against a real clock, rehearsed. Decide who today. |
