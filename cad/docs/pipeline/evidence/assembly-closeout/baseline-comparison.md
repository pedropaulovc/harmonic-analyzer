# Closed snapshot comparison: main550 and candidate64

Comparison complete. Six operational DOF manifests match byte-for-byte, including all 70 drive specifications. Three of eight assembly fingerprints match. Five differ and remain unexplained; the retained evidence does not establish full geometry equivalence or identify a geometric defect.

| Assembly | Geometry fingerprint | DOF manifest |
|---|---|---|
| frame | differs | absent in both |
| drive_train | differs | identical, 4 specs |
| channel | identical | identical, 60 specs |
| summing | identical | identical, 1 spec |
| magnifier | differs | identical, 3 specs |
| pen | identical | identical, 1 spec |
| paper_drive | differs | identical, 1 spec |
| harmonic_analyzer | differs | absent in both |

These DOF files describe driving entities, rest values and verification positions. They are not independent cold native DOF readbacks. Frame and top assembly have no such manifest in either snapshot; absence proves no zero-DOF result. The candidate full build's soundness and kinematics gates remain separate evidence.

## Pinned sources and verification

- Baseline head: `55056d4990d38ebb461f343d3002fc90731b9e73`, published at `66e5d88ef6efced5f402a2631dd51eee2489eeda`. Baseline capture: 2026-09-07 21:34:40 UTC. Its recorded source status includes one untracked diagnostic; no clean source-tree claim is made.
- Candidate head: `64c3dab4875354a7d44d709539e001db920a0377`. The closed snapshot's before/after identities agree and record clean tracked source and adapter trees.
- Both adapter pins: `2269009ed56712867826516f4406afc98a0c2814`.
- Candidate `closed-64c3dab4/snapshot.zip`: 325,124,327 bytes, SHA-256 `d225536a25209191f422dbbf47c16af8f9aecd636b5b03baf0bc0e2876f70569`. Its whole-file hash and size were rechecked. This comparison reread and hash-verified 260 selected members against the frozen receipt, including the native files, sidecars, ledger, cache log and relevant source/telemetry. Current live outputs were not used.
- Baseline manifest SHA-256: `2bbab87b02b55141689d0b96fae047154651ebc4a1725067d8626684fabec9b7`. The prior publication-validation receipt hash was rechecked, and all 130 published comparison sidecars were rehashed. The original baseline native ZIP is retained on VM2, not supplied in this publication; its native hashes are historical manifest evidence.
- All 115 paths in the candidate no-save closure witness match the snapshot. This set covers 106 leaf parts, eight assemblies and the top drawing. `chain-sprocket.SLDPRT` and `hex-bolt.SLDPRT` are outside that witness; both are present and hash-verified in the snapshot. Thus “115 closure paths” must not be presented as all 116 part/assembly files.

## Separate identity and recipe results

| Signal | Result |
|---|---|
| Leaf recipe input maps | 108/108 equal |
| Leaf recorded cache keys | 108/108 equal; each candidate part has exactly one `restore_hit` event |
| Leaf raw CAD SHA-256 across seats | 0/108 equal |
| Leaf execution token payloads across seats | 0/108 equal |
| Assembly raw CAD SHA-256 and execution payloads across seats | 0/8 equal for each signal |
| Assembly recipe digests and recorded cache keys | 0/8 equal for each signal |
| Candidate raw CAD versus its own execution token | 73/108 parts and 8/8 assemblies equal |

Candidate ledger input maps come from the frozen `.doit.db` current `deps:` lists, with checkout paths normalized to repository paths. No recipe, cache key or execution token was recomputed or restamped. All eight assembly recipe sidecars match their saved ledger `_recipe_digest` values. The baseline publication does not include assembly input maps, so those maps cannot be compared here; complete candidate maps are retained in the JSON.

The 35 candidate part raw/token differences are reported separately. The pipeline intentionally keeps tokens stable through parent-save metadata churn. These files remained as captured; this comparison neither attributes every byte difference to a particular save nor treats raw/token inequality as a geometry measurement. Cross-seat identity equality was not an acceptance assumption.

## What the fingerprint measures and when

`cad/scripts/_assembly.py:2464`, `assembly_geometry_digest`, is AST-identical between baseline550 and the candidate ZIP. Its normalized AST SHA-256 is `79904c9fcb4fbb8b059985195aad6a4bbb6999480092796761d920527374e192`.

It hashes `repr(rows)` containing configuration enumeration order, rounded mass (6 decimals), volume/area (3), center of mass/inertia (4), and sorted top-level component `Name2` plus `Transform2` rotation (6) and translation (4). Hash inequality cannot reveal which entry changed. Component naming, configuration order and numeric differences all enter this serialization. Hash equality covers that rounded summary, not every property of the CAD model.

The full-build path computes the digest after `SaveAsCopy`, from the still-open source document, then discards that source and reopens/reconciles the saved copy (`_assembly.py:2261`, `:2268`, `:2275`, `:2281`). The refresh path computes it after rebuild but before gates and `Save3`, writes that earlier digest afterward, and only then optionally reopens/reconciles (`:2876`, `:2922`, `:2924`, `:2934`). `verify.py` contains no digest call or fingerprint-sidecar write. These sidecars therefore must not be described as independent cold readbacks of the final saved snapshot.

No complete numeric fingerprint serialization is retained in the published baseline. Its DOF verification positions are available, but do not supply all mass and component-pose rows. The candidate serializer only persists the final hash. Its 24 relevant telemetry spans retain configuration names and component counts, without numeric mass/pose rows or `Name2` lists. Three matching log messages are watchdog activity notices naming the mass-properties operation; they contain no measurements. Dedicated matching filenames are the eight hash sidecars only. The unpublished baseline ZIP may still supply its original logs and native artifacts, but those contents were not read here.

## Smallest evidence-only follow-up

If numerical equivalence remains required, use preserved native snapshot copies on their original seats and the same serializer to read one mismatched assembly (frame) plus the matching channel control first. Record configuration order, raw and rounded mass rows, component names/transforms and referenced file/configuration identity, with explicit before/after rebuild labels. Establish whether those cold reads reproduce their own stored sidecars before attributing the cross-seat mismatch. Then inspect the remaining four differing assemblies as needed. Close without save, verify native hashes before/after, and leave execution tokens untouched. This report does not launch that readback or alter production code.

Complete hashes, per-part and per-assembly results, candidate input maps, exact DOF payloads and relevant telemetry are retained in `baseline550-candidate64-comparison.json`, SHA-256 `87b5812054690de09c83c7c264afa618f35678f6478d0e8a01cbf39e53e353a9`. The evidence-only script is `compare_closed_64_vm2_550.py`, SHA-256 `1e4964af5c9c0a308c2196404bd20fccd1b8ca0880ed2a269904ab3d38d7631b`. It exited 0, reads only Git/published evidence/the frozen ZIP, and creates its own report with exclusive-create mode.
