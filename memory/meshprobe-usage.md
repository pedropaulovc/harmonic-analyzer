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

- **Worker timeout (2026-09-01):** `meshprobe open` on the 105 MB whole-machine
  `harmonic-analyzer.glb` dies with `Invalid value: timed out` -- the daemon's Blender
  worker has a hard-coded `DEFAULT_WORKER_TIMEOUT_SECONDS = 180` in
  `meshprobe/controller.py` (no env/CLI override; `client.py` derives its read timeout
  from it). Either patch that constant in `.venv` (session-local -- `uv sync` reverts
  it; then `meshprobe kill --all` so the daemon restarts) or, cheaper, open the
  per-subassembly GLBs from the release bundle (`pen.glb` 141 KB .. `channel.glb`
  69 MB) -- every part is in one of them. `meshprobe find` needs a PATTERN or
  `--name` (a bare `*` is expanded by the shell -- quote it).
