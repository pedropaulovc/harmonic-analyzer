---
name: dimxpert-authoring-probe
description: "DimXpert PMI authoring on this seat: the swdimxpert typelib IS reachable (makepy-generate it, wrap the RAW _oleobj_ — CastTo/Dispatch silently fall back to late binding), swDimXpertGtolType_e IS recoverable from the tlb (CircularRunout=12 confirmed), but IDimXpertPart.InsertDatum WEDGES SolidWorks reproducibly"
metadata:
  type: project
---

Probed 2026-07-28 (R2026x SP3.0 Makers seat), repro committed at
`cad/scripts/diagnostics/probe_dimxpert_gtol.py`. Context: the drawing-purity
audit found 125 `tolerance="..."` FCF literals across 55 sheets and asked
whether they could become model PMI instead. See [[dimxpert-block-tolerance]]
for the (separate, dormant) block-tolerance doc props.

**What WORKS — three binding facts, each a prerequisite for any PMI work:**

- `ext.DimXpertManager(config, True).DimXpertPart` resolves. The recon's
  "no makepy pass over `SolidWorks.Interop.swdimxpert`" blocker is REMOVED:
  `gencache.EnsureModule("{582D0D5B-FF58-42CD-8968-A8A001A52454}", 0, 34, 0)`
  generates the wrapper from the installed `swdimxpert.tlb` in ~0.1 s.
- **The DimXpert dispatches expose NO type info** (`GetTypeInfo` → "Invalid
  index"). So `win32com.client.Dispatch(obj)` and `CastTo(obj, "IDimXpertPart")`
  BOTH fall back to a late-bound `CDispatch` — silently for Dispatch, with
  "This COM object can not automate the makepy process" for CastTo — and every
  property PUT is then refused (`Property '<unknown>.FeatureSelectorOptions'
  can not be set`). The ONLY binding that works is constructing the generated
  class around the **raw** dispatch: `wrapper.IDimXpertPart(obj._oleobj_)`.
  Passing the CDispatch instead nests a dispatch in a dispatch
  (`AttributeError: DimXpertPart.InvokeTypes`).
- **`swDimXpertGtolType_e` is recoverable from `swdimxpert.tlb`** even though
  the offline API-doc bundle omits it entirely (`InsertGtol`'s only parameter
  cites an enum the bundle does not ship). comtypes `GetModule` yields all 14
  members: Straightness=0, Flatness=1, Circularity=2, Cylindricity=3,
  SurfaceProfile=4, LineProfile=5, Angularity=6, Perpendicularity=7,
  Parallelism=8, Position=9, Symmetry=10, Concentricity=11, **CircularRunout=12**,
  TotalRunout=13. (The audit's synthesizer rejected `CircularRunout = 12` as
  fabricated because it was unsourced *in the bundle*; the typelib confirms it.
  Same "read it off the tlb, don't guess" move `_drawing_common` uses for the
  undocumented detailing prefs.)

**What FAILS — `IDimXpertPart.InsertDatum` WEDGES the seat.** Reproduced twice:
the SLDWORKS window goes `IsHungAppWindow`, the scratch part is left open and
dirty, COM never returns, and only `_sw_lifecycle.force_recover()` (kill +
connector relaunch) recovers. Reproduced with `FeatureSelectorOptions` passed
BOTH as a bare Python list AND as an explicit `VT_ARRAY | VT_I4` VARIANT — so
the marshalling trap `com_variant.double_array` documents is NOT the cause.
Q3 (`InsertGtol`), Q4 (filling the frame) and Q5 (importing PMI onto a sheet)
are UNREACHED, not disproven.

**Untested deltas** (do these before any "PMI is dead" verdict): `InsertGtol`
with NO preceding `InsertDatum` (a form control needs no datum, so the wedge may
be datum-specific); `swDimXpertFeatureSelectorOption_Default = -1` instead of
`_Plane = 0`; `SelectByID2` instead of `IEntity::Select4`; `AutoDimensionScheme`
as a **positive control** that ANY DimXpert authoring works on a Makers seat;
a non-Makers licence; the VBA path the API example is written for. Without a
positive control, "InsertDatum is broken" and "DimXpert authoring is unavailable
on this licence tier" are indistinguishable — see
[[negative-result-positive-control]].

**Also note:** `IDimXpertTolerance.Tolerance`, `GetPrimaryDatums`,
`GetMaxTolerance`, `Modifier`, `ZoneType` and `IDimXpertDatum.Identifier` are
ALL get-only. The DimXpert tolerance surface is a READ surface; the only
documented write is `InsertGtol` (creates an empty symbol defaulting to 0.02)
followed by `IGtol::SetFrameSymbols2`/`SetFrameValues2`, which are marked
"valid only if this Gtol was created in a version earlier than 2022". That note
means OLD-FORMAT-only, not removed: `_drawing_common.add_feature_control_frame`
already uses exactly that pair to SEED an old-format frame before
`ConvertFormat()`, so both halves of the fill recipe exist and are proven — on
the DRAWING side.

**Consequence: PMI is not on the critical path.** The unit/drift hazards the
audit found are fully closed by moving values into `*_spec.py` / `_fit_limits` /
`_surface_finish` and keeping the existing drawing-side authoring. See
[[drawing-spec-purity]].
