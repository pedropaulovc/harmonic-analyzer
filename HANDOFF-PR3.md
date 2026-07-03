# Handoff — pinion lane (PR3 → PR4 → PR5 → PR6)

> **Delete this file before merging PR3.** It is a working brief for the seat
> running the pinion lane, not documentation.

## Context

Six drive-train fixes are in flight as stacked PRs. Lane A (this branch's base)
handled the cone side: PR1 `pr1-cone-swing-platform` (open, #147) put the cone
gear set on a swinging platform; PR2 (thumb-screw lock) continues on that seat.
**This branch (`pr3-brackets`, forked from the pr1 branch) starts lane B — the
pinion side.** Base on pr1, NOT main: nearly every PR edits
`cad/scripts/build_drive_train_assembly.py`, and a shared validated base keeps
the lanes conflict-free.

The four lane-B issues, in the user's words, to be fixed **sequentially in this
order** (each defines geometry the next depends on):

1. **PR3 (this branch)** — "all brackets for all 3 gears dont match size and
   shape on device". Reshape the cylinder-gear arbor pedestal
   (`build_arbor_pedestal.py`) from the current block into the BLACK tapered
   round-top strap visible in still `t00393`; check the pinion straps
   (`build_pinion_bracket.py`) against book ch. 25.
2. **PR4** — "missing spring that keeps tension on pinion gear when disengaged
   by default": a brass leaf spring, default-disengaged tension on the pinion.
3. **PR5** — "mechanism to engage pinion gear does not work; probably should be
   a cam": replace the current lift-rod engage path with a cam.
4. **PR6** — "both handles for rotating pinion gear and engaging pinion gear
   dont have the proper size and will interfere with each other if rotated":
   resize (`build_pinion_handle.py` / `build_pinion_lever.py`; current tilts
   HANDLE_TILT_DEG=65 / LEVER_TILT_DEG=32) and PROVE no mutual interference
   through full rotation, with spring (PR4) + cam (PR5) present.

Why sequential: PR3's strap geometry is what PR4's spring and PR5's cam mount
to; PR5's cam sets the engage travel and lever throw PR6 must clear; PR6's
interference proof is meaningless before spring + cam + final handles coexist.

## Reference material (inspect BEFORE modeling — user instruction)

- Book chapters: `references/albert-michelsons-harmonic-analyzer/`
  — `25_Pinion_Gear.pdf` (pinion straps, handles), `13_Cylinder_Gear_Set.pdf`
  (arbor/cylinder brackets), `12_Cone_Gear_Set.pdf` (cone side, for shape
  comparison across "all 3 gears").
- Video stills: `references/engineerguy-youtube/stills/` (contact sheets
  `sheet_v4_*.jpg` etc.), per-frame in `stills/full/` (e.g. `t00393` = the
  black tapered round-top strap; video 4/4 "Operation" covers engage/disengage),
  curated crops in `keyframes/` (`sheet_v4_pinion.jpg`). Transcripts: the
  `.vtt` files one level up.

## Process constraints (user-mandated, non-negotiable)

- **Stacked PRs; no autocommit; NO auto-merge** (explicit override of the
  global auto-merge default). Deliberate commits only.
- Per PR: full `uv run python -m doit -n 4` green with SolidWorks open, then
  save a **self-contained inspection snapshot** to `cad/out/inspection/prN/`
  (copy the built `.SLDPRT`/`.SLDASM` set + any `.park.json` sidecars so
  references resolve in-folder; the dir is gitignored) and tell the user which
  mates to suppress / what to drag to inspect the change.
- Arm the PR-lifecycle Monitor from the global CLAUDE.md template after
  `gh pr create` (no auto-merge step).
- Invoke `/developing-solidworks` as the FIRST tool call of the session
  (AGENTS.md). SolidWorks is launched ONLY via the 3DEXPERIENCE Start-menu
  shortcut.

## Coordination with lane A

- **Don't touch cone-side files**: `build_cone_*.py`, `build_crank_pedestal.py`,
  `cad/config/parts/cone-*.yaml` — PR2 (thumb-screw lock on the platform) owns
  that region on the other seat. Shared file `build_drive_train_assembly.py`:
  keep edits to the pinion/arbor region to minimize rebase pain.
- The remote Azure cache is shared rw: your first `doit build` on this base
  should restore most parts published by the lane-A seat. Misses are normal
  for anything that seat hasn't built under the current submodule pin
  (SolidworksMCP-python @ ab2c3f1 — run `git submodule update --init` before
  `uv sync`). `doit cache_status -- <filter>` explains any miss.
- Known pending on lane A (don't duplicate): a Codex review fix in
  `build_mobility_probe.py` (p1 probe family → `cone-swing-platform`) will land
  on the pr1 branch; you'll pick it up on the next rebase.

## Bootstrap on this seat

```
git clone --recurse-submodules <repo-url> && cd harmonic-analyzer
git checkout pr3-brackets
git submodule update --init      # SolidworksMCP-python @ personal, references
uv sync
# open SolidWorks via the 3DEXPERIENCE shortcut, then:
uv run python -m doit -n 4       # should be mostly cache restores
```
