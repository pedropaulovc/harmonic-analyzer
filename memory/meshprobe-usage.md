---
name: meshprobe-usage
description: "meshprobe (Playwright-for-3D CLI) driving notes: needs Blender >= 5.2 via --blender, glTF must be metres, view-orbit needs --projection-json, high_key illumination for CAD inspection"
metadata:
  type: reference
---

meshprobe (`uv run meshprobe`, pedropaulovc/meshprobe, 0.3.0) inspects/renders release
GLBs in durable sessions. Hard-won usage notes (2026-07-17, filed as issues #93–#102):

- **Blender ≥ 5.2 required** (worker calls `gpu.init()`, new in 5.2; 4.5/5.1 crash with
  AttributeError). Not auto-discovered on Windows — pass
  `--blender "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"` to `open`.
- **glTF units are METRES** (spec). A mm-authored GLB reads as a 457 m machine with no
  warning — author GLBs in metres.
- Coordinate mapping (in the `open` receipt): glTF +X→world +X, +Y→+Z, +Z→−Y. Machine
  coords (Y up, front = −Z) → world = (x, −z, y); front view = azimuth 90°.
- `view-orbit` REQUIRES `--projection-json`, e.g.
  `{"mode":"perspective","focal_length_mm":100,"sensor_fit":"vertical","sensor_height_mm":23.6,"sensor_width_mm":15.8}`
  reproduces the book's DX + 100 mm camera; `--target` is world-space **mm**;
  `--aspect-ratio` must match render width/height by hand.
- Renders: `render-image --style shaded_edges` (Freestyle) for crisp CAD edges;
  `illumination-set high_key --background-rgb 1 1 1` for SW-exported PBR metals (they
  render near-black under the default preset).
- Session state lands in `.meshprobe/` under the workspace — **gitignored** since
  PR #339 (Codex caught it committed).
- Schema discovery: `meshprobe schema --kind commands` (no per-command lookup);
  invalid preset/enum values error with the valid list — cheap discovery trick.
- **GPU TDR crash on heavy scenes (2026-07-20):** the current VM's GPU is an
  NVIDIA A10-4Q 4 GB vGPU slice (~2.3 GB already committed at idle). Rendering
  the full-machine ~105 MB GLB in Eevee exceeds the 2 s Windows TDR watchdog →
  nvlddmkm event 153, Blender dies 0xC0000409, session lost ("NVIDIA OpenGL
  Driver Error code: 7" dialog). No TdrDelay registry keys are set. Workaround:
  render small GLBs (subassembly exports like `crank-closeup-check.glb`) or
  `display --mode isolated` on a subtree before rendering; keep only one live
  session. Positive control: small GLBs render fine on the same session.
