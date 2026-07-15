---
name: drawing-fanout-orchestration
description: Fanning out Fable drawing agents — they yield between steps; verify progress on-disk, not by idle pings; PR each gate-complete slice; watch the Fable weekly quota
metadata:
  type: feedback
---

Orchestrating the manufacturing-drawing fan-out (one Fable subagent per part, each
in its own git worktree, all serialized on the single SolidWorks COM seat).

**Fable drawing agents END THEIR TURN between steps** (after building the part, or
while the seat is busy) and emit an `idle_notification ... "available"` — they do
NOT autonomously run through to the commit. An idle ping is NOT "done" and often
NOT "blocked" either; it just means the turn ended and the agent is waiting for a
kick.
**Why:** left alone they stall the fan-out until re-nudged, wasting the lead's cycles.
**How to apply:**
- Bake "run the whole build→iterate→review→commit sequence to completion WITHIN
  your turns; do not go idle between steps; only stop when committed or hard-blocked"
  into the agent prompt from the start (now in `cad/scripts/drawing_recipe.md`'s
  template).
- On an idle ping, do NOT trust it — check the worktree ON DISK: `git log -1`
  (committed?), `cad/out/png/<stem>_drawing.png` (drawing built?),
  `cad/out/reports/codex_machinist_review.txt` (reviewed?). Nudge only if genuinely
  stalled with work unfinished; a part-built-but-drawing-unbuilt state is the common
  stall.
- Gate-complete = commit subject "…curated manufacturing drawing slice" AND PNG AND
  codex review file all present. Run a persistent [[com-seat-lock]] Monitor per wave
  keyed on those three, then open the PR (`gh pr create --draft` → `gh pr ready`) the
  moment a part flips DONE (the standing "PRs as drawings are ready" rule).
- A checkpoint commit (slice files only, no PNG/review) is NOT PR-ready — agents
  legitimately commit early to rebase onto origin/main, per AGENTS.md.

**Fable quota is the real ceiling** (user: "keep launching until Fable hits the
wall"). Read it live from `https://api.anthropic.com/api/oauth/usage` with the
`claudeAiOauth.accessToken` from `~/.claude/.credentials.json` + header
`anthropic-beta: oauth-2025-04-20`. The binding limit is the model-scoped entry in
`limits[]` whose `scope.model.display_name == "Fable"` (weekly, resets Mon 08:00 UTC);
`five_hour`/`weekly_all` are looser. ccusage only shows consumption ($/tokens), NOT
remaining quota. Extra-usage overage credits are exhausted, so a weekly-limit hit
blocks hard until reset — no cushion.

**Seat is the throughput bottleneck**, not agent count: N agents author in parallel
but every `doit part:`/`drawing:` COM build serializes on the machine-global seat
lock. More agents = deeper queue, same build throughput. See [[com-seat-lock]].

Shared-file merge points across drawing PRs: `_drawing_registry.py` (every slice adds
a row) and `_drawing_common.py` (shared helpers, e.g. `add_view_centerline` added by
pivot-bushing #308; a backward-compatible `entity_type="EDGE"` param on
add_datum_feature/add_feature_control_frame/add_surface_finish added by BOTH pen-marker
#320 and transgear-stub #324 so GD&T/finish symbols attach to a **revolve's
`"SILHOUETTE"` edges** — a turned/revolved part has no model edges on its flanks). When
finalizing a revolve's drawing FOR an agent, `git status` for a modified `_drawing_common.py`
and FOLD IT INTO the commit — its draw script depends on it, so committing the 6 slice
files alone breaks the CI build. Expect trivial additive conflicts; land infra PRs first,
rebase the rest.

**codex-on-this-machine is NOT truly blind** — a SessionStart hook forces a memory lookup,
so `codex exec ... -i sheet.png` explores the filesystem (rg for MEMORY.md, follows the
image path back into the repo) even from a neutral cwd with `--skip-git-repo-check`. The
machinist verdict is still produced (buried in ~400 lines of tool-call log; grep
"can it be made|Disposition|Verdict"), but treat it as advisory and do a LEAD visual pass
as the real gate. See [[codex-drawing-image-review]].

**2026-07-15 run outcome:** fanned out ~18 Fable drawing agents in 4 waves; **17 PRs
landed** (#305-308, #312-324) before Fable hit **96% weekly (critical)** — the wall. The
finalize-myself pattern (Opus commit+rebase+PR, codex via CLI — neither touches Fable)
converted the built-but-idle drawings without burning the last Fable. Two didn't converge
(cone_gear_shaft 4-diameter, crankshaft cross-hole — draw scripts written but the drawing
build errored); left for the Jul-20 Fable reset. Collisions when committing under a
still-iterating agent (cylinder_gear_shaft): the agent squashed my pushed commit into its
better version — reconciled by force-pushing the agent's SHA to the PR. Only commit-for-them
when the agent is genuinely idle/done, and be ready to reconcile.

**Merge-cascade phase (the "merge all PRs once Codex green" ask).** Every drawing PR appends
one `DrawingSpec` row to the SAME `DRAWINGS` tuple, so merges are STRICTLY SERIAL — each merge
dirties the registry of all remaining PRs, forcing a rebase per merge. Mechanics that worked:
- **Deterministic registry resolver** (`scratchpad/resolve_registry.py`): takes `origin/main`'s
  authoritative registry + inserts ONLY the branch's missing `DrawingSpec` block(s) (keyed by
  `name=`), validates with BOTH `ast.parse` AND `compile()` (Py3.14 parses repeated kwargs but
  rejects at compile — a union-merge corruption signature). NEVER use git `merge=union` on the
  registry — it fuses multi-line specs into one with repeated `name=`.
- **`_drawing_common.py` conflicts are docstring-only.** Multiple slices add the SAME
  `entity_type`/`add_view_centerline`/basic helpers — git auto-merges the CODE and only flags
  the divergent doc prose. Resolve with `git checkout --ours` (main is canonical post-merge);
  the shared helper the branch's draw script needs is already present from the first merge.
- One reusable `merge_pr()` bash fn (rebase → resolve registry → `--ours` drawing_common →
  `rebase --continue` loop → verify registry import + pytest → `push --force-with-lease` →
  `gh pr merge --merge`). A mechanical registry-only rebase preserves a standing Codex 👍 (the
  reviewed draw-script bytes are untouched), so merge on green without waiting for the
  post-rebase re-review.

**Codex RE-REVIEWS after every fix push and often finds a ROUND-2 (and 3) issue** on the same
PR (e.g. #318 pen_v_block: 2X FCF → then basic-dim boxing + finish-both-bores; #319
column_clamp: drop _drawing_marks import → then split the geom constants out of the drawing
spec so assemblies don't rebuild on note edits; #314 crank_pin: 1:45→1:48 taper → then "Ø5.94
≠ real No. 2 pin, relabel custom 1:48"). Chase to green — they're legit P2 build-hygiene/GD&T.
Watch all open PRs with ONE persistent Monitor polling codex body-reaction (👍=green,
👀=reviewing) + last review state; merge on the 👍 transition.

**Fix-agents share the SAME 5-hour session quota and die mid-task** ("session limit · resets
<time>"). When they do, the LEAD (Opus, extra-usage on) takes over the remaining fixes inline —
verify each dead agent's worktree ON DISK first (idle≠done here too): several had correct-but-
uncommitted edits (pen_v_block, pen_rod, crank_pin) or a half-done new module (column_clamp
geom) to finish, not redo. A stray uncommitted edit in a worktree (pinion_pivot_block_spec note
tweak) BLOCKS the rebase — `git checkout --` it if unrelated to the findings and the PR is
already green at the committed HEAD.

**COM gotcha — boxing a curated dim BASIC:** `curate_view_dimensions` returns `IAnnotation`;
`set_basic_dimension` wants the `IDisplayDimension`. Convert via
`adapter._attempt(lambda a=ann: a.GetSpecificAnnotation())` first, else `AddDimension2`-return
dims box directly. "Parameter not optional" com_error = you passed the annotation, not the
display dim.

**All 23 drawing specs merged.** FOLLOW-UP left open: crank_arm (merged) still says "taper-ream
FOR NO. 2 TAPER PIN" while crank_pin is now a custom 1:48 — reconcile crank_arm's nomenclature
in a separate PR. Plus the 2 unbuilt (crankshaft, cone_gear_shaft) for the Fable reset.
