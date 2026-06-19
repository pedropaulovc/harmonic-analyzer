---
name: headless-render-no-gl
description: "VTK/pyvista can't get an OpenGL context in the agent session; use the matplotlib render_diff_mpl fallback (no GL) instead of chasing mesa/osmesa"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 3c39398b-16df-4061-9266-78d730d18647
---

This Windows agent session has **no usable OpenGL** for offscreen rendering, and the
modern-mesa workarounds are dead ends — don't re-walk them:

- pip `vtk`/`pyvista` offscreen fails: `wglChoosePixelFormatARB` → falls back to
  `vtkOSOpenGLRenderWindow` which wants `osmesa.dll`.
- Mesa's `opengl32.dll` (software WGL/llvmpipe) **can't override** the system one:
  `opengl32.dll` is a Windows **KnownDLL**, force-loaded from System32 regardless of
  app-dir/PATH placement.
- `osmesa.dll` is NOT shipped by modern mesa anymore: mesa-dist-win 26.x (release-msvc)
  AND conda-forge `mesalib` 26.x both ship only `opengl32.dll` + `libgallium_wgl.dll`,
  no standalone `osmesa.dll`. So VTK's OSMesa path can't be satisfied either.

**Working fallback:** `comparisons/tools/render_diff_mpl.py` — pure matplotlib Agg, no
GL at all. Renders the scene graph (`cad/out/boxes/harmonic-analyzer.json` + STLs):
changed base parts as real RED geometry, the rest as light-grey bbox wireframe context,
4 ortho views. Run with `.render-venv/Scripts/python.exe` (persistent venv with
pyvista/trimesh/matplotlib/scipy; gitignored). It colors ALL instances of a changed
base part (slightly over-inclusive vs render_diff's per-config classification).

Pair it with the **real SW renders** the build emits — `cad/out/png/harmonic-analyzer/{front,isometric,top}.png` — for actual shaded fidelity. The release-diff CLASSIFICATION
(`comparisons/tools/render_diff.py`) runs fine; only its VTK rendering needs the fallback.
See [[incremental-builds-validation]], [[comparison-camera-refinement]] (GPU box renders
fine; this is the no-GPU agent session limitation).
