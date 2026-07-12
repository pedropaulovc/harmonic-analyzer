---
name: bench-opus-run-setup
description: How to run comparisons/bench for the Opus subject — source geometry from a release, regenerate renders, run at --effort high, push partials
metadata:
  type: project
---

Running `comparisons/bench` (pose-presentation benchmark, docs/pose-presentation-benchmark.md) for the **Opus** subject on a Blender-only seat (no SolidWorks / empty `cad/out`).

**Geometry from a release (no local build needed).** `render_offline.py` consumes `cad/out/{sldprt,sldasm,boxes,stl}`. Populate them from the latest release zip:
- `gh release download <tag> --pattern 'harmonic-analyzer-<tag>.zip'`
- Extract `solidworks/*.SLDPRT`→`cad/out/sldprt/`, `solidworks/*.SLDASM`→`cad/out/sldasm/`, `boxes/*`→`cad/out/boxes/`, `stl/*`→`cad/out/stl/` (zip lays them flat; render_offline wants the split dirs).
- **`touch` all of `cad/out/stl` + `cad/out/boxes` newer than the SLDPRT/SLDASM** — `_stale()` fails if `STL.mtime < SLDPRT.mtime` and the zip stores older stl mtimes.
- v0.19.0 geometry reproduces `cases.jsonl` **byte-identical** to the committed ground truth (verified) → Opus numbers are comparable to the committed codex/codex-sol columns.

**Regenerate the 270 stimuli** (out/ is gitignored, cleaned after codex): `uv run comparisons/bench/gen_cases.py` (6 first-pass pairs × 45). Blender loading the ~131-STL assembly takes several minutes before the first render lands.

**"opus high" = `--effort high`.** `run_opus` in run.py hard-codes `claude -p --model opus --effort high --output-format json --permission-mode bypassPermissions`. Smoke confirms `model_id == claude-opus-4-8`. (`claude --effort` values: low/medium/high/xhigh/max.)

**Run-until-quota + periodic push** (scratchpad scripts, recreated each session — scratchpad is per-session, so they don't persist): `driver.py` re-invokes the resumable `run.py` per task (T1 n=1 → T3 n=3 → T2, `--budget-tokens 999000000` so only quota stops it) in bounded `--limit 160` passes at `--concurrency 16`, and after EVERY pass regenerates `report.py --model opus` and pushes the archive (`comparisons/bench/results/opus.{results,summary,report}` — copies of `out/{results.jsonl,summary.json,report.md}`) — so ~8 min push cadence. Halts after 2 consecutive zero-progress passes (quota-exhausted; a real quota wall returns fast errors). run.py `done_keys` counts only `response!=null` as done, so rate-limit/timeout errors auto-retry next pass.

**Quota-reset timer** (`supervisor.py`): sleeps until 01:30 America/Los_Angeles (= 08:30 UTC in PDT/summer; fixed offset, no tz db) and, if cells remain and no driver is progressing (results.jsonl growth probe), launches a fresh resumable driver (→ `scratchpad/driver.next.log`); loops daily until done. Guard prevents double-running alongside a still-live driver.

**Git/PR:** PR #253 MERGED into main (first 1570 rows there + #254 COM-seat-lock refactor). Continued run went on re-pushed branch `feat/bench-opus-high` → **PR #257, MERGED 2026-07-12** at a PARTIAL stopping point: **T1 1782/1782 (complete), T3 770/1584 (~49%), T2 0/396 (not started)** — quota exhausted twice (once overnight, once at 01:55 PT after the 01:30 auto-restart). To finish T3+T2 later, re-run the driver on a fresh branch (out/ data is gitignored/local; resume works off the committed archive too). T1 total = 1782 (6 pairs × 27 subgrid tags × 11 arms × n=1); T3 = 1584 (n=3); T2 = 396. Merge was conflict-free — main advanced 81 CAD commits but none touched `comparisons/bench/`.

**T3 cell_key collision fix (committed in #257, run.py `t3_key`).** The T3 cell_key keyed on delta CLASS (az/el/roll/ty/tx), but `T3_PAIRS` has 3 `az` + 2 `ty` graded-difficulty pairs sharing a class → 1584 cells collapsed to 990 unique keys. A single big pass (how codex ran) writes all 1584 rows regardless, but the resumable `--limit` driver rebuilds `todo` each pass excluding done keys, so it dropped the duplicate-class pairs → only ~990 opus rows with a DIFFERENT difficulty mix than codex (not comparable). Fixed by keying on the delta-PAIR tag (`c1.split('+',1)[1]`, e.g. `az+1`). cell_key is resume-only (never scored), so codex's recorded rows are unaffected. driver.py/supervisor.py call `R.t3_key`. If T3 ever looks like ~990 not 1584, this regressed.

See [[parallel-sw-instances-investigation]] for the COM-spine seat constraint (irrelevant here — bench needs no SolidWorks).
