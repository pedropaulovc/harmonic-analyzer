---
name: config-dirty-on-activate
description: "engagement/operating/pinion configs are under-defined by design → activating them dirties the doc; NOT a determinism bug, no script change"
metadata: 
  node_type: memory
  type: project
  originSessionId: 045bacc1-f12e-48b0-b137-916b2b43a02d
---

harmonic-analyzer.SLDASM (and drive-train.SLDASM) open **CLEAN on Default**
(GetSaveFlag=False) — Default is the rendered, photo-gated, Pack-and-Go output
pose, so deterministic output is fine. Activating ANY of the 3 non-Default
engagement configs (`cone_disengaged`, `operating`, `pinion_engaged`) flips
GetSaveFlag=True and it stays dirty. This is **by design, not a bug**: those
configs are INTENTIONALLY under-defined (free DOF — cone_disengaged decouples the
42-member gear train; operating frees the crank; pinion_engaged frees the swing),
and SW re-solves the freed bodies on activation → dirty flag. The verify
isolation/engagement suites *assert* these freed-DOF sets, so a "configs must open
clean" gate would FALSE-FAIL.

**Proven inherent, not stale-save:** rebuilding+saving every config
(ShowConfiguration2 + ForceRebuild3 per config, then byref Save3) does NOT change
the activation-dirty behavior — identical before/after. So pre-rebuilding configs
is wasted build time; reverted.

The dirty doc the user saw after `cut_release` came from **SavePackAndGo**
iterating all configs to pack them (touches the under-defined configs → dirty);
the packed zip is a copy and is unaffected. A post-pack / under-defined-config
dirty doc left open makes a later `CloseAllDocuments(True)` pop the "Save Modified
Documents" modal in 3DX R2026x (hangs headless) → close-without-save / discard.

Diagnostics live in `cad/scripts/diagnostics/`: `probe_clean_open.py`
(close→open→GetPackAndGo→activate each config, read GetSaveFlag) and
`probe_dirty_on_open.py` (read-only attach to a live doc, per-doc GetSaveFlag +
What's Wrong via sw_type_info flagging). See [[dof-refactor]] (the under-defined
configs) and [[harmonic-analyzer-project]].
