---
name: headless-render-no-gl
description: "VTK/pyvista offscreen render on the no-GPU Windows agent session — the REAL fix is Mesa <=25.0.x osmesa.dll + VTK 9.4 runtime GL selection (osmesa_win.py); matplotlib render_diff_mpl.py is the legacy fallback"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 3c39398b-16df-4061-9266-78d730d18647
---

This Windows agent session has **no usable GPU OpenGL** for offscreen rendering.
pip `vtk`/`pyvista` offscreen fails (`wglChoosePixelFormatARB` → falls back to
`vtkOSOpenGLRenderWindow`, which wants `osmesa.dll`). Mesa's `opengl32.dll`
(software WGL/llvmpipe) **can't override** the system one — `opengl32.dll` is a
Windows **KnownDLL**, force-loaded from System32 regardless of app-dir/PATH.

**REAL FIX (proven 2026-06-19, VTK 9.6.2):** VTK ≥ 9.4 does *runtime* OpenGL
window selection and falls back to an **OSMesa software render window** — on
Windows it just needs `osmesa.dll` on the DLL search path (Kitware's own guidance:
discourse.vtk.org "Status Update: Runtime OpenGL render window selection in VTK").
The earlier "osmesa.dll is a dead end" conclusion was WRONG — it only checked Mesa
**26.x / 25.1.0+**, which **removed** standalone `osmesa.dll`. Mesa **≤ 25.0.x**
still ships a **self-contained** `osmesa.dll` (x64, gallium+llvmpipe baked in — no
sibling DLLs needed, ~55 MB). Pinned: **pal1000/mesa-dist-win 25.0.7**
`mesa3d-25.0.7-release-msvc.7z` → `x64/osmesa.dll`.

`cad/comparisons/tools/osmesa_win.py` automates it: `enable_offscreen_gl()` (call
BEFORE `import vtk`/`pyvista`) fetches that DLL on demand into a gitignored cache
(`cad/comparisons/tools/.osmesa-cache/`), `os.add_dll_directory`s it, and sets
`VTK_DEFAULT_OPENGL_WINDOW=vtkOSOpenGLRenderWindow`. `render_diff.py` wires it in
before its pyvista import, so the **release-diff render now works headless** (no
matplotlib needed). Gotcha: Mesa's `.7z` uses the **BCJ2** filter that `py7zr`
can't decode — extract with the official standalone `7zr.exe` (osmesa_win.py
downloads it). `cut_release.py`'s `render_diff()` is now **fatal** — a failed diff
render blocks the release instead of shipping an empty `diff/` folder.

**Legacy fallback (no longer needed, kept for reference):**
`cad/comparisons/tools/render_diff_mpl.py` — pure matplotlib Agg, no GL. Renders the
scene graph (`cad/out/boxes/harmonic-analyzer.json` + STLs): changed base parts as
RED geometry, rest as grey bbox wireframe, 4 ortho views. Colors ALL instances of
a changed base part (over-inclusive vs render_diff's per-config classification).

Note the release-diff **classification** (`render_diff.py`, CRC + Hausdorff)
always ran fine; only its **VTK rendering** was blocked, and that's now fixed.
See [[incremental-builds-validation]], [[comparison-camera-refinement]] (GPU box
renders fine; this is the no-GPU agent session limitation).
