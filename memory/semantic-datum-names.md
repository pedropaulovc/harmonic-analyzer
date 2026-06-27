---
name: semantic-datum-names
description: Reference datums/planes/axes added to parts must get human-readable semantic names, not SW auto-names
metadata:
  type: feedback
---

When adding reference geometry (datum planes, axes) to SolidWorks parts, give each a
human-readable **semantic name** describing its role (e.g. `seat_cyl00`, `base_top`,
`crankshaft_axial_seat`, `post_swing_x`) — never rely on SolidWorks' auto-names
(`Plane1`, `Axis2`, …).

**Why:** auto-names are order-dependent and opaque; the assembly script selects datums by
`named_ref("<name>@<part>", "PLANE")`, so a stable, legible name makes the mate tree
readable and immune to feature-reorder churn.

**How to apply:** the adapter's `create_plane`/`create_axis` only auto-name, so pair them
with a `rename_feature` step (`IModelDoc2.FeatureByName(old).Name = new`). Use a helper like
`name_ref_plane(adapter, base, offset, name)` (mirrors `name_bore_axis` in
`cad/scripts/_common.py`). Related: [[harmonic-analyzer-project-decisions]].
