---
name: chain-component-pattern
description: Native SW Chain Component Pattern — how the paper-drive roller chain is built (pywin32 FeatureChainPattern + closed-spline path); path must be a sketch SEGMENT not the sketch feature
metadata:
  type: reference
---

## SHIPPED 2026-07-05 — `_insert_roller_chain` now uses the native chain pattern

The paper-drive roller chain is now built by a native **connected-linkage chain
component pattern** (adapter method `pattern_components_chain` →
`IFeatureManager.FeatureChainPattern`), replacing the manual per-link placement.
Full `doit`/standalone build + `verify:soundness` pass (58 links, DOF pattern=56,
0 interference, model healthy). Diagnostic: `diagnostics/diag_chain_pattern.py`
(exercises `_insert_roller_chain` in a fresh assembly). The pywin32 recipe below
is the one implemented.

## RESOLVED 2026-07-05 — the feature works; the blocker was the path selection type

Earlier this memory concluded the Chain Component Pattern was unusable via API
(CreateFeature → None across ~14 pywin32 + early-bound C# runs). **That was wrong.**
A UI macro-recording (`Macro1.swp`) of the working feature revealed the real cause:

- **The PATH must be selected as the sketch SEGMENT** —
  `SelectByID2("Arc1@Sketch1", "EXTSKETCHSEGMENT", …, mark=2)` — NOT the sketch
  feature (`"Sketch1"`, `"SKETCH"`). Selecting the sketch feature yields an invalid
  definition, so `CreateFeature` silently returns null (no error from
  `GetCreateFeatureErrors`). This one thing caused every failure.
- With the segment path, the docs route works verbatim: pre-select segment(2) +
  component(1) + path-link axis(256) [+ link2 512 / group2 2048/4096/8192/32768 for
  linkage] + align plane(16384) → `fm.CreateDefinition(swFmLocalChainPattern=112)` →
  set `PitchMethod`/`AlignMethod`/`Options`/`InstanceCount`/`FillPath` → `CreateFeature`.
  Verified live: count-driven gave 20 instances, `FillPath=True` filled to 13.
- **The property GETTERS are unreliable pre-commit** (read back 0/False right after a
  valid set) — ignore them; the SETTER still applies at `CreateFeature`. This false
  signal is what made the earlier runs look like "PropPut doesn't stick".
- `IFeatureManager.FeatureChainPattern(PitchMethod, FlipDirection, FillPath, Number,
  Spacing, GroupOneFlipPlane, GroupTwoChain, GroupTwoFlipPlane, AlignMethod, Options)`
  is a dedicated one-call alternative to CreateDefinition/CreateFeature (untested for fill).
- `sw_type_info.early_bound` is NOT required — the path-selection type was the whole issue.
  In-process `gencache.EnsureModule`/`CastTo` on the SW TLB still WEDGES the seat; don't.

## pywin32 recipe (the one to ship) — use FeatureChainPattern, not CreateFeature

Verified end-to-end in pywin32 on the real loop (58 alternating links, connected linkage):

1. **Path = a single CLOSED segment.** Author the loop as one closed **spline**
   (`add_spline` through dense `loop_point_tangent` samples + closing point) — the
   3-arc+line contour is NOT connected (segments share coords but have no coincidence
   relations, so `MakeSketchChain` forms 0 paths / `GetSketchPathCount`=0). Select it as
   `EXTSKETCHSEGMENT` (`"Spline1@Sketch1"`, mark 2).
2. **`CreateDefinition`/`CreateFeature` returns null under pywin32** even with everything
   right (works in early-bound C#, not late-bound pywin32 — a marshaling quirk of the
   feature-data object). **Use the dedicated one-call method instead:**
   `IFeatureManager.FeatureChainPattern(PitchMethod, FlipDirection, FillPath, Number,
   Spacing, GroupOneFlipPlane, GroupTwoChain, GroupTwoFlipPlane, AlignMethod, Options)`.
   It consumes the pre-selection and returns the feature. Connected linkage =
   `PitchMethod=2`, `GroupTwoChain=True`, `FillPath=True`, `AlignMethod=1`(tangent),
   `Options=1`(dynamic).
3. **Selections (marks):** path `EXTSKETCHSEGMENT`(2); group1 inner comp(1) + pins
   `Axis1`(256)/`Axis2`(512) + `Front Plane`(16384); group2 outer comp(2048) + pins
   `Axis1`(4096)/`Axis2`(8192) + `Front Plane`(32768). Seeds placed tangent (chord) so
   both pins sit ~on the path.
4. Non-integer fit leaves a one-link seam at the seed — RESOLVED by quantising the
   LOOP, not the pitch: `_chain.py` keeps `LINK_PITCH` at the exact #25 standard
   (6.35) and solves the slack-run SAG so `CENTRELINE_LEN == LINK_COUNT * pitch`
   with an even count (54) — the sag absorbs the residual, like a real chain
   (2026-07-06; was 58 stretched-pitch links with a seam risk).

**How to apply:** the native chain pattern is viable for the paper-drive roller chain
(`_insert_roller_chain` can be replaced). Author the loop path sketch, select the loop
as EXTSKETCHSEGMENT(s), place inner+outer seeds, use connected linkage (two groups) for
the alternating chain. Toolchain for API spikes: `csc.exe` (.NET Framework 4.0 at
`C:\Windows\Microsoft.NET\Framework64\v4.0.30319`) + the Interop DLLs at
`…\SOLIDWORKS 3DEXPERIENCE R2026x\SOLIDWORKS\api\redist\` (copy next to the exe — not in
GAC); reflect DispIds/signatures by loading the DLL. Makers = SW Connected Professional
(full modeling; only simulation/Xpress removed), so assembly features are all present.

---

## Original (superseded) investigation notes

The paper-drive roller chain is placed link-by-link on purpose
(`build_paper_drive_assembly._insert_roller_chain`). The docstring's claim that
the native **Chain Component Pattern** "rejects raw-COM CreateFeature" was
retested exhaustively live (2026-07-05, probe
`cad/scripts/diagnostics/probe_chain_pattern.py`, ~14 runs) per
[[verify-assumptions-live-sw]]. Result: the native feature is **not usable through
this adapter** — but the mechanism is subtler than "CreateFeature always None".

**What blocks it, in layers:**
1. `IFeatureManager.CreateDefinition(swFmLocalChainPattern=112)` returns a bare
   untyped `<COMObject <unknown>>` because the adapter *forces late binding*
   (`win32com.client.dynamic` — early binding breaks `OpenDoc6` pass-by-ref; see
   the SolidworksMCP-python COM-threading notes). On the untyped object, property
   PUTs are unreliable and `CreateFeature` returns `None`.
2. **The fix for creation is `sw_type_info.early_bound(data,
   "IChainPatternFeatureData")`** — wraps the dispatch in its typed gen_py class
   (dispid invoke, no makepy regen). With it, `CreateFeature` DOES return a
   feature. (Do NOT use `win32com.CastTo` — *"can not automate the makepy
   process"* — nor in-process `gencache.EnsureModule`/`EnsureDispatch` on the SW
   TLB: that is a multi-minute regen that **wedged the seat**, Not Responding
   >11 GB. Recover only via Platform-shortcut relaunch, never COM cold-start.)
3. Post-create configuration also works once typed: the feature (also
   `early_bound(feat, "IFeature")` so `GetDefinition`/`ModifyDefinition` resolve)
   → `GetDefinition` → `AccessSelections(model, None)` → set `FillPath`/
   `InstanceCount` (now they STICK) → `ModifyDefinition` → returns True.
4. **BUT the pattern generates ZERO instances** — FillPath=True and explicit
   InstanceCount=20 both `ModifyDefinition->True` yet no link copies appear
   (visually confirmed: render shows the loop path + the two seeds only). And
   **connected linkage** (`PitchMethod=2`, the alternating inner/outer chain the
   roller chain actually needs) can't be set at all — it stays 0.
5. Extra quirk: the single-group distance `CreateFeature` only succeeds when a
   (failing) two-group connected-linkage attempt runs *first* in the same process
   — a non-deterministic priming dependency.

**Bottom line:** even fully typed, the chain pattern is a degenerate empty
feature here — no instances, no connected linkage. Not viable for the roller
chain. Keep `_insert_roller_chain` (explicit placement); it produces the correct
alternating chain deterministically. The parts carry `Axis1`/`Axis2` (documented
PathLink1/2) and `_chain.loop_segments` exists for the path sketch, so the design
*intended* the native feature — it's blocked by the COM binding + the feature not
propagating instances, not by geometry. Relates to [[no-untested-failure-assumptions]].
