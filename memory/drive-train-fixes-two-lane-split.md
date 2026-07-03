---
name: drive-train-fixes-two-lane-split
description: Six drive-train fixes run as stacked PRs in two lanes on two SW seats — this seat owns the cone side (PR1/PR2), another seat owns the pinion side (PR3–PR6 from branch pr3-brackets); don't cross lanes
metadata:
  type: project
---

The six drive-train fixes (2026-07) run as stacked PRs split into two lanes on
two SolidWorks seats, both based on branch `pr1-cone-swing-platform` (PR #147):

- **Lane A (this seat)**: PR1 cone swing platform (#147) + PR2 thumb-screw
  lock knob on that platform.
- **Lane B (other seat)**: PR3 bracket reshape → PR4 pinion leaf spring →
  PR5 cam engage → PR6 handle resize + interference proof, sequentially, from
  branch `pr3-brackets`. Brief: `HANDOFF-PR3.md` at that branch's root
  (deleted before PR3 merges).

**Why:** the pinion PRs are internally sequential (strap geometry → spring/cam
mounts → engage travel → interference proof), so parallelism is exactly two
lanes. Both lanes edit `build_drive_train_assembly.py`; the shared pr1 base
avoids conflicts.

**How to apply:** on this seat, do NOT edit pinion/arbor-side files
(`build_arbor_pedestal.py`, `build_pinion_*.py`, and the pinion region of
`build_drive_train_assembly.py`) while lane B is active — the other seat owns
them. Process rules for every PR in both lanes: stacked, no autocommit, NO
auto-merge (explicit user override of [[global auto-merge default]]), full
`doit` build green + self-contained inspection snapshot in
`cad/out/inspection/prN/` before asking the user to inspect. Delete this
memory when all six PRs are merged.
