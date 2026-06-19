---
name: part-d-custom-properties
description: "Part D DONE — parts.yaml registry → SW custom properties via raw COM, tolerance audit gate, validated live"
metadata: 
  node_type: memory
  type: project
  originSessionId: 045bacc1-f12e-48b0-b137-916b2b43a02d
---

Part D of the professionalize-cad plan is COMPLETE (committed fd3431c on branch `professionalize-cad`).

- **Source of truth:** `cad/config/parts.yaml` — 77-part registry (was 85 at validation; 8 alignment-pinion parts deleted 2026-06-18, commit c1ebca3 — see [[od-62mm-reanchor]]) (number MHA-###, material, tolerance_class, fit_class, process, confidence), merged over a `defaults:` block. `_config.parts(stem)` returns the merged record.
- **Writer:** `_common.apply_custom_properties(adapter, props)` drives raw COM `IModelDocExtension.CustomPropertyManager("").Add3(name, 30, value, 2)` (swCustomInfoText, swCustomPropertyReplaceValue) — the PyWin32 adapter has NO property writer — then reads back via `model.GetCustomInfoValue("", name)` and raises on mismatch. `part_properties(part_name)` builds the dict (Title + Generator + registry fields); Generator = `harmonic-analyzer @ {git short sha}{-dirty}` (NO wall-clock — determinism decision). Wired into `save_part_and_images` (re-save after writing).
- **VALIDATED LIVE** 2026-06-15: opened cone-gear.SLDPRT, wrote 9 props, saved, reopened from disk, all 9 read back identical. The raw-COM Add3 path persists correctly.
- **Audit:** `verify.py --suite config` includes the tolerance audit (handoff §14.2 Gate E) — reconciles registry vs the `PART_NAME = "..."` each build_*.py declares (`_declared_part_names()` regex-scans source, no SW needed), asserts material/tolerance_class/process present + class names resolve in tolerances.yaml, emits `cad/out/reports/tolerance_audit.csv` (gitignored). Config suite 14/14 green (11/11 at validation; amplitude-preset gates added since — see [[professionalize-plan-status]] F3).
- Every moving part references a fit via its per-part `fit_class` (stamped as "Fit Class" property) — chose part-level metadata over per-mate annotation (mates aren't addressable metadata carriers).

Remaining plan work: Part F (testability suite + engage/disengage config enums) — see [[harmonic-analyzer-project]], dof-refactor (dropped memory).
