---
name: solidworks-modeling-pitfalls
description: "SolidWorks COM modeling pitfalls learned live (SW 2026 via PyWin32Adapter): revolve axis edge breaks booleans, FeatureCut4 27 params + -Y default, direct-db circles, helix tessellation slack, cone-on-drum incline from drum pitch (sin i = step/drum-pitch)"
metadata:
  node_type: memory
  type: reference
  originSessionId: 5e824fa0-7bda-4055-8655-aa59ed6f0ef9
---

Live-verified SolidWorks 2026 COM facts (PyWin32Adapter, SolidworksMCP-python),
discovered during harmonic-analyzer M6.4:

- **A 360° revolve must pass EXACTLY 2π rad or the seam never knits**: the
  adapter's legacy `FeatureRevolve2` branch (SW major != 33, i.e. SW 2026)
  computed `Dir1Angle = angle * 3.14159 / 180`, so 360° came out 6.283180 —
  5e-6 short of 2π (6.283185). SolidWorks then does a near-360 *blind*
  revolve and leaves the start/end profile as TWO coincident planar cap
  membranes; the swept face degenerates so the body **tessellates as the
  flat profile** (STL export + viewport image both show a flat half-disc)
  while `GetMassProperties().Volume` still reads the correct solid value.
  A volume gate sails right past it — diagnose on the B-REP: `GetBodies2(0)
  → GetFaces → GetSurface().IsSphere()/IsPlane()`; a clean ball is exactly
  ONE spherical face (capped = `[sphere, plane, plane]`). Fixed in
  SolidworksMCP PR #57 (`math.pi`); `build_chain_bead.py` now asserts the
  single-face shape. Burned ~2h chasing this as a "hemisphere" — the giveaway
  is volume-correct-but-renders-flat. Affected EVERY 360° revolve part.
- **On-axis 360° revolve poisons later booleans**: revolving a rectangle
  whose edge lies ON the centerline leaves a degenerate axis edge in the
  b-rep; ANY later boss/cut whose body crosses that axis fails silently
  ("FeatureExtrusion3 returned None", revolve-second also fails). Model
  rods as EXTRUDED CIRCLES instead (probe matrix in the deleted probe
  script; recipe in `build_knife_stay.py`). Revolves are fine when nothing
  later crosses the axis (e.g. `build_pen_marker.py`).
- **add_circle on a Right-plane sketch** fails unless wrapped in
  `set_sketch_direct_db(True)` … `(False)`.
- **On-axis revolve's SEAM EDGE poisons inference-ON circles on it**: a
  360° revolve of a Top-plane profile leaves its seam edge along +X on
  the z=0 face; an inference-ON `add_circle` whose CENTRE lies on that
  edge picks up an auto-relation to it, after which EVERY driving
  point-pair dim (and following dims in the sketch) fail with
  "SolidWorks failed to create ... sketch dimension" while the sketch
  stays under-defined, 0 over-defining relations (transgear-removable
  pin holes at (±9.5, 0); bisected in `diag_onaxis_pin.py` scenarios
  A–I: bare/extruded/equation parts all pass, revolved part fails,
  direct-db on the same part passes). Fix: create circles direct-to-DB.
- **`extrude_at_offset` (raw FeatureExtrusion3 with T0=3 swStartOffset)**
  is the proven path for direct-db quad sketches; negative offsets work;
  the adapter's mid-plane extrusion can fail on direct-db sketches.
- **FeatureCut4 takes 27 params** — the last is OptimizeGeometry; omitting
  it gives "Parameter not optional". The default cut direction from a
  Top-plane sketch is **−Y**; pass Dir=True to cut +Y (verified live in
  `build_column_clamp.py`: the un-flipped cut removed the wrong band).
- **Helix/spring volume gates need slack ∝ base volume**: helix-body
  tessellation noise in mass-property diffs is ~0.02–0.03% of the WHOLE
  part, which can dwarf a small added feature. `_common.add_spring_end_hooks`
  uses `slack = 0.0003 * before`. Don't widen the feature tolerance itself.
- **Involute gear phasing** (`_gear.py` recipe): the seed tooth GAP is
  centred at +γ/2 (flanks cross the pitch circle at ±π/(2N) about the gap
  centreline) — so for N divisible by 4, a TOOTH (not a gap) sits at the
  ±90° positions. Rack meshes need the half-pitch offset (see
  [[output-layout-m64]] platen-rack entry).
- **Inclined-cylinder clearance needs r/cos(i), not r**: a cylinder
  inclined at i to the bore axis has an ELLIPTICAL constant-z
  cross-section, in-plane semi-axis r·sec(i), and its surface reaches
  r·sin(i) past its end station in z. (Discovered sizing the M6.6
  canted-gear bores; those seats are retired, the geometry fact stands.)
- **Cone-on-drum mesh: derive the incline from the DRUM pitch, not the
  shaft pitch** (M6.7, replaces the M6.6 canted-seat advice — canting
  satisfied the checker but visibly deformed the cone vs the book
  photo, user-rejected). A gear seated perpendicular to a shaft
  inclined i in plan contacts a parallel-axis drum only via the tooth
  at the drum-facing azimuth, which sits r·sin(i) ALONG-SHAFT south of
  the gear centre — so each centre must ride r_j·sin(i) NORTH of its
  drum plane, and the 20 centres are collinear iff
  sin(i) = radius_step/DRUM_z_pitch (harmonic analyzer: 2.54/7.0568 →
  21.0976°; arcsin(2.54/7.5) = 19.8° is the wrong triangle leg —
  0.44/station z-drift = "most gears not meshing"). Along-shaft seat
  pitch = drum_pitch·cos(i) (forced face 7→6.5). Model the book's
  "oblique partial engagement" literally: penetration varies
  ±(face/2)·tan(i) across the drum face; back the centre grid off so
  the DEEPEST crossing stays ~0.15 short of working depth. Elegance
  check: tan(half-angle) = step/seat_pitch = tan(i) → drum-side cone
  generator parallel to the drum axis (the p.18 seam).
- **`check_no_interference` raises on EVERY returned pair**, including
  0.00 mm³ slivers (TreatCoincidenceAsInterference=False already
  filters true tangency), so design ≥0.25 mm margins, not 0.1.
- **Sketch inference snaps small offsets to the origin/axes silently**:
  a rectangle corner 0.75 mm off the origin snapped back to 0 with
  inference on, rebuilding the untrimmed shape with NO error (caught
  only by the volume gate — pen-frame TRIM_NEAR). Any near-origin /
  near-axis coordinate needs `set_sketch_direct_db(True)` around it,
  and every dimension change deserves an analytic volume assert.
- **Unabsorbed sketches default SHOWN and render in EVERY assembly
  instance** while staying invisible to GetBox/boxes-JSON scans (helix
  seed sketches after InsertHelix, orphan sketches from failed cuts).
  `_common.blank_sketch()` them; `IFeature::Visible` is an int: 2 =
  shown, 1 = hidden (a `== True` filter sees nothing).
- **Appearance hierarchy beats doc MPV**: `apply_material` attaches the
  database material's render appearance (.p2m) at PART scope;
  `doc.MaterialPropertyValues` only retints its primary colour. Plain
  metal/iron appearances track the tint, but TEXTURED ones (Oak's wood
  image) ignore it — set the colour at BODY scope too
  (`IBody2.MaterialPropertyValues2`, hierarchy face > body > part);
  `_common.apply_color` now does both. Enumerate appearances with
  `ext.GetRenderMaterials2(2, None)` (works even though `dir()` on the
  typed wrapper lists no Render members).
- **`mirror_placement` needs the part's STL bbox at insert time**: it
  calls `stl_bbox_mm(stem)` on `cad/out/stl/<stem>.STL` to locate the
  part-local mirror plane, but brand-new parts have NO STL yet —
  `export_models.py` only exports comparisons/manifest.json models plus
  assembly-component meshes, and running it before the part is in an
  assembly exports nothing useful (it re-exported unrelated stale models
  for ~4 min). Fix: give every new x-symmetric part an explicit
  `MIRROR_PLANE["<part>"] = ("x", 0.0)` entry in `_common.py` (precedent:
  wheel-bar, drive-chain; ch25 added all five pinion parts this way).
- **Shaded-WITH-edges captures paint fine geometry black**: the fluted
  columns (16 grooves × 2 sharp edges over 1070 mm) rendered as solid
  black bars at ~10 px width — the part colour was never wrong. The
  comparison pipeline (`render_compare.py`) now calls
  `IModelDoc2::ViewDisplayShaded()` after every open; book plates have
  no outline ink either. Per-part `export_image` PNGs still show edges,
  so thin parts read dark there — judge colour from assembly renders.

- **Chain component pattern (raw COM, live-proven in
  `_common.create_chain_component_pattern`)**: select path sketch mark 2,
  seed COMPONENT mark 1, path-alignment geometry (a part reference AXIS
  normal to the path plane works for spheres) mark 256, alignment PLANE
  mark 16384 — then `FeatureManager.CreateDefinition(112)` (swFmLocal-
  ChainPattern), set props, `CreateFeature`. Enum values: PitchMethod
  Distance=0/DistanceLinkage=1/ConnectedLinkage=2; AlignToSeed=0/
  TangentToCurve=1; Options Static=0/Dynamic=1 (read via swconst typelib
  `gencache.EnsureModule('{4687F359-...989}', 0, 34, 0).constants`).
  Gotchas: (1) select strings need the DOC TITLE suffix — an unsaved
  assembly is `AssemN`, never hardcode the save name; (2) `FillPath=True`
  UNDER-fills a closed loop (61 of 63 beads, ~2-pitch gap) — set
  `FillPath=False` + `InstanceCount=N` (count INCLUDES the seed) +
  `Spacing`; (3) the seed must be UNFIXED at CreateFeature (fix it after;
  it is not an instance); (4) instances report `GetConstrainedStatus` 2
  (under) though feature-driven — exempt via `IComponent2::
  IsPatternInstance()`; (5) instances chord-step on tight arcs (gaps
  5.98..6.43 vs arc pitch 6.39) — gate spacing at ±50%, not ±1%.
- **Mirrored sketch loops**: an assembly sketch has no part-local mirror
  shim — author in FINAL post-mirror coords: negate x AND swap every
  arc's start/end (mirror reverses CCW; add_arc draws CCW). Exactly-merged
  junctions stay merged. A tangent-continuous arc/line loop fully defines
  with 2 centre anchors + 3 radials + ALL 4 explicit junction tangents;
  the retired band's over-definition came from its two offset loops'
  concentric centres MERGING at creation and being double-anchored.

- **Converting fix-all to mated DOF can EXPOSE hidden layout slack** (Phase E,
  M6 op-sim): a 2-bore link FIXED at an exact transform tolerates its two bore
  targets being slightly inconsistent with its bore spacing — the fix just
  freezes the part mid-gap. Replacing the fix with a proper pin↔bore coincident
  snaps ONE end exact and throws the OTHER end off by the slack. Here the
  connecting-rod is 127 mm between bores but the rocker-bore→cam-lobe span is
  127.39 mm; Phase B's correct pin coincident pushed the cam RING 0.39 mm off
  the cylinder-gear lobe (a 0.1 mm-clearance journal) → 20× 38.92 mm³ top-level
  interference, invisible to channel's own gates (the cam is in another sub).
  Fix: pin the link at its exact design pose anchored to ASSEMBLY datums (ring
  exactly on the lobe; slack absorbed at the loose pin), via the prismatic
  pattern (slide axis = ring's Z bore): two axis-to-plane distances (Right=X,
  Top=Y) + spin_driver via the pin bore (Rz) + Front-plane distance (Z). The
  real link revolutes belong in the flexible-sub motion study. Diagnose by
  measuring bore world-points old(green) vs new — identical cam + drifted ring
  pinpoints WHICH part moved without guessing. See [[flexible-subassemblies]].
- **A revolute snapshot must target the PLACED (design) pose, not a post-mate
  measurement**: `_revolute`'s spin driver originally measured its off-axis
  target AFTER the radial/axial mates ran, freezing sub-mm mate-solve drift.
  Capture it from `world_point` at the placed pose (parts are inserted on their
  exact mirrored transforms, so design IS the on-solution target).

- **Saving an assembly you OPENED from disk: never `adapter.save_file(PATH)` —
  it DESTROYS the file** (live, drive-train.SLDASM, twice). Its SaveAs branch does
  `swApp.CloseDoc(PATH)` then `os.remove(PATH)` BEFORE `currentModel.SaveAs3(PATH)`
  — when the active doc IS that path, CloseDoc closes the very doc being saved, so
  SaveAs3 runs on a disconnected COM object and raises `-2147417848 "The object
  invoked has disconnected from its clients"` AFTER the file is already deleted →
  gone. (Build scripts that CONSTRUCT a new doc and SaveAs are fine: CloseDoc is a
  no-op since the doc isn't registered at that path yet.) To save an opened-in-place
  doc, do NOT use `save_file` at all — call `Save3` directly (next entry).
- **Saving an opened-in-place assembly = `Save3(Silent)` with REAL byref outs; the
  "Makers seat is hostile to silent saves" claim was WRONG** (corrected; user was
  right to doubt it). The save NEVER needed a UIAutomation watchdog — that whole
  saga was self-inflicted by two wrong adapter calls: `save_file(PATH)` destroyed
  the file (entry above), and `save_file()` (no path) runs `Save3(1, None, None)` —
  passing Python `None` for `Save3`'s two `[out]` byref params makes the win32com
  call FAIL, so the adapter falls through to the blocking parameterless `Save()`
  that raises the **"Component documents must be saved → [Save All]"** modal. The
  earlier "Save3 silently no-ops" reading was an artifact of testing on a doc the
  destructive SaveAs path had already disconnected. The correct call:
  ```python
  import pythoncom; from win32com.client import VARIANT
  err  = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
  warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
  model.Save3(1 | 8, err, warn)   # swSaveAsOptions_Silent | SaveReferenced
  ```
  → `ret=True, err=0, warn=0`, mtime advances, the change persists on reopen — no
  dialog, no watchdog, ~0.4 s. The modal only appears with parameterless `Save()`
  AND dirty *referenced* docs; `SaveReferenced (8)` saves those silently too, and
  for an assembly-only change (config + mate suppression) the part docs stay clean
  so even plain `Silent` writes. Proven by `cad/scripts/repro_inplace_save.py`
  (open from disk → add config → `Save3` on a copy, real file untouched). Canonical
  per SW docs/forums (CodeStack "save all silently"; SW "Rename Components and Save
  Assembly" notes a bare save errors "without first saving its references" → why
  the 8 flag). Still gate on `model.GetSaveFlag()` (True = dirty) to skip a clean
  idempotent re-save. `_click_save_all.ps1` + the watchdog are DELETED.
- **Config-scoped mate suppression** (`SuppressMateParameters(configuration=...)`
  → `SetSuppression2(action, swSpecifyConfiguration=3, [cfg])`): a derived config
  that suppresses gear mates is the right model for an engagement-state ENUM. But
  GearMate suppression FREES the driven members — the harmonic gear train's
  rotation is pinned by ONE crank park driver flowing THROUGH the meshes, so
  cutting the 21 meshes drops exactly the 42-member train to under-defined; that is
  physically correct for "disengaged" (assert no STRUCTURAL part leaks instead of
  asserting full-definition). See [[dof-refactor]].

See [[solidworks-3dx-launch]] for session/launch rules.
