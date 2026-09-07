# Owned source-prefix positive control

The owned native control passed at `5e773756`; no save, cold-reopen or printed
acceptance is claimed. The fix originated as
`271f80b27196dcc8580d912d614780f1e3a44c77` and corrects
`_drawing_marks.set_dimension_prefix`: `IDisplayDimension.SetText` is void,
so success is its exact `GetText(1)` readback, not a Boolean return. Its old
telemetry fixture invented `True`; the corrected fixture keeps the span
assertion and supplies the actual void shape. No production caller exists.

The correction was replayed as `96679c5f` on `fc13a85b`, then integrated as
`f02d9f47`; the diagnostic was integrated as `5e773756`. Despite no
callers, `_drawing_marks.py` content is an input to 86 of 108 current part
helper closures (parent's read-only graph audit). Its integration therefore
still requires the final affected-part/full-stack build; prior native recipe
acceptance does not cover its changed digests. This small native control is not
an exemption from that build gate.

## Native result: immediate and redraw readbacks

The frozen `5e7737560d1efba42ff03d75376565e3b4710962` run passed on the
serialized native seat. Retained evidence under `cad/out/reports/`:

- `dimension-prefix-jv_856cn/prefix.json`, SHA-256
  `782de3c7589ed3d6b939c7984f9f46a34a02638b763df3cc21ffffae5eaee282`.
- `dimension-prefix-jv_856cn/ownership.json`, SHA-256
  `6d121b52ca4debb7b42c376a03d6118809bdb61e0343d072d1b0bd74f04197f5`.

The real helper returned `None` in **1.3740676 s**. On
`BodyDiaDim@BodyProfile`, only GetText fields 1 and 5 changed, from
`<MOD-DIAM>` to `PREFIX CONTROL ` (including its trailing space). Fields 3 and
7 retained `5/16-18 UNC-2A`; 2/4/6/8 stayed empty. `ShowDimensionValue` stayed
`True`. The complete immediate and post-redraw banks were identical. All five
observed source dimension names, values, tolerance types/BASIC designations and
the `Default` configuration stayed exact; every same-session dimension identity
readback was integer 1. The copy's dirty flags remained `False`, including
before/after every getter bank; text changed without an observed dirty flag.

Original and copied disk bytes retained the pinned `f3578ac2...48468` SHA below
at copy, before close and after close. Cleanup closed only the owned copy and
preserved the original visible, clean cone-tip part that was already open.
The receipt has no errors; ownership reports no probe or cleanup error and
`baseline_preservation.status = preserved`. Imported adapter/helper fingerprints
were guarded. No source save, drawing import, cold reopen, PDF/PNG export or
full geometry proof occurred: this proves the corrected void-call/readback
contract in one native PART, not persistence or printed output.

## Exact control

`diagnostics/probe_dimension_prefix.py` opens only a unique-basename bytecopy
of the explicitly SHA-pinned cone-tip adjuster. It uses the existing locked
parent/worker, attach-only runner and owned-document cleanup; no new session
framework, automatic launch, fallback, save, export, or recipe build.

The real helper receives the exact named `BodyDiaDim@BodyProfile` and literal
`PREFIX CONTROL `. The source PART, current/active document, exact named owner,
and native dimension identities are checked. The five required tip dimensions'
values/tolerances/BASIC and current configuration are read with the existing
source bank. This is not complete BREP or all-configuration coverage.

Before the helper, immediately afterward, and after one documented
`GraphicsRedraw2`, the receipt retains raw `GetText(1..8)`, numeric visibility,
source values/tolerances and dirty flags. Baseline getter dirtiness stops before
the helper. Every getter bank has an exact ownership/dirty-state exit check.
The expected change is **prefix1 and prefix-definition5 only**, both equal to
the requested literal. Suffix/callout fields 2/3/4/6/7/8, numeric visibility and
source parameters remain exact; same-session source dimension `IsSame` must
return integer 1. A different native definition is a failed tested call shape,
not a reason to discard that raw field. No geometry tolerance is added.

The source copy may become dirty in memory because this explicitly authors
its prefix; it is discarded without save. Original and copied disk SHA values
are checked before/after and again after owned cleanup. Helper and actual
imported adapter fingerprints are checked even on failure. Primary operation,
readback, cleanup and final-guard failures are retained separately. Existing
documents are excluded from owned cleanup by the shared lifecycle.

Official bundled pages read: `IDisplayDimension.SetText`, `GetText`,
`ShowDimensionValue`, `IsHoleCallout`, `swDimensionTextParts_e`,
`IFeature.GetFirstDisplayDimension`/`GetNextDisplayDimension`,
`IDimension.GetSystemValue3`, and `IModelDoc2.GraphicsRedraw2`, with the display
properties and dimension-values VBA examples. No visibility-toggle writes are
introduced to obtain feature dimensions; missing/ambiguous named inventory
fails. The method docs prohibit `GetText(0)` despite that older dimension-values
example using it; this control reads only the documented 1..8 fields.

## Reproduction invocation

Run in the frozen integrated checkout using its unchanged adapter/venv and
the serialized native seat. The source SHA below is the reviewed existing
cone-tip input, not an automatic pin.
Confirm the current PID separately; 31860 is not a perpetual readiness claim.

```powershell
$env:HARMONIC_SW_AUTOSTART='0'
$env:HARMONIC_REMOTE_CACHE_MODE='off'
$env:HARMONIC_DIAGNOSTIC_SW_PID='31860'
uv run --no-sync python cad/scripts/diagnostics/probe_dimension_prefix.py `
  --candidate HEAD `
  --source C:/src/harmonic-analyzer/cad/out/sldprt/cone-tip-adjuster.SLDPRT `
  --expected-sha256 f3578ac2b2ab95e478bc7bd72c316ebab057c125d5244af6fa2c3e12f4d48468
```

The fixed helper's independent tests passed 55, with one pre-existing opt-in
telemetry race test skipped (`pytest-telemetry/run-ity_ili2`). The new control
tests run the actual helper against native-shaped doubles and the real owned
lifecycle; no test result is native efficacy evidence.

The first combined control/marks/ownership/source-dirty/fillister/full-pilot
run passed 219 tests in 9.45 s (`pytest-telemetry/run-ubggr5v7`). The final run,
including a targeted prefix-definition refusal regression, passed 220 tests in
4.13 s (`pytest-telemetry/run-1zbx3ip0`). Ruff F and diff checks passed.
The original cone-tip source SHA above was independently reread with
read-only shared file access while preparing this control and matched exactly.
