# Closed updated-main baseline: 55056d49

These are existing snapshot originals, copied byte-for-byte for #702. No new
build, COM session, snapshot or execution-token restamping produced this bundle.
This is the updated-main baseline, not the older initial-main `c6ab57db` baseline
and not candidate/full-stack acceptance.

- Head: `55056d4990d38ebb461f343d3002fc90731b9e73`.
- Adapter: `2269009ed56712867826516f4406afc98a0c2814` (clean in the snapshot).
- Source checkout: `C:/src/ha-assembly-granularity-integration`.
- Snapshot: `D:/harmonic-assembly-granularity-evidence/native-main-550/`.
- Capture: `2026-09-07T21:34:40.267819+00:00`.
- Recorded quiescence: `build-ended-owned-documents-closed`.

The manifest records one untracked source at capture:
`cad/scripts/diagnostics/report_assembly_dependencies.py`. Its baseline pins
and input maps remain exactly as recorded; no clean-worktree claim is made.

## Comparison inputs

[manifest.json](manifest.json) contains `semantic.parts` for all 108 leaf tasks,
including recipe keys/input maps, raw CAD SHA-256, and exact execution-token
payloads/file hashes. Its `semantic.assemblies` records all eight assembly
recipe keys, geometry fingerprints, execution tokens and DOF-sidecar state.

The `files/` subtree preserves the original relative paths of 130 inputs:
108 part `.execution` files, eight assembly `.execution` files, eight
`.massprops.sha` geometry fingerprints and six `.dof.json` files. Original and
copied bytes match the manifest; the same 130 members were also verified in the
existing ZIP before publication.

Frame and harmonic-analyzer have no `.dof.json` in this snapshot. The manifest
explicitly reports both as `missing`; the snapshot utility requires operational
DOF files only for drive-train, channel, magnifier, summing, pen and paper-drive.
Their absent sidecars are not zero-DOF readbacks and do not provide fresh native
validation. The bundle does not supply native geometry files.

## Closure and preserved hashes

The updated-main `build_bare` completed with exit 0: paper-drive FULL, top assembly
REFRESH, other six assemblies and 108 parts current. The first close guard
refused the dirty top assembly. The later bounded close discarded its unsaved
CSV-export BOM table without saving; its 114-path before/after hash maps match.
Both closure receipts remain unchanged under their original `files/cad/out/reports/assembly-granularity-integration/` paths.

| Original / copied file | SHA-256 |
|---|---|
| `manifest.json` | `2bbab87b02b55141689d0b96fae047154651ebc4a1725067d8626684fabec9b7` |
| `native-main-550-archive.json` | `49623f28d18db1ff6bc8c71bbdbb70152dca3ea60a2b0b11ae0ac30f1d42cee8` |
| `files/cad/out/reports/assembly-granularity-integration/updated-main-documents-closed.json` (refusal) | `81c73cd924703449f5da9c9ae794b2e017ea48f0c0c642735e88c2b857289963` |
| `files/cad/out/reports/assembly-granularity-integration/updated-main-bom-discard-closed.json` (successful no-save closure) | `bbd1359333979d3672b66f88d68553a21a13f82a224a4f66e0481b1f2e0c2332` |

The original 98,735,049-byte ZIP remains at
`C:/src/ha-assembly-granularity-staging/cad/out/reports/assembly-granularity-delivery/native-main-550.zip`,
SHA-256 `eb2b31272d95e6a87e1478605612f1ca123805df45dc3ce1832c0c4d46dbf9a0`.
The adjacent original `native-main-550-archive.json` is copied here; it records
verification of all 1,857 ZIP members. The ZIP contains the full 1,856-file
snapshot plus its manifest and is not included in this smaller publication.

The manifest's historical absolute `source`/`copy` paths are preserved. For this
publication, resolve each included entry using its `relative` path beneath
`files/`. Use the ZIP for snapshot entries outside this bundle. Current candidate
comparison and the full retained-stack build/closed snapshot/zero-COM repeat
still require VM1's designated integration SHA.
