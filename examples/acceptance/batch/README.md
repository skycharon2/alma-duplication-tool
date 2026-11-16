# Offline multi-source browser acceptance

From the repository root, with the project environment installed:

```sh
python scripts/preview_multi_source.py --port 5057
```

Open `http://127.0.0.1:5057/acceptance/batch`. Choose another port if it is busy.
Stop the server with Ctrl+C; temporary reports are removed on shutdown.

The script creates two independent targets with LINE and CONTINUUM reports.
`targets.csv` deliberately repeats the recorded cone at RA 201.365 degrees,
Dec -43.019 degrees so both targets match the Archive replay. The names and
redshifts are synthetic acceptance inputs, not independently verified source
metadata. Shared frequencies are SKY frequencies. Different redshifts therefore
do not demonstrate REST conversion; automated batch parity tests cover that.

Archive input is `examples/confirmed_line/archive/manifest.json`; Queue input is
`examples/acceptance/queue/dual-source-line.csv`. Live Archive, automatic Queue
updates, managed Queue and external array evidence are explicitly disabled even
when enabled in the shell environment. Both sources should display Retrieved.
An unresolved LINE result remains unresolved; successful retrieval does not
establish a scientific match.

## Browser checks

1. Open target A's LINE visualization from the overview.
2. Click Next target. Confirm target B, LINE and visualization remain selected.
3. Click Continuum. Confirm target B and visualization remain selected.
4. Click Text report. Confirm target B and Continuum remain selected.
5. Click Previous target. Confirm target A, Continuum and text mode.
6. Click Back to batch overview. Confirm the URL ends in `#source-line-2` and
   the target A row group is highlighted.
7. Repeat at a narrow viewport and inspect the navigation for wrapping.

This entry exercises saved-report navigation. It seeds reports through the real
batch orchestrator at startup, bypassing upload and form interaction. Use
`/proposed/batch` with this CSV for separate form checks. The existing five-target
CSV/TXT parser fixtures cover the proposal's wider sky positions; they do not
match this single-cone Archive replay.

The local preview deliberately gives every browser visiting `/acceptance/batch`
access to the same synthetic batch. This helper route exists only in this script,
not the production application. It binds to loopback, uses temporary storage,
and is not a deployment entry point or a live scientific acceptance run.

## Recorded check: 2026-11-16

Checks 1–6 passed in a real browser on port 5058. Target, purpose, view and return
anchor were preserved. The previously interrupted next-target click is now
verified. Desktop and 390px layout screenshots were inspected on 2026-11-13.
The initial page logged only a missing favicon; no report-page console error
was observed. Automated preview coverage additionally prohibits external HTTP
access, enables live-source environment flags to test their override, verifies
all four reports contain retrieved sources and comparison contexts, and checks
that another browser cannot read the batch before visiting the preview entry.
