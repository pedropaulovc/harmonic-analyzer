# Fillister source first-dirty control

Diagnostic-only addition on top of the reviewed tip probe `83c17ea1`.
No production recipe, source authoring, full-pilot enrollment, source pin, save
policy or geometry change. The first native attempt stopped because a required
source callout was missing; after a real source rebuild, the second localized the
first dirty transition to the whole-text recipe group. Neither saved the copy
or established cold/printed drawing acceptance.

## Exact subject and observed input

The frozen fillister drawing calls `set_dimension_text` for imported
`ShankDia@ShankProfile`, with the exact whole-text replacement `#4-40 UNC-2A`.
The common helper calls void `IDisplayDimension.SetText(0, text)`, reads back
GetText(1), then invokes its existing drawing rebuild. Presence of these calls
does not establish that the source part becomes dirty or which inner call does it.

Read-only file access at 2026-09-07 12:40:57 UTC found
`C:/src/harmonic-analyzer/cad/out/sldprt/fillister-screw.SLDPRT`, 79,367 bytes,
SHA-256 `f3adf8b31928cb001a623d9970a42f1a911335e8b4060c866c8a17d6524d5d4a`.
The existing `.fillister-screw.execution` token matched exactly. The check used
a read-only FileStream with ReadWrite/Delete sharing; no native document was
opened, rebuilt, saved, reset or repinned. This is a point-in-time byte witness,
not a new builder receipt or proof that this part satisfies the current recipe's
earlier read-only callout verifier. If an earlier group fails, the probe stops;
it does not author missing source text to reach the whole-text operation.

## Same monitor, one more explicit target

`--target fillister_screw` selects its actual spec, trusted pinned recipe, and a
unique `fillister-screw-source-dirty-*` copy. All four required dimensions must be
observed: `HeadDia@HeadProfile`, `ShankDia@ShankProfile`, `HeadHt@Head`, and
`ShankLg@Shank`. Arbor remains the default; arbor and tip retain their exact
five-dimension assertions. There is no automatic next target or full-pilot entry.

The source bank retains every supported observed feature/display dimension,
native full name/value/tolerance/BASIC, marking, precision and GetText(1..8).
It now also reads raw `ShowDimensionValue` for each observed display. That
documented Boolean must be a Boolean, as must `IsHoleCallout`; no truthiness
coercion is accepted. GetText fields must be strings, including actual empty
strings. Unsupported hole-callout text remains explicitly excluded rather than
calling an unsupported getter; visibility is still recorded. A malformed read or
native exception aborts instead of being converted to empty text or a clean state.
This additive shared diagnostic-bank field is required for other callers too;
production modules do not import this diagnostic reader.

The official SetText page specifies that selector 0 puts the string in the
prefix, clears suffix/callout text and hides the numeric value. GetText expressly
does not support selector 0; the probe continues to read only 1..8. The
ShowDimensionValue/IsHoleCallout pages and display-properties VBA example were
read. No property setter or redraw is added by this diagnostic observation.

Initial getter reads remain bracketed by source dirty-flag checks. Each existing
recipe operation group is monitored, including `set_dimension_text`; the first
dirty flag triggers a full bank/native identity capture and BaseException stop,
even through `_attempt`. A malformed transition read is retained as a capture
failure. If no earlier group dirties the copy, the existing stop occurs before
the real finalizer. This is group attribution, not a SetText-versus-rebuild
experiment, a complete BREP proof, or persisted/printed drawing acceptance.

Original and copied source SHA, frozen helper/adapter/recipe bytes, exact owned
handles, and baseline documents retain the existing guards. No finalizer,
SLDDRW/PDF/PNG save, source save, reset or retry is introduced.

## Reproduction invocation

Run from the frozen integrated checkout on the serialized seat, using its
confirmed current native PID. This reproduces the second attempt's rebuilt
input; the first attempt's old SHA remains recorded above, not auto-updated:

```powershell
$env:HARMONIC_SW_AUTOSTART='0'
$env:HARMONIC_REMOTE_CACHE_MODE='off'
$env:HARMONIC_DIAGNOSTIC_SW_PID='31860'
uv run --no-sync python cad/scripts/diagnostics/probe_source_dirty_recipe.py `
  --target fillister_screw --candidate HEAD `
  --source C:/src/harmonic-analyzer/cad/out/sldprt/fillister-screw.SLDPRT `
  --expected-sha256 5ca2e24ed0a67672d77645c8ddbc5ada3806ecec763794a3652338044692be2a
```

The existing parent runner holds the machine-global seat; the worker attaches
only and forwards the exact target, candidate and source. The receipt records
those inputs, required dimension names, original/copy hashes, baseline flags,
observations and the first dirty/clean-before-finalizer stop.

## Native evidence at 5e773756

Both attempts used candidate/helper revision
`5e7737560d1efba42ff03d75376565e3b4710962` and drawing recipe SHA-256
`9e9bad0ba6c72fecb0017b1e6b60a61217770552875111846f542d118a301293`.
Receipt paths below are relative to `cad/out/reports/`.

### First attempt: verifier stopped before whole-text authoring

`source-dirty-xieu_1wg/source-dirty.json` has SHA-256
`0875beddcd6aed9240c10b8d965833e739ff6fe9d604e12b09f85e2f1d6aa816`;
its `ownership.json` has SHA-256
`f96d344ea745b9f71390bc0c5b42dc467e07a17214e919813588a28c40126d22`.
The old `f3adf8b3...d5d4a` input failed at
`recipe.verify_dimension_callouts`: `ShankLg@Shank` imported below text was
empty instead of `UNDERHEAD LENGTH`. All 44 boundary observations were clean;
there was no `recipe.set_dimension_text` event or first-dirty capture. This is
a missing authored-source prerequisite, not evidence of source mutation.
Original/copy disk hashes stayed exact; owned drawing/copy cleanup preserved
the already-open clean cone-tip part. The verifier error was retained and
cleanup had no error.

### Real rebuild, then first-dirty capture

The real `doit part:fillister_screw` build at the same frozen head passed in
58.407867 s task time (57.138711 s `part.build`), trace
`0x2100fc633482e116f0dfa7580b977644` in `telemetry/traces.jsonl`.
Its `dim.model_callouts` span for `Shank` took 1.954997 s. The resulting
79,634-byte source has SHA-256 matching the `.fillister-screw.execution` token:
`5ca2e24ed0a67672d77645c8ddbc5ada3806ecec763794a3652338044692be2a`,
independently reread without COM. The old source/token were retained under
`fillister-before-rebuild-26170db8eb5d4ecc8ea90c491a4667bb/`; no diagnostic
reset or automatic pin change was used to reach the setter.

The second probe exited 0 with `status = stopped_at_boundary`:

- `source-dirty-nesqj5vt/source-dirty.json`, SHA-256
  `a159a7a7e72e7ac1c691eeb81cb99bd33f905ad40a0dcb612191782559137ebe`.
- `source-dirty-nesqj5vt/ownership.json`, SHA-256
  `875386000c7adef667c08f35aa98194f964ade5822b22b5a544ca4b8836e7399`.

The below-callout verifier now passed. Of 46 boundary observations, the first
45 were clean; the final one was dirty immediately after
`recipe.set_dimension_text`, at 21.7003553 s elapsed in the probe. The transition
snapshot remained dirty. This time includes setup and observation, not just
the setter. It identifies the group containing the native text setter and the
helper's rebuild, not which inner operation caused the change.

Only the two source displays of `ShankDia@ShankProfile` changed, as seen through
features `Shank` and `ShankProfile`. Both have these exact before/after rows:

| Source display field | Before | After |
|---|---|---|
| GetText(1), GetText(5) | `<MOD-DIAM>` | `#4-40 UNC-2A` |
| GetText(2/3/4/6/7/8) | empty | empty |
| ShowDimensionValue | `True` | `True` |
| Value, system units | `0.0020000000640000002` | unchanged |
| Tolerance type/min/max | `0 / 0.0 / 0.0` | unchanged |
| BASIC designation | `other` | unchanged |
| Primary/tolerance precision | `-2 / -2` | unchanged |
| Marked for drawing | `True` | `True` |

The complete source-bank diff contains exactly four leaves: fields 1 and 5 in
each of those two displays. All ten observed dimension identities were `same`;
all other recorded features, names, values, tolerances, markings, precision,
texts and `Default` configuration stayed exact. In particular, the source
`ShowDimensionValue` did **not** become false: the documented behavior on the
target drawing display cannot be assumed to propagate to the source display.

Original/copy disk hashes stayed at `5ca2e24e...2be2a`. Cleanup discarded the
owned unsaved drawing and copied part, preserving the already-open visible,
clean original fillister part. Ownership reports `preserved` and null probe/
cleanup errors; source/helper/adapter guards passed. This is a no-save,
group-level source-propagation observation. It does not prove persistence,
cold reload, printed visibility, complete BREP/all-configuration equivalence,
or successful completion of the fillister drawing recipe.

## Offline proof

The fail-first run retained 21 failures and 29 passing cases
(`pytest-telemetry/run-_j0q3xej`): missing target/visibility capture and malformed
read rejection were not implemented. Existing arbor/tip assertions were not
relaxed. The final fixture invokes the **real** whole-text helper with a void
SetText(0) test double, verifies True→False numeric visibility and all eight text
fields, and proves no later operation or finalizer runs. A separate malformed
transition preserves the capture error and stops as well. This unit test does
not establish native source propagation.

The existing source-authoring fixture gained only the native-shaped
`ShowDimensionValue=True` property; its save, cold, source and failure assertions
are unchanged. No COM, root checkout, adapter or remote write was performed.

Focused/adjacent verification passed 358 tests in 6.64 s
(`pytest-telemetry/run-kyuo8wsm`), covering the real owned-copy lifecycle,
source authoring/save boundaries, template banks, recipe loader/factory, and
unchanged fillister drawing assertions. Ruff F and `git diff --check` passed.
