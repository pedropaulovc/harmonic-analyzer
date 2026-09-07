# Owned source-prefix positive control

Diagnostic candidate only; no native run or persisted/printed acceptance yet.
The separate fix `271f80b27196dcc8580d912d614780f1e3a44c77` corrects
`_drawing_marks.set_dimension_prefix`: `IDisplayDimension.SetText` is void,
so success is its exact `GetText(1)` readback, not a Boolean return. Its old
telemetry fixture invented `True`; the corrected fixture keeps the span
assertion and supplies the actual void shape. No production caller exists.

The correction is replayed as `96679c5f` on published `fc13a85b`. Despite no
callers, `_drawing_marks.py` content is an input to 86 of 108 current part
helper closures (parent's read-only graph audit). Integrate this correction
before the final affected-part/full-stack build; prior native recipe acceptance
does not cover its changed digests. The diagnostic below is a separate commit,
not an exemption from that build gate.

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

## Native invocation after review and separate seat grant

Run in the frozen integrated checkout using its unchanged adapter/venv. The
source SHA below is the reviewed existing cone-tip input, not an automatic pin.
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
