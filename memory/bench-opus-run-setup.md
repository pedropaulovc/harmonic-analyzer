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

**Opus-5 rerun (2026-07-24, PR #404) — what a NEW subject generation costs.**

- **A restricted tool set is mandatory, and `--allowed-tools` is NOT it.** Left
  unrestricted under `--permission-mode bypassPermissions`, claude-opus-5
  answers ~6 cells in 7 by shelling out to numpy/PIL (it will `uv venv` and
  `pip install` to get them) and computing the misregistration numerically —
  10+ min/cell vs ~30 s for a visual read, and every presentation arm collapses
  to the same pixel math, which scores a different question than the benchmark
  asks. `--allowed-tools=Read` does **nothing** here (it is a no-prompt
  allow-list, so Bash still ran — verified in the cell transcripts). The flag
  that works is **`--tools=Read --strict-mcp-config`**; the subject then reports
  Read as its only tool. Both flags are **variadic**, so pass them in `=` form —
  a separate `--tools Read` swallows the trailing prompt arg (same trap as
  codex's `-i`). `opus-5-tools` keeps the unrestricted path as a 900 s
  side-probe so the gap is measured, not assumed.
- **Read-only opus-5 cells run 20–152 s** (p50 ~50 s at concurrency 16), ~2× the
  archived opus-4.8 p50 of 25 s, so its timeout is **420 s** not 240 — the
  archived timeout would truncate the slow tail and bias the column.
- **THE CELL'S cwd WAS THE ANSWER KEY (and every archived column carries it).**
  The sandbox was named for the cell key, so a T1 cell ran in a directory
  ending `+az+3` — and Claude Code puts the working directory in prompt
  context. A probe cell quoted its own path back, read "az+3" out of it, and
  volunteered that the directory looked like an eval harness. Name sandboxes by
  the **opaque id** the stimulus files already carry (T3 keys name the
  delta-pair, T2 keys the starting perturbation — all three leaked), and keep
  the root OUT of the repo (`$TMPDIR/pose-bench-sandbox`) so a relative walk
  can't reach `cases.jsonl`. The archived `codex`/`opus` columns were collected
  before both fixes, so `run.py` refuses those subject ids without
  `--allow-archived-subject` rather than mixing harnesses under one cell key.
- **Two contamination checks worth running on any new subject**, both cheap and
  both caught real defects here: ask a cell what instruction files it sees
  (should answer NONE), and ask it to quote its cwd (should be opaque). Scan
  the cell transcripts under `~/.claude/projects/*<sandbox>*` for tool use to
  confirm what the subject actually did.
- **Comparability pin.** Regenerating stimuli on current `main` is NOT
  comparable: `comparisons/manifest.json`, `tools/composite.py` and
  `render_offline.py` all drifted (camera-pose refreshes). Pin geometry to the
  **v0.19.0** release zip and `comparisons/{manifest.json,tools}` +
  `bench/render_server.py` to **c8efcf1e** (last opus-4.8 bench commit), plus
  the `references` submodule to **03d58e23**. That reproduces the committed
  `cases.jsonl` to ≤3 ULP (FP noise on one pair from a different Python/Blender
  build), so keep the committed file and let the pins carry the meaning.
- The pinned `render_offline.py` hardcodes a **Windows** Blender 5.1 path with
  no env override, so a Linux seat needs a local-only
  `HARMONIC_BLENDER`/`shutil.which` patch (`main` later formalised this as
  "use any available Blender"). Unpinnable caveat: the archived columns'
  renderer version is gone from the seat (now 5.2.0 LTS) and the archived
  stimuli were gitignored + cleaned, so it cannot be pixel-verified.
- `gh release download` / `gh pr create` / `gh pr ready` all go through
  **GraphQL**, which rate-limits separately from core REST. With GraphQL at 0,
  fall back to REST: fetch the asset id from
  `repos/:o/:r/releases/tags/<tag>` then `gh api -H "Accept:
  application/octet-stream" .../releases/assets/<id>`, and POST
  `repos/:o/:r/pulls` to open the PR.
- `git checkout <sha> -- <paths>` **stages** what it restores, so a later
  `git add <other file>` + commit silently swallows the pins. Unstage them
  (`git restore --staged`) right after pinning.

See [[parallel-sw-instances-investigation]] for the COM-spine seat constraint (irrelevant here — bench needs no SolidWorks).
