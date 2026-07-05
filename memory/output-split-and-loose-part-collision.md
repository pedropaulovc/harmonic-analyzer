---
name: output-split-and-loose-part-collision
description: output.SLDASM split into 4 flat subs (summing/magnifier/pen/paper-drive); why the spare T18 gear lives in paper-drive not at top level (leaf-name collision)
metadata:
  type: project
---

Phase 1 of the restructure (plan fold-pen-into-magnifier-serene-yeti) is DONE +
fully green on branch `claude/restructure-output-subassemblies` (4 commits, pushed,
no PR yet — paused for sign-off per [[feedback-pause-between-phases]]). The
monolithic `output.SLDASM` (ch 18-25, ~123 comps) was split into FOUR FLAT
top-level subs, NOT nested (nesting would add an assembly→assembly edge the
dodo.py refresh DAG doesn't model):

* `summing` (ch 18-19, 9 comps) · `magnifier` (ch 20-21, 11) · `pen` (ch 24, 7,
  owns the F5 pen_driver, MOTION_OWNER="pen") · `paper-drive` (ch 22-23-25, 91
  incl. 64-link chain + spare T18).
* Top-level tree = 7 subs (frame·drive-train·channel·summing·magnifier·pen·
  paper-drive) + 1 loose part (measuring-stick). Value chain reads
  summing→magnifier→pen; paper-drive is the orthogonal time-base.
* build_output_assembly.py DELETED; geometry byte-identical (Phase 1 kept `fix`).
* verify.py component bands tightened to measured 9/11/7/91/8.

**Non-obvious gotcha that cost a build (the spare T18 chain wheel):**
`place_component(ground=True)` ends with `fix_component(name=<leaf>)`. The MCP
adapter resolves a component by LEAF name; when the same part-type is also nested
inside subassemblies in the same tree, the leaf is AMBIGUOUS and resolution lands
on a NESTED instance, failing with e.g.
`fix ... failed: Failed to select component: 'drive-train-1/transgear-removable-1'`.
transgear-removable exists 3× (T12 in drive-train, T24 in paper-drive, T18 spare),
so placing the spare DIRECTLY at top level collided. measuring-stick (unique name)
was fine. **Fix: house such a part INSIDE the sub where it's a flat sibling** (the
spare T18 went into paper-drive next to the mounted T24 → unambiguous `-2` suffix,
exactly as the book's single output group held both removables). Rule of thumb: a
loose top-level part is only safe if its part-type appears nowhere nested.

Supersedes the output-band details in [[output-layout-m64]]. Phase 2 (deterministic
`fix`→interface mates, per [[fix-relations-last-resort]]) followed.

> **UPDATE (later):** this Phase-1 branch MERGED as PR #41 (2026-06-20) — no longer
> "no PR yet"; Phase 2 (semantic/datum-locate mates) began 2026-06-27. The component
> bands have since drifted (measured ≈ summing 8 / magnifier 12 / pen 8 / paper-drive 87 /
> top 8 — magnifier +lever-wire, pen +pen-wire, chain 64→60 links). The leaf-name
> collision LESSON is unchanged.
