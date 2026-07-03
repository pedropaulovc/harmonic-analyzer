---
name: dxf-import-makers-seat
description: DXF import on the SW 3DEXPERIENCE Makers seat ignores SetPosition+SetSheetScale (bake into file); buffer line-art strokes into closed ribbons to cut
metadata:
  type: reference
---

Two hard, verified facts about `adapter.import_dxf_dwg`
(`IFeatureManager::InsertDwgOrDxfFile2`) on THIS SolidWorks 2026 3DEXPERIENCE
"for Makers" seat, found debugging the nameplate engraving (PR #143):

1. **The import's placement controls are NO-OPS here — bake scale AND position
   into the DXF.** `IImportDxfDwgData::SetPosition` returns `True` but never
   translates (tested mode 1 `swDwgEntitiesCentered` AND mode 2
   `swDwgEntitiesSpecifyPosition`, and reordered last). For a **flat modelspace
   DXF** `SetSheetScale` is ALSO a no-op — the artwork lands at 1:1 native mm
   regardless of the `scale`/`position` passed (rendered proof: an 88 mm target
   imported at ~280 mm, only the left third on the plate). (An earlier note that
   "SetSheetScale works" was from a blocks/INSERT DXF; it does NOT carry to flat
   modelspace.) Edition-agnostic fix: **author the DXF at FINAL plate-mm** — scale
   + centre the geometry offline so it already spans the target width on the plate
   centre, then import at `scale=1.0, position=(0,0)`. `test_nameplate_geometry`'s
   golden width then equals the plate footprint (88 mm), and `build_nameplate`'s
   `ENGRAVING_SCALE`→1.0 / `ENGRAVING_POSITION`→(0,0) act as swap guards.
   `GetPosition`/`GetSheetScale` getters raise "Parameter not optional" (byref
   out-params under late binding) — unrelated red herring.

2. **Traced line-art has no closed cut regions — buffer each stroke into a closed
   ribbon.** The raw engraving (46 SPLINE + 3 ELLIPSE + 8 LWPOLYLINE open strokes,
   hollow outline letters) imports and renders but cuts NOTHING —
   `create_cut_extrude`/boss both return None (no closed profile); no
   `merge_distance` (0.002–0.5 mm) helps. The 39 HATCH entities are the NEGATIVE
   field (background, letters as islands), not the ink. **Solution that shipped
   (PR #143):** offline, resolve the nested INSERTs (ezdxf `virtual_entities`,
   recurse), buffer every stroke into a thin ~0.4 mm closed ribbon and `unary_union`
   them (shapely), then scale+centre to final plate-mm and emit as ~112 closed
   modelspace LWPOLYLINEs. SolidWorks then forms regions and the cut removes real
   material (~210 mm³), reproducing the outline artwork faithfully as grooves. The
   generator is the one-off scratchpad `generate_cut_dxf.py`; git history keeps the
   original spline trace. See [[solidworks-3dx-launch]] and
   [[solidworks-modeling-pitfalls]].
