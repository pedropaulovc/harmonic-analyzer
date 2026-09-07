# Prepared template: full-recipe functional control

This diagnostic is implemented and offline-tested, **not natively accepted**.
Blank normal/MISS/HIT raw and printed controls do not prove a model-linked sheet
survives native save, cold reopen and rendering. This extends the existing owned
rocker/lever pilot to test that remaining path, without changing any recipe or
production helper.

Use `probe_datum_policy_recipes.py --factory normal|prepared`. Both variants bind
only the isolated loaded recipe's `new_project_drawing`; normal calls the current
factory unchanged. Prepared invokes `_drawing_prepared_template` before any owned
source opens, validates a fresh MISS and a read-only HIT, then uses the validated
entry for the recipe's single setup. The declared recipe scale and two-decimal
setup must match; unsupported factory arguments fail, with no fallback.

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
remains the shared exact-owned-document lifecycle. No full pipeline gate, visual
acceptance, production rollout, or conflict probability is established offline.
