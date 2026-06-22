# Parametric self-naming conversion spec (TEMP — deleted before commit)

Convert a `build_<part>.py` to the **full-parametric self-naming** pattern.
**GEOMETRY-NEUTRAL**: do NOT change any coordinate, dimension value, plane, or
build logic. Only ADD: (a) editable equation-manager globals, (b) named
sketches/features, (c) recorded+named+driven dimensions, (d) a deferred drive
batch + a neutrality re-check.

## HARD RULES
- **Do NOT run SolidWorks or execute any `build_*.py`.** There is ONE shared SW
  seat owned by the orchestrator. You may ONLY edit files and run
  `uv run python -m py_compile <file>`. The orchestrator validates on the seat.
- Compile MUST pass for every file you touch.

## Read first (proven, validated exemplars)
- `cad/scripts/build_top_frame.py` — canonical: circles + centered rectangles,
  multi-sketch, globals + deferred driving + neutrality.
- `cad/scripts/build_support_bar.py` — single centered rectangle.
- `cad/scripts/build_crank_pin.py` — revolve; manual `add_sketch_dimension` dims
  recorded after each call.
- `cad/scripts/build_hex_bolt.py` — polygon chain + on-axis circle.
- Helper signatures/docstrings in `cad/scripts/_common.py`: `SketchDims`,
  `define_circle`, `define_centered_rectangle`, `define_rectilinear_chain`,
  `define_polygon_chain`, `name_last_feature`, `set_global`, `drive_dimension`,
  `force_rebuild` (async — must be awaited), `volume_check`.

## The pattern (mirror the exemplars exactly)
1. Imports: add `SketchDims, name_last_feature, set_global, drive_dimension,
   force_rebuild, volume_check` from `_common`; drop imports you no longer use.
2. After `create_part`: declare globals for the part's module-scope design
   constants. **Every length MUST carry `mm`**:
   `await set_global(adapter, "Name", f"{CONST}mm")` — this is an INCH document;
   a bare number evaluates as inches and blows the part up 25.4x. Derived globals
   reference others as equation strings, e.g.
   `await set_global(adapter, "OuterX", '"ColX" + "W" / 2')`.
3. `drive_jobs: list[tuple[str, str]] = []`
4. Per sketch:
   - `sd = SketchDims()` before `create_sketch`.
   - Pass `dims=sd` + `names=`/`drives=` into the `define_*` helper (recording
     rules below). For any manual `add_sketch_dimension`, call
     `sd.record(name, drive)` immediately after EACH one, in order.
   - After `exit_sketch`: `name_last_feature(adapter, "ProfileName")` then
     `drive_jobs += sd.apply(adapter, "ProfileName")`.
   - After the feature (extrude/cut/revolve): `name_last_feature(adapter, "FeatureName")`.
5. Keep all existing `volume_check` calls unchanged.
6. At the very end, before material/save:
   ```python
   await force_rebuild(adapter)
   for dim_name, expr in drive_jobs:
       await drive_dimension(adapter, dim_name, expr)
   await force_rebuild(adapter)
   await volume_check(adapter, "driven <part> (equations neutral)", <same expected as last check>, <same tol>)
   ```

## Recording rules (names/drives align to dim EMISSION ORDER)
`SketchDims.apply()` count-asserts the recorded total vs the feature's real
display-dim count and FAILS LOUD on mismatch — that is your safety net, so if
you are unsure of a count, record your best guess and the orchestrator's build
will tell you.

- `define_circle(..., dims=sd, names=(cx, cz, dia), drives=(dx, dz, ddia))`:
  emits a centre dim ONLY for each non-zero coord (x dim if x≠0; z dim if y≠0),
  THEN the diameter. On-axis/origin circles record fewer than 3 — provide all 3
  names anyway; unused are ignored.
- `define_centered_rectangle(..., dims=sd, name_width=, drive_width=, name_depth=,
  drive_depth=, name_corner=(x,z), drive_corner=(x,z))`: exactly 4 dims (width,
  depth, cornerX, cornerZ). Use for ANY origin-centred rectangle (corner at
  `(-half_x, -half_z)`). `drive_corner` values are the half-spans (e.g. `'"W" / 2'`).
  **If a part currently builds an origin-centred rectangle via
  `add_line_chain` + `define_rectilinear_chain`, switch it to
  `define_centered_rectangle`** (cleaner; see support-bar).
- `define_rectilinear_chain(..., dims=sd, names=[...], drives=[...])`: names/drives
  align to emission order = the per-segment distance dims in line order SKIPPING
  the last segment of each direction (closure supplies it), THEN the anchor dims
  (x if anchor x≠0, then z if anchor z≠0). Unnamed slots → `None`.
- `define_polygon_chain(..., dims=sd, names=[...], drives=[...])`: emission =
  anchor dims first (x then z, non-zero only), THEN each kept segment's offset
  dims in line order (horizontal then vertical per general segment; one for an
  axis-aligned segment; the segment ending at the anchor vertex is skipped).

## Driving rules
- Length globals get `mm`; equations reference globals as `"GlobalName"`.
- For a derived/trig dim, drive by a DIMENSIONLESS coefficient times a global:
  `f'"Dia" * {coeff!r}'` (see hex-bolt) — unit-safe, avoids SW `sqr()` syntax.
- **Centre/anchor coordinate dims are UNSIGNED distances from the origin.** A
  dim for a point at a NEGATIVE coordinate displays as the magnitude, so its
  driving expression MUST evaluate POSITIVE. If the global holds the signed
  coordinate (e.g. `ScrewHoleX = -97.5mm`), negate it in the drive:
  `'-"ScrewHoleX"'`. Driving such a dim to a negative value fails LOUD at
  equation-add (`Failed to add equation`). Same for any derived span that lands
  negative — wrap so the expression is positive.
- If a dim has no meaningful global knob, leave its name/drive `None`
  (auto-named, static). That is acceptable.
- **Extrude/cut DEPTH is a feature parameter, not a sketch dim** — it will NOT be
  in `drive_jobs`. You may still declare a global for its constant (editable
  knob) even though nothing drives it; that's fine and matches the exemplars.

## Choosing globals
Expose the module-scope CONSTANTS (the commented values at the top of the file)
as the editable knobs; drive the sketch dims that equal them or simple functions
of them. Derived spans → derived globals.

## Report back (concise)
Per part: globals added, sketch/feature names, any dim left `None` + why, and
confirm `py_compile` passed.
