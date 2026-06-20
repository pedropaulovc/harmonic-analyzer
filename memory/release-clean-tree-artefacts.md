---
name: release-clean-tree-artefacts
description: cut_release.py needs a clean tree, but the build regenerates tracked artefacts (docs/images + BOM) — commit them first
metadata:
  type: project
---

`doit release` (cut_release.py preflight) aborts if `git status --porcelain --untracked-files=no` is non-empty (`--allow-dirty` overrides, but then the release ships marked DIRTY). The catch: the `doit` build spine itself regenerates **tracked** artefacts every time it rebuilds the assemblies — `docs/images/{frame,drive-train,channel,output,hero}.png` (via `save_assembly_and_images` → `trim_renders.trim_readme_render`) and `cad/out/harmonic-analyzer-bom.csv` (via `build_harmonic_analyzer_assembly.export_gallery_and_bom`). So any model change that you merge MUST also commit the regenerated renders + BOM, or the very next release fails on a dirty tree.

**Why:** these artefacts are README images + the parts BOM; the repo tracks them, and the tag is supposed to pin a tree consistent with the shipped bundle.

**How to apply:** when landing a model change, regenerate and commit the artefacts in the SAME (or an immediate follow-up) PR:
- `docs/images`: `python cad/scripts/trim_renders.py` — instant, no SolidWorks, deterministic crop from the still-fresh `cad/out/png/<asm>/<asm>_isometric.png` (gitignored, survives `git reset`).
- BOM: `python cad/scripts/refresh_assembly.py harmonic-analyzer` — reopens the top assembly, runs gates, re-exports the BOM (~280 s, needs SW open).
Both outputs are deterministic, so once committed the next build cache-hits them and the tree stays clean. Direct push to `main` is blocked by the permission classifier — always route via a feature branch + PR + `gh pr merge --auto --merge`. See [[mm-normalization-render-bundle]].
