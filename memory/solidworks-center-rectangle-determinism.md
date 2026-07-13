---
name: solidworks-center-rectangle-determinism
description: Native CreateCenterRectangle's origin anchor depends on the per-seat swSketchAddConstToRectEntity option (id 584) — the build must add the anchor explicitly, not rely on it
metadata:
  type: reference
---

**Native `ISketchManager.CreateCenterRectangle(0,0,0, hx, hy, 0)` does NOT
deterministically anchor its centre to the sketch origin.** The centre→origin
coincidence (and the rectangle's other auto relations) is added by SolidWorks
only when the **system option "add constraints to sketched rectangles"** is ON —
enum `swSketchAddConstToRectEntity`, **swconst id 584**. On a seat where it is
OFF, the rectangle is drawn at the origin geometrically but left FREE to
translate: a `define_centered_rectangle` profile comes back `under_defined` even
with width+depth dims, and the part build fails
`sketch not fully defined (state='under_defined')`.

Key facts (verified live, SW 3DEXPERIENCE R2026x / "for Makers"):
- The option is **READable** via `swApp.GetUserPreferenceToggle(584)` (returns
  the real bool) but **NOT settable** — `SetUserPreferenceToggle(584, True)` is a
  silent no-op (read-back stays False). So you cannot force it as a preference at
  build start; the fix must be in the geometry code.
- `swSketchAutomaticRelations` (id 9) and `swSketchInference` (id 249) being ON is
  NOT enough — the rectangle-specific 584 is the lever for the origin anchor.
- With 584 OFF, `AddToDB=False` still adds the EDGE orthogonality relations; only
  the centre→origin anchor is missing. Adding a single `midpoint(origin,
  <construction diagonal>)` relation flips the profile to `fully_defined`
  (proven: native rect + w/d dims = under_defined → + midpoint anchor =
  fully_defined).

**Fix (main PR #283, `define_centered_rectangle` Path A in `cad/scripts/_common.py`):**
capture one of `CreateCenterRectangle`'s two construction diagonals; after the
width/depth dims, if `check_sketch_fully_defined()` is not already
`fully_defined`, `add_sketch_constraint("origin", diagonal, "midpoint")`. It is
**idempotent** — skipped when the native anchor already fixed the sketch (seat
with 584 ON), so it never over-defines. Safe because every
`define_centered_rectangle` call owns a fresh single-entity sketch
(`create_sketch → rectangle → ensure_fully_defined → exit_sketch`), so the
whole-sketch status check is exactly "is the rectangle anchored".

Getting the swconst ids: they are NOT in `adapter.constants` (curated subset) and
the doc enum tables list no ints. Load the TLB directly:
`pythoncom.LoadTypeLib(r"...\SOLIDWORKS 3DEXPERIENCE R2026x\SOLIDWORKS\swconst.tlb")`
then walk `TKIND_ENUM` typeinfos reading `GetVarDesc(v)[1]` (already an int on this
pywin32). Ids found: swSketchAutomaticRelations=9, swInputDimValOnCreate=10,
swSketchInferFromModel=95, swSketchInference=249, swSketchAddConstToRectEntity=584.

It is a **document property** (part template), NOT a system option: absent from the
system registry `...\SOLIDWORKS 2026\General` and the chezmoi `swSettings.sldreg`
(only the unrelated `Add Dimensions To Rectangle Entity` exists), and the system
`swApp.SetUserPreferenceToggle` is a no-op — it is settable only via
`IModelDocExtension.SetUserPreferenceToggle` and stored in the `.prtdot` template.
So the sldreg cannot carry it. Durable follow-up: **issue #284** — ship a
repo-tracked `.prtdot` with this baked True (+ IPS units) and build parts from it
via `create_part()` (`io.py:268` currently uses seat-default `NewPart`).

Related: this was the true root cause behind the "16-part under_defined" scare in
[[zero-late-binding-task]] — a per-seat option drift, not a code regression.
Beware `swInputDimValOnCreate` (id 10): if ON it pops a modal dimension-entry box
that would HANG a headless build — keep it OFF.
