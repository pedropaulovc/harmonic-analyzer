---
name: pose-studio-part-delta-fitting
description: How to extract model-improvement info from an aligned comparison pair — fit parts by hand in Blender pose_studio, export per-part deltas, map back to SolidWorks dims
metadata:
  type: project
---

Workflow to turn an *already-aligned* comparison pair (e.g. `ch30-p003`) into
concrete CAD edits ("resize the platen", "shift the magnifying wheel"). Added
2026-07-12, PR #276, branch `pose-studio-part-deltas`.

**Loop:** align model↔photo (camera pose, done) → move/resize individual parts
in Blender against the overlay → export the per-part transform deltas → map each
delta to a SolidWorks build-script edit.

- **Data:** `pose_studio.py` loads the analyzer PER-PART (`cad/out/boxes/<model>.json`
  scene graph + `cad/out/stl/*.STL`), each component a named, selectable Blender
  object. Stage from a release bundle when `cad/out` is empty: `gh release download
  <tag> -p "*.zip"`, extract `boxes/` + `stl/` → `cad/out/`, and the SLDASM →
  `cad/out/sldasm/harmonic-analyzer.SLDASM` (its presence gates the per-part branch
  vs a monolithic assembly mesh — the per-assembly export is now `gltf/<asm>.glb`, the mono STL is retired), and the prepared ref →
  `cad/comparisons/ref/<id>.jpg`. All gitignored.
- **Fit:** `uv run cad/comparisons/tools/pose_studio.py --pair ch30-p003` → N-panel →
  Build/Reload Scene. Native Blender `G` move / `S` resize on a selected part
  (constrain axis with X/Y/Z; resize with Pivot=Individual Origins so size doesn't
  leak into translation). **Part fitting → Export Part Deltas** writes moved parts
  (translate_mm / scale / rotate_deg, above ~0.5 mm floor) to
  `cad/comparisons/findings/<pair>_deltas.json`.
- **Map:** `uv run cad/comparisons/tools/map_deltas.py --pair <id>` (SolidWorks-free).
  RESIZE → `build_<stem>.py` dimension constants with confidence tags: `(low)`/
  photo-scaled = editable, `(high)` book-annotated = LOCKED (the *pose* is the
  suspect, not the geometry). SHIFT → the `build_*_assembly.py` that
  `place_component(adapter, "<stem>", …)`s it — no free offset knob, trace to an
  upstream driving dim; `verify:soundness` polices interference/DOF.

**Gotchas (why single-view fitting can fool you):**
- **Depth is unconstrained by one view.** Dragging a part to match `p003` fixes
  only its 2 image-plane axes; depth (toward/away camera) can be anywhere and still
  "look right" — worse here because the 68.4 mm lens (~13° FOV, near-telephoto) has
  almost no perspective depth cue. Mitigate: move along the machine's real axes, and
  re-check the fit in a near-orthogonal view (`p002` front / `p004` side) before
  editing.
- **Don't touch the camera while fitting parts** — nudging az/el/zoom "fixes"
  geometry error with camera error. Pose stays frozen. Uniform rescale of everything
  is degenerate with camera zoom (`align.scale` in composite.py is a global uniform
  scale + translate) — only relative part-to-part size/position survives as a real
  signal.
- **Rebuild before trusting a re-render.** `render_offline` reads the STL/boxes
  cache; after a build-script edit you must rebuild + re-export (or pull the next
  release) or you compare against stale geometry.

See [[comparison-pose-vision-first]], [[comparison-camera-refinement]],
[[pose-studio-camera-toggle]], [[default-free-dof-park-drivers]].
