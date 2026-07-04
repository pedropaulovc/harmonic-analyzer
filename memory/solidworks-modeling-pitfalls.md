---
name: solidworks-modeling-pitfalls
description: "SolidWorks COM modeling pitfalls learned live (SW 2026 via PyWin32Adapter): revolve axis edge breaks booleans, FeatureCut4 27 params + -Y default, direct-db circles, cut both_directions depth = TOTAL (half per side), helix tessellation slack, cone-on-drum incline from drum pitch (sin i = step/drum-pitch), arc-centre locating dims reject equations"
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
  rods as EXTRUDED CIRCLES instead (e.g. `build_gooseneck.py`'s vertical
  leg; the former `build_knife_stay.py` example was removed with that part —
  see [[knife-stay-removed]]). Revolves are fine when nothing
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
  Corollary (bit again 2026-07-03, cone-pivot-screw slot): a cut's default is
  OPPOSITE the sketch normal for ANY plane, so a blind cut from a top/far-FACE
  offset plane down into the body needs **NO** `reverse_direction` —
  reversing sends it into air, the no-intersection cut falls through the
  adapter's FeatureCut4→Cut3 overload chain, and a mis-mapped arg can land as
  a FLIPPED-SIDE cut (removed the head-top ANNULUS around the slot: caught by
  the volume gate, removal = (disc − strip)·depth exactly). Only a cut running
  ALONG the normal (material above the sketch plane, e.g. a slot cut from an
  origin head-face with the body extruded +Y) takes `reverse_direction=True`.
- **A sketch on a REFERENCE plane enumerates the plane's own offset dim
  first** in the `GetFirstDisplayDimension` walk (`D1@<plane>` before the
  sketch's own `D1@<sketch>`), shifting positional renaming and tripping the
  `SketchDims.apply` recorded-count guard. `_common._display_dimensions`
  now takes an `owner` filter (FullName middle segment) and `apply`/
  `name_dimensions` pass it — sketches on principal planes are unaffected.
- **`ExtrusionParameters(depth=D, both_directions=True)` on a cut = D TOTAL,
  split D/2 per side of the sketch plane** — NOT D each way. A through-cut of a
  plate extruded +Y from its own Top-plane sketch (plate spans y 0..T) with
  `depth=T+4` reaches only (T+4)/2 up and leaves the top uncut (cone-swing-
  platform pivot hole: removed exactly π r²·5.175 of a 6.35 plate; caught by the
  ±1% volume gate). The pen-v-block exemplar's `THROUGH_CUT_DEPTH = 80.0 #
  mid-plane total; > any extent crossed` states the convention — size the total
  generously (≥ 2× any extent crossed), never `extent + small margin`.
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
- **A `concentric` mate on two named reference AXES fails** with
  `AddMate5 failed: unknown error` — concentric wants a cylindrical FACE/
  circular edge, not a reference axis. To make two parts COAXIAL via the
  named-axis idiom (`name_bore_axis` → `Axis<N>@<comp>`), the mate is a
  **`coincident` between the two axes** (collinear = coaxial), exactly as
  drive-train's `_key_to_shaft`/`_seat_on_crank` and summing's
  `_coaxial_seat` do (#114). Reserve `concentric` for when you actually
  hold a cylindrical-face ref (`bore_axis_ref` by point) — and avoid that
  for occluded/internal bore walls (view-dependent point selection, see
  the `name_bore_axis` docstring). Burned one build cycle assuming the
  user's word "concentric" meant the mate TYPE; on reference axes it's
  `coincident`.
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
  asserting full-definition). See dof-refactor (dropped memory).

- **Feature-replay of an external part: a volume+bbox match is NECESSARY but
  NOT SUFFICIENT — a Z-MIRRORED build matches both yet is upside-down.**
  Reproducing `rocker-arm-support.SLDPRT` (a Z-up trapezoid wedge), the
  Top-plane sketch maps sketch-y → **−Z**, so the trapezoid's wide foot must be
  drawn at sketch **+Y** to land at model Z=−88.9 (the real foot). Drawing it at
  −Y put the foot at +Z: every per-feature volume + the bbox matched the source
  exactly (symmetric squares/fillets/holes), but the part was mirrored in Z —
  caught only when real-coordinate chamfer FACE selection points missed. Verify
  orientation independently of volume (hole axes, an asymmetric face point), not
  just the mass ladder.
- **Selecting a whole FACE for chamfer/fillet by a point: use a point on the
  SOLID region, never a bbox centroid that can fall in a window/void.** New
  `_select_faces_geometric` (SolidworksMCP PR #69) walks `IFace2.GetClosestPointOn`
  and picks the nearest face within tol (5 mm). On the cut part the slant face is
  a frame around a window, so its bbox centre (20.1,0,0) sits 5 mm inside the
  void → miss; a point in the solid foot band (31.24,0,−85, computed ON the slant
  plane) hits at 0.00 mm. For a fillet face use an ON-SURFACE point = axis + R·dir
  (the R12.7 corner fillet at axis (0,50.8,−50.8): (0,59.78,−59.78)), not the
  bbox centre (~3.8 mm off the cylinder). `add_chamfer` now takes `face_points` +
  `tangent_propagation` and builds via `IFeatureManager.InsertFeatureChamfer`
  (options 0x4 = tangent prop, type 1 = swChamferAngleDistance, 45°) instead of
  the 3-arg `IModelDoc2.FeatureChamfer`, which can take neither faces nor
  propagation. With faces+prop the replayed `Chamfer2` matched source to +1 mm³.
- **Standalone external-part repros live in `cad/scripts/` but stay OFF the doit
  DAG**: add the script to `_buildgraph.NON_PART_SCRIPTS`, and note `verify.py`'s
  registry audit (`_declared_part_names`) now scans `_buildgraph.part_scripts()`
  (the canonical part-script set) so such repros are excluded from the
  `parts.yaml` "built but unregistered" audit exactly as from the graph.

- **Two cuts SHARING one sketch to leave a central WEB = ONE centred square +
  two Through-All cuts each with a `FromOffsetDistance` start-offset, opposite
  directions.** This is how `rocker-arm-support`'s Cut-Extrude3 AND
  Cut-Extrude4 both consume Sketch11 yet leave a 2×3.175 mm web (re-selecting
  the sketch by name for cut4 → `Sketch11<2>`). The web is NOT a gap in the
  sketch — the sketch is a SINGLE square; the web is the band between two cuts
  that each START 3.175 mm off the sketch plane. Probed source defs (the keys):
  Cut3 `ReverseDirection=False, FromOffsetReverse=True, FromOffsetDistance=3.175,
  T1=swEndCondThroughAll(1)`; Cut4 `ReverseDirection=True, FromOffsetReverse=
  False, FromOffsetDistance=3.175`; the cavity Cut2 `BothDirections=True` (reads
  back as `swEndCondThroughAllBoth=9`). Reproduce with RAW 27-param `FeatureCut4`
  (the "else" branch; 26-param major-33 throws "Parameter not optional") — the
  start tail is `…, T0, StartOffset, FlipStartOffset, OptimizeGeometry` where
  `T0=swStartOffset(3)`, `StartOffset=offset_m`, `FlipStartOffset=
  FromOffsetReverse`. Select the shared sketch by name (`SelectByID2(name,
  "SKETCH",…)`) before each cut. Draw the squares with the SW center-rectangle
  look (4 real sides + 2 construction diagonals) via `define_centered_rectangle`
  + `_add_construction_diagonals` (raw `CreateLine` with `ConstructionGeometry=
  True`, endpoints on corners so no DOF added), matching the source's 6-seg /
  1-contour sketches. Prototyped in `proto_shared_cut.py`; in `build_rocker_arm
  _support_manual.py` (`_cut_through_all`). This SUPERSEDES the earlier
  two-rectangle / contour-object `_cut_window` approach (PR #80, removed in
  #81): that was feature-tree-identical but its SKETCHES did not match the
  source (two rects on the Right plane vs one centred square on the Front
  plane). Volumes are byte-identical either way; only the sketch decomposition
  differs, so match the cut MECHANISM, not just the tree, when sketches matter.
- **Hole Wizard (HoleWzd) with N points = ONE feature, built single-point
  then multi-pointed via the placement sketch.** Sequence (live-proven,
  `_drill_tapped_holes`): `FeatureManager.CreateDefinition(25)` →
  `IWizardHoleFeatureData2.InitializeHole(genericType, std, fastenerType,
  size, endType)` (tap=4, ANSI-inch=0, through-next=2, size="9/16-12") → set
  ThreadClass/EndCondition/ThreadEndCondition → **select the drill FACE as an
  OBJECT** → `CreateFeature(data)` makes a 1-hole HoleWzd whose sub-features
  are a 1-pt placement sketch (ProfileFeature), a 6-pt profile sketch, and a
  CosmeticThread. Then EDIT the placement sketch: move the auto point to hole
  #0 with `ISketchPoint.SetCoords(sx,sy,sz)` and `SketchManager.CreatePoint`
  the rest, then `EditRebuild3`. Model→sketch coords via
  `placeSketch.ModelToSketchTransform` + `MathUtility.CreatePoint(pt)` +
  `MathPoint.MultiplyTransform(xform)` → `ArrayData[:3]`. **CRITICAL: pass
  the model point to `CreatePoint` as `VARIANT(pythoncom.VT_ARRAY|VT_R8,[x,y,z])`**
  — a bare Python list marshals to garbage (sx=sy=0). SetCoords (move auto
  pt) is cleaner than delete-then-add (ISketchPoint.Select4 errored). Through-
  next drills from the selected face's normal-opposite direction; correct
  face → exact source volume. Proven in `probe_hole_wizard.py`/`probe_foot_face.py`.
- **`SelectByID2(...,"FACE",x,y,z,...)` mis-resolves at a SHARED plane: a pick
  ON the foot bottom (Y=−88.9) returned the ±X trapezoid END faces (which also
  touch Y=−88.9), so the wizard drilled along X through the whole part (removed
  ~7× too much, 224660 vs 243665 mm³). Even the bottom-face CENTER (0,−88.9,0)
  picked the +X face — coordinate selection is unusable here.** Fix: ENUMERATE
  `body.GetFaces()`, keep the planar face with `Normal≈(0,−1,0)`, box minY on
  the target plane, and bbox spanning all hole (X,Z) points, then select that
  face OBJECT (`face.Select2(False,0)`). Generalises the earlier chamfer-FACE
  point-picking lesson: when multiple faces meet at the pick plane, select the
  face object found by enumeration, never by coordinate.

- **A point-to-origin distance dim LOCATING AN ARC CENTRE rejects ANY equation
  binding** (SW 2026, live-bisected on `build_pinion_bracket.py`): the sketch is
  fully defined and consistent, the equation's value equals the as-built dim
  (43 mm), `IEquationMgr.Add3` succeeds and the RHS evaluates — but the NEXT
  `ForceRebuild3` fails with only the **Equations folder** flagged in
  GetWhatsWrong (`('Equations', 1, False)`). A literal RHS (`= 43mm`) fails
  identically, so it's the DIM, not the global reference; the *same* dim shape
  on a circle centre (`ArborBoreCz`) takes `= "C2C"` fine, and radius dims on
  the same arc drive fine. Bisect method: monkeypatch `drive_dimension` to
  rebuild after EACH equation; on failure dump `whats_wrong` + walk
  `IEquationMgr` (`Equation(i)`/`Value(i)`; note `Status` is just the last
  successful index, not an error flag). Fix pattern: don't re-dimension what a
  constraint can say — the arc centre was concentric-by-intent with the arbor
  bore, so a point-point `coincident` (arc.center ↔ circle.center) replaced the
  `anchor_point_to_origin` + equation entirely. Same bug class as the
  magnifying-lever dome radius (don't drive an already-forced dim).

See [[solidworks-3dx-launch]] for session/launch rules.
