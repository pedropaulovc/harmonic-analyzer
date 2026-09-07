# Prepared template: full-recipe functional control

The prepared rocker arm passed the native full-recipe and cold-annotation control
below; its original revision-cell overflow prevented full visual acceptance.
Later [two-shaft controls](two-shaft-pmi-entity-migration.md#both-shafts-pass-with-the-populated-title-block-candidate)
passed cold role/content checks and render inspection with the revised template.
The [production MISS/HIT at `d6ad5aad`](prepared-template-viewport-control.md#production-misshit-at-d6ad5aad)
then passed both shaft drawing tasks. That production run did not repeat cold or
printed normal/MISS/HIT comparisons. These bounded results do not establish fleet
or full-pipeline acceptance.

Use `probe_datum_policy_recipes.py --factory normal|prepared`. The current runner
passes an explicit `drawing_factory` to the isolated recipe; it does not replace
recipe globals. Normal calls the normal factory unchanged. Prepared invokes
`_drawing_prepared_template` before any owned source opens, validates a fresh
MISS and a read-only HIT, then uses the validated entry for the recipe's single
setup. The declared recipe scale and two-decimal setup must match; unsupported
factory arguments fail, with no fallback.

Each invocation stops at its first failure. A normal linked-title cold-reopen
rejection remains a failure and does not automatically launch prepared. Run the
other arm only after reviewing that receipt and obtaining a separate seat grant.
There is no paired-equivalence or speedup claim from merely creating two outputs.

Example commands after freezing the revision and obtaining an explicit grant
for each invocation (replace the PID with the currently approved native process):

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '<approved PID>'
uv run python cad/scripts/diagnostics/probe_datum_policy_recipes.py --candidate HEAD --target rocker_arm --factory normal --source-root C:/src/ha-perf-channel/cad/out/sldprt --guard-root C:/src/harmonic-analyzer/cad/out/sldprt
# Separate grant after the normal receipt has been reviewed:
uv run python cad/scripts/diagnostics/probe_datum_policy_recipes.py --candidate HEAD --target rocker_arm --factory prepared --source-root C:/src/ha-perf-channel/cad/out/sldprt --guard-root C:/src/harmonic-analyzer/cad/out/sldprt
```

Use the executing checkout's own initialized adapter and venv. A diagnostic
worktree using another venv must explicitly put its own exact adapter `src` on
`PYTHONPATH` and verify the imported package path. The production preparation
guard rejects a different checkout's imported adapter; it is not bypassed here.

Receipt fields separate template MISS/HIT accessor-and-ownership time, inner
`setup_seconds`, `recipe_seconds` (including native save/PDF/PNG), and pilot
`elapsed_seconds` (including source/annotation/cold witnesses and final input
guards, excluding parent lock/attach and outer ownership cleanup). The same exact
four original/guard hashes, unique source-copy disk hashes, named source
dimensions/tolerances/BASIC, view source/configuration, attachments, and cold
annotation/layout checks remain. A source-copy save or substantive linked-title
movement still fails. Source named-dimension checks do not claim complete
in-memory source immutability.

Original template, derived cache artifacts, actual imported adapter and helper
fingerprints receive final guards even after a recipe failure; any additional
guard failures are reported together with the original error. Native cleanup
remains the shared exact-owned-document lifecycle. Offline tests do not establish
native acceptance; the retained results below have their own measured scope.

## Native rocker result

Both commands ran separately at frozen root `b67a12c6`, adapter `e77bfda4`,
attached to SolidWorks PID 31860 with autostart disabled and remote cache off.
The normal arm ended with exit 1; after reviewing its exact title failure and
clean ownership/input guards, the prepared arm ran and ended with exit 0.

| observation | normal | prepared |
| --- | ---: | ---: |
| inner drawing setup | 4.118858 s | 1.114317 s |
| prepared read-only hit lookup | n/a | 0.043964 s |
| complete recipe, including initial save/PDF/PNG | 77.624137 s | 75.812367 s |
| pilot, including witnesses and cache creation | 138.661691 s | 170.735294 s |
| cold annotation comparison | failed | passed |

Prepared creation on the fresh cache miss took 28.331258 s, outside recipe
timing. Its hit plus setup took 1.158281 s. This one ordered pair supports the
setup improvement; the 1.811770 s whole-recipe difference is not a fleet-wide
speedup estimate. The slower total prepared pilot includes first materialization
and a completed acceptance path that the failed normal arm did not finish.

The normal arm rejected exactly three TITLE X-coordinate observations, all
shifted 7.225209847 mm. The prepared arm used no title setter and passed the
unchanged cold comparator. Its 187 reported coordinate roundoffs were at most
1.942891e-16 m; no substantive annotation change was accepted. Thus left
justification is not the only demonstrated way to stabilize this title: a
prepared blank template also worked for the full rocker recipe. The mechanism
behind that difference has not been isolated.

Both trials kept original source/guard hashes, owned source-copy bytes, template,
helper/config and actual adapter inputs unchanged. Prepared MISS/HIT artifact
hashes matched, as did final cache guards. Both owned document tables returned
to their initially empty state without cleanup errors.

Receipts under `cad/out/reports/`:

- Normal: `datum-policy-aq_ueh8h/pilot.json`, SHA-256
  `953611d82747c790e17d363b16bd6277c958386c8408e661b2813d5eb012c71a`.
- Prepared: `datum-policy-8idxoxuz/pilot.json`, SHA-256
  `962f8b832d55f6a8e245961f7a941ab8bdb143fe2d092855ddcab2a99473c99b`.

The prepared initial PNG was inspected: dimensions, datums, GTol, surface finish,
views and manufacturing notes are visible. The existing revision-cell overflow
remains, so this is not full visual acceptance. This pilot compares native cold
annotations, not a second cold PDF/PNG export. The dedicated title control's
zero-pixel result must not be attributed to this separate prepared-template run.
