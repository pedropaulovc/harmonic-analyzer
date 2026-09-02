---
name: meshprobe-usage
description: "meshprobe (Playwright-for-3D CLI) driving notes: needs Blender >= 5.2 (auto-discovered incl. Windows as of 1.2.0), glTF must be metres, view-orbit needs --projection-json, high_key illumination for CAD inspection"
metadata:
  type: reference
---

meshprobe (`uv run meshprobe`, pedropaulovc/meshprobe, 1.2.0) inspects/renders release
GLBs in durable sessions. Hard-won usage notes (2026-07-17, filed as issues #93–#102):

- **Blender ≥ 5.2 required** (worker calls `gpu.init()`, new in 5.2; 4.5/5.1 crash with
  AttributeError). As of 1.2.0 `open` **auto-discovers Blender on Windows too** — verified
  2026-07-20 by opening a GLB with no `--blender` (EXIT 0). The old "pass
  `--blender C:/Program Files/Blender Foundation/Blender 5.2/blender.exe`" was a 0.3.0
  limitation; `--blender` now only needed to OVERRIDE the discovered install.
- **glTF units are METRES** (spec). A mm-authored GLB reads as a 457 m machine with no
  warning — author GLBs in metres.
- Coordinate mapping (in the `open` receipt): glTF +X→world +X, +Y→+Z, +Z→−Y. Machine
  coords (Y up, front = −Z) → world = (x, −z, y); front view = azimuth 90°.
- `view-orbit` REQUIRES `--projection-json`, e.g.
  `{"mode":"perspective","focal_length_mm":100,"sensor_fit":"vertical","sensor_height_mm":23.6,"sensor_width_mm":15.8}`
  reproduces the book's DX + 100 mm camera; `--target` is world-space **mm**;
  `--aspect-ratio` must match render width/height by hand.
- Renders: keep meshprobe's DEFAULT `--style screen_edges` (GPU depth/normal edge pass).
  `--style shaded_edges` is Freestyle: crisper, geometry-aware, better at separating
  same-colour adjacent parts — but CPU-bound and single-threaded, and its cost scales
  with VISIBLE COMPONENT COUNT, not resolution. Full machine at 945x2240: screen_edges
  7.3 s vs shaded_edges 31.8 s (shaded, no edges, 6.8 s). Reserve Freestyle for final
  confirmation; the GPU is used either way (receipt: `device=graphics_hardware`,
  engine eevee, `renderer` = the actual card — a slow render is NOT a CPU fallback);
  `illumination-set high_key --background-rgb 1 1 1` for SW-exported PBR metals (they
  render near-black under the default preset).
- Session state lands in `.meshprobe/` under the workspace — **gitignored** since
  PR #339 (Codex caught it committed).
- Schema discovery: `meshprobe schema --kind commands` (no per-command lookup);
  invalid preset/enum values error with the valid list — cheap discovery trick.

- **"timed out" on `open` = a Blender importer error, not a slow import (2026-09-01):**
  the v31 whole-machine `harmonic-analyzer.glb` (105 MB, 2.2 M tris) imports in ~5 s
  once it is valid; it hung for the full worker timeout because the SolidWorks glTF
  exporter wrote two primitives (`harmonic-base-1`, `top-frame-1`) whose `TEXCOORD_0`
  count differs from `POSITION`, Blender's importer raises `IndexError: index 576 is
  out of bounds`, and meshprobe 1.2.0's worker glues its error JSON onto Blender's
  un-newlined traceback line so the controller never parses the reply
  (filed upstream: pedropaulovc/meshprobe). Fixes: `export_models.sanitize_glb` now
  strips such attributes at export time (every `.glb` through `_save_as`); for an
  already-exported bundle run the same function on the file. Local venv patch to
  `meshprobe/blender/worker.py::emit` (an empty `print()` before the JSON) makes a
  bad file fail in 6 s with the importer's message -- `uv sync` reverts it. Bare
  `meshprobe find *` gets shell-expanded: quote the pattern.
