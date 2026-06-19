---
name: tube-column-od-rederive
description: M6.11 — tube-frame column OD rederived from the ch30 8-views to Ø25.4 (1"), superseding legacy Ø1.375"; full cascade
metadata:
  type: project
---

**M6.11 (2026-06-19): tube-frame column OD rederived from the ch30 8-views → Ø25.4 mm (1"), superseding legacy Ø1.375" (Ø34.925, ~45% oversize, no book numeric).**

**Method (photogrammetry).** The 4 quarter views (p003/p005/p007/p009) resolve the frame into 4 *isolated single columns* — front/back/side views merge the same-x or same-z column pairs (~2° off-axis azimuths add ~11 mm of pair-offset) and are unreliable. Under the manifest's orthographic euler cameras a vertical cylinder's apparent width = OD × scale (isotropic, azimuth-independent). Per-view scale (px/mm) fit from the known corner stations (±197, ±112) + azimuth: `screen_x = scale·(x·cosA + z·sinA) + c`, R² 0.94–0.99. Cross-checked independently by the **460 mm base plate** = ~1500 px in the front view → 3.26 px/mm, matching the column-spacing scale and confirming the ±197 stations (back-solves 402 vs 394). 7 isolated-column silhouette reads (gradient edges vs black bg) = **Ø23.8 ± 1.0 mm**; base-scale variant ~24.7. Rounded to **1" stock** (1896 Gaertner machine = imperial tube). User chose 1"/25.4 + "cascade everything".

**Why it was wrong before:** legacy Ø1.375" was an eyeball from the no-longer-extant SLDPRT, never a book number. Pitfall confirmed: merged column blobs in front/back/side views read ~35 mm and *look* like they confirm the legacy value — they don't; only the quarter views isolate a true single column. Brightness-threshold over-reads width via specular glow; use gradient/low-T-vs-black silhouette.

**Cascade applied (4 geometry constants + docs):**
- `build_tube_frame.py` OUTER_DIA 1.375→1.0 in (wall kept legacy 0.12" → Ø19.3 bore; wall not view-derivable).
- `build_frame_assembly.py` COLUMN_RADIUS 1.375→1.0 in/2 (auto-moves the corner-bracket tangent placement BRACKET_X).
- `build_top_frame.py` BORE_DIA 35.0→25.5 (boss Ø48 unchanged).
- `build_column_clamp.py` COLLAR_BORE 35.2→25.6 (collar OD 48 + channel offset 21.9 to column CENTRE unchanged; channel now stands ~4 off the smaller column, back wall now 11.2 thick so the channel no longer opens into the bore — `_channel_removed_volume` adapts since seg(bore/2,16.8)=0).
- Clearances only LOOSEN (no part moved, doc numbers refreshed): fulcrum-shaft 182 tips clear by ~5.3 (was 0.6); support-bar 384 — columns z −99.3..−124.7 no longer reach the bar z-band (4.2 gap, old M6.5 corner-trim moot); pinion-bar SE tangent 184.3 (was 179.54); pinch-screws backed out further (wall 11.2); ball-mount boss-bore clearance need dz≥20.5 (was 25.3).
- Docs: cad/DIMENSIONS.md + cad/config/dimensions.yaml rows (tube-frame audit, top-frame, ball-mounts, support-bar, column-clamp, pinch-screws, pinion-bar, fulcrum) + the part docstrings.

Volume_check tolerances all derive from the constants → self-consistent, no hardcoded volumes to touch. **NOT yet SW-rebuilt** (agent session has no SW/GL) — run `doit` (deleting the affected .SLDPRT/.SLDASM targets to force full rebuilds) to validate the interference/DOF gates. Same family of re-anchor as [[od-62mm-reanchor]] (measure-from-photo supersedes legacy). See [[harmonic-analyzer-project]], [[solidworks-modeling-pitfalls]], [[comparison-camera-refinement]].
