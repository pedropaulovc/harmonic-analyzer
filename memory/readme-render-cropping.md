---
name: readme-render-cropping
description: "Refresh committed README CAD images with trim_renders.py after a release build; do not copy raw SolidWorks canvases"
metadata:
  type: workflow
---

README assembly renders are deliberately refreshed **after** the release from the
latest generated `cad/out/png/<assembly>/<assembly>_isometric.png` files. Use the
repository script rather than copying those 1600×1000 SolidWorks canvases directly:

```powershell
uv run python cad/scripts/trim_renders.py
```

`cad/scripts/trim_renders.py` owns the assembly-to-`cad/docs/images` mapping and crops
each render deterministically to its non-background content with a fixed padding.
Keeping this explicit and outside the doit graph prevents normal builds from dirtying
tracked README assets and blocking the release clean-tree preflight.

Engineering-drawing PNGs are full sheets, so they are not inputs to this crop script;
copy selected existing sheets into `cad/docs/images` unchanged. Visually inspect every
cropped assembly image and selected drawing before committing them.
