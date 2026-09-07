# Migrated gear pilots: alignment preflight audit

At `fdf1e84d`, no diagnostic ABI migration is needed for the six ordinary VIEW
pilots: crank-drive-gear, crank-pinion, cylinder-gear, rack-pinion,
transgear-feed-pinion and transgear-pinion.

`selected_callout_contract()` returns `None` before reading recipe code when
`source_observation` is unselected. The post-load contract check is conditional
on that result. Selecting `alignment_save` for a gear fails `require_targets()`
before files or native attachment. The narrower `ArborBoreProfile` check therefore
belongs only to the explicitly selected alignment experiment; it is not a gate
on ordinary recipes' `BoreProfile` verifier calls.

The production gear recipes use the real read-only verifier with explicit view
and source-model arguments. Their normal owned pilots must consume already-built
source parts. Do not opt into source authoring, lower-text storage or save-method
experiments to make them pass. No setter alias, controller expansion or native
identity/layout/geometry acceptance change accompanies this audit.

## Reproduction

```powershell
uv run --no-sync python -m pytest cad/scripts/test_fleet_callout_preflight_drawing.py cad/scripts/test_view_recipe_acceptance_drawing.py cad/scripts/test_callout_recipe_contract_drawing.py -q
```

This passed 125 tests in 12.09 s; receipt
`C:/src/ha-perf-fleet-callout-contract/cad/out/reports/pytest-telemetry/run-qgm5aefx`.
The new tests inspect all six actual migrated recipe imports/calls, exercise the
real pilot preflight up to its first owned-output operation, and reject every
alignment experiment before that operation. Existing full owned-pilot fixtures
now also cover all six targets, preserving cold-title and accidental-source-save
failure assertions. This is offline control-flow evidence, not native acceptance.

## Exact inputs still require deliberate production receipts

Read-only disk inspection on 2026-09-07 found every current root gear SLDPRT hash
equal to both its existing acceptance pin and its `.execution` token:

| Target | SHA-256 of native file and execution token |
|---|---|
| crank-drive-gear | `2cd81cf44def13c0bbd298617d16769206e4931eac41a04642ac6217e4880cb5` |
| crank-pinion | `08ea59d153d8801792a8b611981702d0b584b9e8a04a33e4b9cb322a3d9df6fc` |
| cylinder-gear | `46fcb66a87fd35f8862e4a01e2225688b91ab7182608bce26159f59c5b14f120` |
| rack-pinion | `96f57e663d04d745e8ad67d36a5f9ea4ddbaece4c82b2dc312bca69d4d8005b8` |
| transgear-feed-pinion | `f9b033d0026ef26996a52f73fad3b3147c6f5e5b15333a306004dcaf435a0d77` |
| transgear-pinion | `4c079ba522ccf79fa90e75afa23303ba4c2f6541232e608525368e4cbb56d335` |

Those are still the manifest's pre-migration identities. Hash equality does not
prove their source display fields were authored by the new builders; no native
content read was made in this audit.

Before each migrated gear's native acceptance trial, run its actual production
part task on the accepted code under the normal machine seat. Retain the build
revision, exact SLDPRT SHA, matching execution token and source author/readback
evidence. Deliberately update only the corresponding acceptance pin from that
receipt. Never refresh pins automatically from whatever file happens to exist.

Then run the normal owned pilot against an exact copy of that built part, without
the alignment experiment flags. Keep original/copy hash checks, cold source and
drawing checks, native parameter/owner identity, VIEW attachment geometry and
rendered layout gates intact. Changed bytes without an explicitly reviewed new
pin still fail before source open; a regression preserves this boundary for all
six targets. No source pins or native files were changed by this audit.
