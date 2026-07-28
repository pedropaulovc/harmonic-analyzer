---
name: dimxpert-authoring-probe
description: "DimXpert PMI authoring WORKS on this Makers seat (datum + gtol + XML fill + save, all proven 2026-07-28 pm). The morning InsertDatum wedge was session state, NOT call shape — unreproducible on a fresh SolidWorks. early_bound now serves IDimXpert* via the aux-typelib registry in sw_type_info."
metadata:
  type: project
---

Probed 2026-07-28 (R2026x SP3.0 Makers seat). Repros committed:
`cad/scripts/diagnostics/probe_dimxpert_gtol.py` (Q1–Q5, full pass) and
`probe_dimxpert_authoring.py` (staged: read / auto / datum / datum-nolength /
gtol — one process per stage, safe→risky, so a wedge can't destroy earlier
evidence). Context: the drawing-purity audit's 125 `tolerance="..."` FCF
literals across 55 sheets. See [[dimxpert-block-tolerance]] (separate, dormant)
and [[drawing-spec-purity]].

**AUTHORING WORKS — full chain proven on the Makers seat:**

- Positive control: `AutoDimensionScheme` (default options) authors 3 features
  + 3 annotations on transgear-stub. Its `False` retval is a SOFT signal
  (partial scheme), not failure — judge by created evidence. NOT licence-gated.
- `InsertDatum` returns True in ~0.5 s (`Datum19@Plane1(A)`), with or without
  the official example's `DatumLength = 0.06`.
- `InsertGtol` works, and needs NO preceding datum for form controls.
- **Q4 fill**: `IDimXpertAnnotation.GetDisplayEntity` returns the display-side
  `IAnnotation` — the `IGtol` is one hop further via
  `IAnnotation::GetSpecificAnnotation` (None ⇒ PMI-only). Behind that hop the
  DimXpert-created Gtol is ALREADY current-format (`GetFormat()=2`,
  `GetFrameCount()=1`) and `IGtolFrame.SetSymbolXml` takes the same XML the
  drawings use, read-back verified. (Treating the display entity AS the IGtol
  was the probe bug behind the earlier "no frame" reads.)
- The part saves carrying the annotations. Still untested: sheet import via
  `IDrawingDoc::InsertModelAnnotations3` + DimXpert filter.

**The morning WEDGE was session state, not call shape.** `InsertDatum` hung
SolidWorks twice in one session; on a freshly launched SolidWorks the EXACT
original form (no DatumLength, same part/selector/VARIANT array) passes. Do
not fix call shapes for it — treat a recurrence as session health:
`_sw_lifecycle.force_recover()`. Classic [[negative-result-positive-control]]
and [[no-untested-failure-assumptions]] material: two self-authored failures
proved that session failed, not the API.

**Binding recipe — now IN THE LIB.** The DimXpert dispatches expose NO type
info (`GetTypeInfo` → "Invalid index"): `Dispatch()`/`CastTo()` silently fall
back late-bound and every property PUT is refused. The only working binding is
the makepy class from `swdimxpert.tlb` wrapped around the RAW `_oleobj_`.
`sw_type_info` (submodule, `pedro/dimxpert-early-binding`) now has an
auxiliary-typelib registry (`_AUX_TYPELIBS`): on an interface miss against the
vendored sldworks wrapper, it lazily locates the tlb next to sldworks.exe,
reads its version via `LoadTypeLib().GetLibAttr()` (never hard-coded),
`EnsureModule`s it (~0.1 s, gen_py cache) and serves strict early-bound
classes — so `_early_bound(obj, "IDimXpertPart")` just works everywhere.

**Enum sourcing:** `swDimXpertGtolType_e` and `swDimXpertFeatureSelectorOption_e`
are still ABSENT from the offline doc bundle (v3.11.0, which otherwise added
the swdimxpertapi examples) — read them off the installed tlb
(`_gtol_type_map`; CircularRunout=12 confirmed). Misc: `GetDimOption()`
defaults: `DatumLength=0.05`, `TextPosition`=uninitialized denormal garbage
(harmless, nobody sets it); XML-filled gtols keep DimXpert
`GetAppliedAnnotationCount()=0` (fill lives on the display annotation);
`DeleteAllTolerances` leaves count reads at -1.

**Consequence: PMI is proven authorable but still not on the drawing-purity
critical path** — the unit/drift hazards close entirely with the spec
relocation ([[drawing-spec-purity]]); sheet import is the one open question.
