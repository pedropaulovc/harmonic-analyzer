---
name: per-config-stl-export-race
description: "Per-config neutral STL export captured the PRIOR config's geometry — SolidWorks regenerates config switches LAZILY, so ShowConfiguration2 then immediate SaveAs3 (no rebuild) shipped a multi-config part's STL holding an adjacent configuration. Fix: ForceRebuild3(False)+EditRebuild3() after the switch + a fail-loud distinct-CRC guard."
metadata:
  node_type: memory
  type: project
  originSessionId: 86222888-efe3-4a2b-8220-a86f1509aa3a
---

Multi-config parts (`cone-gear` ×20 tooth counts, `transgear-removable` ×3:
T12/T18/T24) ship **one neutral STL per configuration**. Both export paths —
`export_models.export_part_stls` and `cut_release.export_neutral` — switched
configs with `doc.ShowConfiguration2(cfg)` then **immediately** `SaveAs3`'d the
mesh with **no rebuild between**. SolidWorks regenerates config switches
**LAZILY** (same root cause documented in `build_cone_gear.py` for the 20-config
gear), so `SaveAs3` captured the *previous* config's still-tessellated solid. A
config's STL **non-deterministically held an adjacent configuration**.

Caught diffing v0.5.1 vs v0.5.0 — the SAME race hit a DIFFERENT config each
release (timing-dependent): v0.5.0 shipped `transgear-removable--t24.STL` with
18-tooth geometry; v0.5.1 shipped `--t18.STL` with 12-tooth geometry. **Master
CAD was always correct** — the `.SLDPRT` configs pass the in-SW `expected_volume`
gate and assemblies use the right config; only the **bundled per-config neutral
STLs** were mislabelled. Pre-existing, NOT a regression from the PR #33 pipeline
refactor.

**Fix (commit 83d6ad6, PR #40, branch `fix/per-config-export-rebuild-race`,
v0.5.2):** after each config switch and BEFORE `SaveAs3`, force
`doc.ForceRebuild3(False)` + `doc.EditRebuild3()` (mirrors `build_cone_gear`'s
proven remedy). Plus a fail-loud guard — `assert_configs_distinct` (export_models)
/ `_assert_configs_distinct` (cut_release): two configs of a multi-config part
producing byte-identical STLs is impossible by design (tooth counts differ), so it
raises rather than ship a stale mesh.

Validated with two `export_models.py --force` runs: guard passes; transgear outer
radii **14.08 / 20.08 / 26.05 mm** = the 14:20:26 (N+2) ratio for 12/18/24 teeth
(was 14/13.3/26 buggy); all 23 per-config STLs **byte-identical across both runs**
(deterministic). **Perf:** the `ForceRebuild3` of each gear config costs ~3.0–4.1 s
(vs ~0.4 s for `SaveAs3` alone) → **~70 s added to the export step only** across 23
configs; **zero** added to part/assembly builds or any `verify:*` gate (single-config
parts never enter the loop). The ~3 s is the gear gap-pattern rebuild itself —
skipping it *is* the bug.

v0.5.1 stays published (user: keep, fix forward). See [[mm-normalization-render-ready-release]],
[[headless-render-no-gl]] (the render-diff that surfaced this).
