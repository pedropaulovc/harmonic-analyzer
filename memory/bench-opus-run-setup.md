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

**Run-until-quota + periodic push** (scratchpad scripts, this session): a driver re-invokes the resumable `run.py` per task (T1 n=1 → T3 n=3 → T2, `--budget-tokens 999000000` so only quota stops it) and halts when a pass makes zero new successes while cells remain (quota-exhausted signal). A pusher archives opus-only rows → `comparisons/bench/results/opus.results.jsonl` (+summary+report) and pushes to branch `feat/bench-opus-high` (PR #253) every ~10 min. run.py `done_keys` only counts `response!=null` as done, so rate-limit errors auto-retry on the next pass.

See [[parallel-sw-instances-investigation]] for the COM-spine seat constraint (irrelevant here — bench needs no SolidWorks).
