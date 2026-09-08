# Datum attachment probe results

The correction remains incomplete. Production recipes, shared helpers, adapter,
manufacturing checks and both placement limits are unchanged. Work remaining is
tracked in [#703](https://github.com/pedropaulovc/harmonic-analyzer/issues/703);
the isolated investigation is [draft PR #702](https://github.com/pedropaulovc/harmonic-analyzer/pull/702).
VM1 owns integration and merging.

## Baseline and method

Main is pinned to `55056d4990d38ebb461f343d3002fc90731b9e73`, adapter to
`2269009ed56712867826516f4406afc98a0c2814`. Both source parts were built in
`C:/src/ha-datum-placement-main` through the normal seat-locked tasks with cache
off. The [parts log](probes/parts-wrapper.log) records that build.

`probe_vm2_datum_attachment.py` runs the unchanged recipe up to its first datum.
It then calls the production helper with a different attachment, or directly
inserts a native tag without `SetPosition2` as an insertion control. Every sheet
is **partial**: later GD&T, finish symbols and notes have not been authored.
An `observed_and_closed` status means observation/export/closure completed;
it does not mean the production placement check passed.

All runs attach to existing SolidWorks PID 18748, revision 34.3.0, under the
machine-global seat lock and watchdog. Receipts contain exact code/helper/source
hashes, commands' selection/placement arguments, UTC intervals and elapsed times.
The original files are retained under this worktree's `cad/out/reports/datum-placement`.
The copies in `probes/` were verified byte-for-byte; Git text conversion is disabled.

## Observations

| Trial | Result | Receipt |
|---|---|---|
| Rod, semantic edge, original requested XY | Production helper rejected 34.697126 mm error against 0.020 mm. Native attachment matched the selected edge. | [receipt](probes/rod-edge-requested/receipt.json) |
| Rod, semantic edge, native insertion | Edge association matched and position survived rebuild/save. Old requested-XY check would still fail. | [receipt](probes/rod-edge-native/receipt.json) |
| Rod, diameter dimension, initial lookup | Diagnostic stopped before insertion because untyped annotation lookup did not find `RodDia`. | [receipt](probes/rod-dimension-requested/receipt.json) |
| Rod, diameter dimension, typed lookup, requested XY | Found `RodDia`; helper rejected 55 mm error. Tag reported zero attached entities. | [receipt](probes/rod-dimension-requested-typed/receipt.json) |
| Rod, diameter dimension, native selection | Direct `IAnnotation.Select3` returned false; insertion did not run. The production helper has an additional named-dimension selection path, so these two dimension trials are not a pure placement comparison. | [receipt](probes/rod-dimension-native/receipt.json) |
| Rack, semantic edge, requested XY | Helper rejected 38.129304 mm error against 0.100 mm. Export changed the newly built source bytes, causing a second failure. | [receipt](probes/rack-edge-requested/receipt.json) |
| Rack, semantic edge, native insertion after export | Edge association matched; position and source bytes survived rebuild/save/closure. This run used the post-export source identity and is not a same-input comparison with the preceding rack trial. | [receipt](probes/rack-edge-native-post-export/receipt.json) |

The rod resolver selected the circular boundary at model Z = 0.202000000114 m,
radius 0.003175 m. The rack resolver selected the bore circle at Z = 0.003 m,
radius 0.002499999953 m. `IsSame(edge, edge)` and the attached-entity comparison
both returned 1 for the semantic-edge trials. This proves equality to the selected
edge within those sessions; it does not independently prove the controlled face,
datum axis meaning, uniqueness or identity after cold reopen.

Visual inspection of the [rod native print](probes/rod-edge-native/partial.png)
found a readable A below the end view with a short shoulder leader. The
[rod requested-position print](probes/rod-edge-requested/partial.png) instead
has a leader crossing the end view. In the
[rack native print](probes/rack-edge-native-post-export/partial.png), A is readable
inside the gear but its leader crowds the diameter leader at the bore. No full
sheet or measured clearance acceptance is claimed.

## Identity failure and closure

Rack source bytes changed during the requested-position trial:

- Before: `1cce146435cf80cac5d9827bd76e0b6948764ed314f5304956e08acc1e46bd96`
- After: `612fda6a2db58670dce187b1e59016f721067a9f89c4a374b06bee035407bc15`

The probe failed rather than accepting this change. The
[read-only inventory](probes/rack-export-failure-inventory.json) found the exact
source and saved partial drawing clean. The
[closure receipt](probes/rack-export-failure-closed.json) preserves the identity
failure and records closure without further byte changes. The cause of the byte
change has not been established. No execution tokens or ledger entries were
restamped to conceal it; this is the new experiment's source, not a protected
assembly artifact.

A rack native trial was queued before the requested-position process had been
fully consumed. The seat lock serialized them, and its empty-inventory guard
rejected it after the earlier export failure retained documents. It authored no
new drawing or receipt. The subsequent `rack-edge-native-post-export` run began
only after the failed drawing's ownership and closure were recorded.

Early failed dimension probes were closed after matching a separate read-only
inventory, source hash and all three view references. Their receipts did not yet
record the prepared drawing title. Review identified that future closure could
otherwise confuse a later drawing of the same part with the failed probe. The
current diagnostic records that title and refuses unsaved-probe closure without
it. It also rejects simultaneous closure modes and re-enumerates after each close
to avoid using a proxy implicitly closed by SolidWorks.

The offline diagnostic regressions exercise the real entry points with fake COM
objects, including ownership refusals, implicit document closure, export failures,
position rejection, source-hash drift and the retained saved-export failure.
They do not replace the required native manufacturing or correction regressions.

## Remaining correction and acceptance

Native edge insertion is a candidate, not an approved replacement contract.
Before a shared-helper change, establish the intended cylindrical/bore datum
independently, prove cold-reopen association and move/scale behavior, and resolve
the rack leader crowding with a measured clearance check. Then propose the exact
opt-in helper diff to VM1. Unrelated callers must retain their current behavior.

VM1's [coordination reply](https://github.com/pedropaulovc/harmonic-analyzer/pull/702#issuecomment-5578052357)
allows changing only the shared test's coordinate-specific assertion after a
native positive control proves the replacement entity/association check. Preserve
its other entity-count and manufacturing assertions, and add real-receipt
fail-first regressions. The existing coordinate requirement and any replacement
contract must be documented explicitly.

Still required: normal-pipeline validation of both completed drawings, full-sheet
and detail PDF/PNG inspection, clean full-diff review, then the reviewed correction
combined with #686/#687 on an isolated integration branch. That branch needs the
full build, same-main geometry/DOF/native identity comparison, closed snapshot and
exact-head zero-COM full repeat. #682/#685/#686/#687 remain untouched.
