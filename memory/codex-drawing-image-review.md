---
name: codex-drawing-image-review
description: Blind machinist review of drawing PNGs is now a repo script (cad/scripts/machinist_review.py) with a policy-calibrated prompt; the old gap-hunting prompt produced the over-engineered fleet
metadata: 
  node_type: memory
  type: feedback
  originSessionId: dd57a3c2-7d38-4878-8a31-99f6cc6dadb1
  modified: 2026-09-02T16:57:27.210Z
---

Pedro's flow for validating manufacturing drawings: render the sheet PNG, then have
Codex (gpt-5.6-sol, high) review the IMAGE with zero repo context as a senior
machinist. 2026-09-02: the flow is now `uv run cad/scripts/machinist_review.py
<name>... | --all --jobs N`, prompts in `cad/scripts/prompts/`, reports under
`cad/out/reports/machinist-review/` (index.md + per-sheet json/md/events).

**Why the prompt was recalibrated:** the earlier ad-hoc prompts ("is this print
manufacturable/certifiable as a standalone drawing? list missing tolerances,
datums, finish, threads...") rewarded the reviewer for GAPS, so two months of
rounds grew ~125 FCFs, 100+ datums, Ra on hand-crank bores and 5-12-line notes —
exactly what Pedro flagged as "way too overengineered". The new prompt (distilled
from Harvey *Machine Shop Trade Secrets* ch. 9 and Lipton *Sink or Swim* ch. 2-3)
reads the title block as the general spec, scores **over-specification as a
defect**, and encodes hidden-lines-on / one origin / drill-vs-ream / few notes.
Standard: `cad/docs/drawing-simplicity-policy.md`. Baseline check: the old
crank-arm sheet came back FIX with 11 over-spec findings naming every datum,
frame and boxed basic — the calibration works.

**Mechanics that matter:**
- Isolation is by COPY: PNG + schema copied into a mktemp dir, `-C` there,
  `--ignore-user-config --ignore-rules --skip-git-repo-check --ephemeral
  --sandbox read-only`, prompt on stdin. `--ignore-user-config` drops the config
  model, so `-m`/`-c model_reasoning_effort` are passed explicitly.
- `--json` event stream is scanned for tool/command events; any hit marks the
  review `blind: false` and fails it.
- `--output-schema` strict JSON: `{verdict SHIP|FIX, summary, blockers[],
  over_specification[], clarity[], minor[]}`; pass = SHIP with the three gating
  lists empty. ~200-330 s per sheet at high effort.
- Run it from the REPO ROOT with an absolute script path — the Bash cwd drifts
  after `cd cad/scripts` and `uv run cad/scripts/...` then fails to spawn.

**How to apply:** rebuild the sheet, run the script, fix blockers and every
over-spec/clarity item that the policy agrees with; a clarity finding that asks
for a package item the policy forbids is declined, not fixed. Judge rounds by
finding quality ([[codex-review-diminishing-returns]]).
