---
name: helical-gear-lib-followup
description: Follow-up idea (user, 2026-07-14) — replace the K-slice linearized helix cut with library-generated true helical gear geometry (e.g. thingiverse 2854963)
metadata:
  type: project
---

User suggestion (2026-07-14, during the crank-mesh rederive): later consider
using library code to generate helical gear geometry instead of the K=12
stacked rotated slice cuts in `_gear.build_fixed_gear` — reference:
https://www.thingiverse.com/thing:2854963 ("Public Domain Involute
Parameterized Gears: Powered Up" by TrinaryLogic — OpenSCAD `gear()`/`rack()`
with helical, inner, and partial gears; an update of @3dexplorer's
public-domain involute library with @zkarcher's optimizations). Second
source (user, 2026-07-14):
https://hackaday.io/project/163953-crossed-helical-gears-in-openscad —
crossed-helical gears specifically (the exact pair class of this crank
mesh: helix angles summing to the shaft crossing angle, point-contact
screw mesh), useful for the theory/derivation side alongside the library
code.

**Why:** the shipped linearized-helix 64T ([[crank-mesh-crossed-helical]]) is
a K-slice approximation — each slice's teeth are straight, only rotated; a
true helix would remove the slice-quantization facets and could tighten the
backlash/slack margins the study reserves for them.

**How to apply:** porting the involute math is straightforward (the repo's
`gear_facts` already has the involute profile); the SolidWorks-native path
would be a swept cut along a helix (`create_helix` + sweep with twist) or a
loft between the per-face profiles instead of K plane-offset slice cuts.
Re-arbitrate any change with `diagnostics/crossed_mesh_study.py` (drop the
`slices` quantization there to model the continuous helix, i.e.
`slices=0`). Not urgent: the K=12 cut passed its volume gate and the
zero-collision phase sweep on 2026-07-14.

**Attribution (user requirement, 2026-07-14):** if any library code (or a
port of its math/structure) is used, provide proper attribution — credit the
authors (TrinaryLogic, building on @3dexplorer and @zkarcher) + source URL in
the adapted file's docstring and the repo's attribution record (the
comparison gallery's `ATTRIBUTION.md` is the existing precedent for crediting
third-party material). License verified 2026-07-14 (Firecrawl on the live
page): Creative Commons **Public Domain Dedication (CC0)** — no copyleft
concern; attribution is our own courtesy standard, not a license demand.
(Do NOT confuse it with janssen86's GPL OpenSCAD gear library — an earlier
note here made exactly that mistake.)
