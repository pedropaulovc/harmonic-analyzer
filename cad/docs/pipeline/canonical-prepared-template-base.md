# Canonical prepared base, requested-scale instances

All 15 registered scale pairs passed the owned native blank-sheet control at
`7c86fdba` on 2026-09-07. Populated-sheet acceptance and a matched end-to-end
fleet comparison remain outstanding. The earlier per-scale preparation receipts
remain evidence for their recorded code; the canonical result is recorded below.

## Boundary

The 92 registered drawing recipes currently declare 15 distinct `TemplateSpec`s,
all with decimal precision 2. Previously each scale created a different prepared
entry. The accessor now accepts precision only, and its stored spec is truthfully
1:1. This gives one base for the current fleet, or one per precision if a later
recipe declares precision 3. It is not removal of scale from a falsely labeled
artifact: input schema 2, manifest and native receipt all describe the 1:1 base.

`ProjectDrawingFactory` remains bound to the recipe's actual scale and precision.
`prepared_drawing_factory(adapter, entry, spec=requested)` verifies that the
entry matches the requested precision. Before the instance-scale setter, the path
validates the entry's current inputs/receipt/bytes, creates the blank and proves
its inherited 1:1 ASME-B sheet, single empty sheet and exact active/current drawing.
It then calls `ISheet.SetScale(numerator, denominator, True, False)` exactly once,
requires native True and reads back the requested scale before returning. Those
are the normal initializer's flags: scale annotation positions, not text height.
`ViewZoomtofit2` remains afterward. No normalization, style write, extra rebuild,
fallback or retry is added.

Production and owned diagnostics consume this same factory. The normal factory
remains the explicit control. No recipe specs, view placements, finalizer or source
model are changed. The finalizer still verifies the actual requested scale and
sets the title's property source to the actual model view after views exist.
Canonical blank inheritance alone does not prove populated title behavior.

The original template, all configuration YAML (including release), full adapter
Python tree, local preparation closure, lock/project files, Python identity and
native revision remain key inputs. The actual imported adapter must still be this
checkout's initialized submodule. No configuration/adapter pruning, alternate
hash analyzer or compatibility wrapper is included. Part/assembly code is untouched;
the dependency tests still require setup to remain drawing-only.

## Explicit test-contract changes

- `test_scale_and_precision_are_cache_inputs` deliberately described the old
  artifact-per-scale design. Precision remains a base input; all 15 actual scale
  requests now test the single truthful base plus exact requested-scale setters
  and readback. Wrong requested factory specs still fail.
- The inherited-factory test formerly prohibited every setter. It now requires
  only the one normal-flag instance-scale call, after the base proof. Corrupt
  cache bytes, wrong precision, unexpected views/current document and incorrect
  native return/readback still fail rather than selecting normal setup.
- The two old normal-2:1/cache mismatch tests rejected at accessor comparison.
  A raw 1:1 preparation receipt is not directly comparable to a 2:1 drawing. The
  same exact defaults gate now rejects the scaled 2:1 factory trial, before HIT;
  both the valid base and failed requested-scale trial are retained separately.
- Pinned noncanonical historical frame/accessor failures now reject before the
  seat runner/native work. The old receipts and historical instructions remain
  unchanged. Synthetic frame fixtures use 1:1; their no-resize, exact defaults,
  active-document and ownership assertions remain intact.

These premise changes were raised explicitly and approved; identity, source
values, raw ink, release/config and native acceptance predicates were not relaxed.

## Owned all-scale control

`diagnostics/probe_canonical_template_scales.py` composes the existing cache trial,
`RecipeTemplateFactory` preparation scopes and owned attach-only runner. It reads
the registry rather than duplicating a scale list. In fixed sorted order, each
spec gets a fresh normal drawing and fresh canonical instance of that **same
requested spec**. One MISS/HIT pair validates the shared base per precision.

Each factory trial compares the complete existing raw defaults/notes/SF witness,
captures or restores the normal's full viewport, and exports production PDF/PNG.
It saves only the owned blank SLDDRW using the existing proven legacy call shape,
closes it, cold-opens it, restores the exact captured viewport, and rechecks raw
defaults, PDF characters/glyph boxes and zero changed preview pixels. Save/export
and final cleanup cannot change its pinned native bytes. Full raw observations,
including existing proven no-ink exclusions, remain in the report.

The current 15-spec control therefore saves 30 owned blank drawings and one base;
it does not open any part, create model views or write managed production outputs.
Existing visible documents, protected template, cache and runtime hashes remain
guarded on success and failure. Unexpected documents stop cleanup. First failure
stops the sequence; its primary error, cleanup errors and final guard failures
remain recorded. A getter-induced activation switch before cold viewport restore
is rejected without changing the unrelated drawing.

After review and an explicit exclusive seat grant, from the frozen checkout with
its own initialized adapter/import provenance and venv:

```powershell
$env:HARMONIC_SW_AUTOSTART='0'
$env:HARMONIC_REMOTE_CACHE_MODE='off'
$env:HARMONIC_DIAGNOSTIC_SW_PID='<approved-current-PID>'
uv run python cad/scripts/diagnostics/probe_canonical_template_scales.py --expected-pid <approved-current-PID>
```

No fixed PID is reusable. The parent validates the environment before the existing
machine lock; the worker attaches only. Reports are under a fresh
`cad/out/reports/canonical-template-scales-*` directory. An all-scale blank pass
still needs printed visual review and the unchanged populated/full-fleet gates.

## Native all-scale result, 2026-09-07

The command above completed with exit 0 at root
`7c86fdbaf4e6d3d274d6be39831c68d4e4e98e16`, adapter
`25bc99b1ae39d8c0e004867e9b5c0f2068f2abc2`, on the attached PID 31860.
No source edits or checkout changes occurred during the native process.
The complete receipt is
`cad/out/reports/canonical-template-scales-j2jsh_cv/measurements.json`, SHA-256
`23deb35d5598bc2fe92df3aac65d7b81c352740b27564933fffcc7ce521031b6`.

Every pair passed the exact raw/default, viewport, native save/reopen and
printed comparison gates. All normal/canonical preview comparisons and cold
preview comparisons had **zero changed pixels** at 5100 by 3300 pixels; all
paired cold comparisons passed. All 30 saved native blanks retained their exact
bytes through cold export and final cleanup. All 46 runtime/template/cache guards
passed. The outer `ownership.json` records the one borrowed baseline document
preserved, one final document, and no probe or cleanup error. The original
DRWDOT stayed at SHA-256
`2b1bbe3dfff265e8bb35ea79f0f9690f808049f5cef764cab8959c1eaee5e849`.

| Requested scale | Normal factory seconds | Canonical factory seconds |
|---|---:|---:|
| 1:1 | 4.969167 | 1.601307 |
| 1:2 | 5.652346 | 1.682220 |
| 1:3 | 5.129620 | 1.635766 |
| 1:4 | 4.953524 | 1.682155 |
| 1:5 | 5.487613 | 1.590366 |
| 1:6 | 5.249727 | 1.643630 |
| 1:7 | 5.931822 | 1.984354 |
| 1:8 | 5.173546 | 1.521264 |
| 2:1 | 5.047432 | 1.763003 |
| 3:1 | 5.114064 | 1.647237 |
| 4:1 | 5.409907 | 1.532086 |
| 5:1 | 4.597569 | 1.592026 |
| 6:1 | 4.958193 | 1.678935 |
| 7:1 | 5.140653 | 1.584946 |
| 8:1 | 5.455546 | 1.674538 |

Mean factory setup was 5.218049 seconds normal versus 1.654256 canonical.
The single base MISS cost 49.208331 seconds; its HIT cost 0.046461 seconds,
under key `501c5b276632ddd820eb4b72f42613ba93a8ea31eda6cfd64d2b4b95461f75ec`.
For these 15 instances, canonical factory time plus that one preparation was
74.022164 seconds, versus 78.270729 seconds of normal factory time. This avoids
presenting the factory-only saving as though cold preparation were free.

The complete diagnostic took 3095.704639 seconds, including repeated raw
witnesses, PDF/PNG export, save/reopen and cleanup. That is acceptance-test time,
not production setup time. The pairs ran once each, normal then canonical, in
fixed order; they are not randomized repeated performance samples. No full-recipe
speedup or below-five-percent failure-rate claim follows from this control.

The cold canonical PNGs for 1:1, 1:7 and 8:1 were visually inspected: the frame,
zones, title block and displayed scale were intact. Model-linked properties are
blank because these drawings contain no source view. This does not establish
populated titles, manufacturing annotation coverage or affected-part render
acceptance. Those remain part of the full recipe/fleet validation.

## Earlier cost hypothesis, not a measured fleet improvement

Retained per-scale preparation was roughly 37–45 s, normal blank setup roughly
5 s, inherited setup roughly 1.4 s. At those illustrative costs, 15 preparations
plus 92 inherited setups total 684–804 s, versus 460 s normal setup. One canonical
base would avoid 14 preparations, or 518–630 s, **before** accounting for the new
per-instance scale call/readback and any downstream effects. The older exploratory
ABBA and native observations are documented in
[prepared drawing templates](prepared-drawing-templates.md) and
[key isolation](prepared-template-key-isolation.md); none is a matched end-to-end
measurement of this candidate.

The new report separates accessor/MISS/HIT, factory setup, viewport, raw witness,
print, native save, cold reopen, cleanup and guard time from total control elapsed.
Acceptance measurements are not factory cost. A later matched full-recipe/fleet
normal-vs-canonical run must count cold preparation and instance scaling before
any speedup claim.

## Offline verification

The initial canonical contract tests failed in all 28 cases before implementation.
The final focused/adjacent run passed 1,066 tests in 51.87 s, including all 15
scale pairs through the real cache/ownership state machines with native doubles,
saved/cold/printed rejection cases, all template/default/viewport suites,
buildgraph and part isolation. Receipt: `pytest-telemetry/run-rgwt_hkh` in the
isolated worktree. Undefined/unused-name lint and `git diff --check` passed.
These tests do not execute SolidWorks or replace the native gates above.
