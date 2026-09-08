# Signed-zero hypothesis result at candidate64

No tested zero-only representation reproduced any of the five differing baseline fingerprints. Paper-drive also did not reproduce its own stored fingerprint. Equivalence remains unproven for these comparisons; this result excludes only the bounded variants tried.

| Assembly | Attempts | Baseline target | Own stored target |
|---|---:|---|---|
| frame | 202 | unproven_under_tested_variants | identity_match |
| drive-train | 478 | unproven_under_tested_variants | identity_match |
| channel | 1 | identity_match | identity_match |
| summing | 1 | identity_match | identity_match |
| magnifier | 136 | unproven_under_tested_variants | identity_match |
| pen | 1 | identity_match | identity_match |
| paper-drive | 665 | unproven_under_tested_variants | unproven_under_tested_variants |
| harmonic-analyzer | 138 | unproven_under_tested_variants | identity_match |

1622 attempts, 1506 distinct serialization hashes across the eight assemblies, 4.494 seconds total. Every attempt passed exact parsed Python row equality; float zero signs were the only permitted changes. No tolerance, rounding precision, configuration order, component name or nonzero value changed.

Finite variants were identity controls; global positive and negative float zeros; each single zero-sign flip; and fixed semantic mass, rotation and translation groups, including rotation indices/rows/columns and translation axes. There was no exponential combination search. Channel, summing and pen matched both hashes unchanged. Seven assemblies reproduced their own saved hash; paper-drive was the exception.

Paper-drive cold target: `cc77113a0d5cb0fb73671eec8c718d35a40eeab8587f3db3b01ed9cff5a445f0`; own stored target: `aabf4b054da9269faa5da32351d3466ff439e27ae7fd1b4284e08a54ede586d1`; baseline target: `d917c7ac65e04713d413bc5bf746bb82b6f3d849ef2f90bb91e07eeb0fd0469a`.

The first batch pins only seven completed entries from the growing capture. The separate top batch pins its completed entry after capture ended. Both pin head `64c3dab4875354a7d44d709539e001db920a0377` and retain the exact input `rows_repr`, source capture SHA and capture-script provenance. The probe read and wrote ignored evidence only; it did not use COM or modify native files, sidecars, tokens, telemetry or tracked sources. Diagnosis stops at this finite result.

| Retained result | SHA-256 |
|---|---|
| `signed-zero-64-batch1/results.json` | `2058a719474b27bf0f91a82d21da5e6824a485b5daaa768b25dad93e0632d230` |
| `signed-zero-64-top/results.json` | `6a89ca89df7887a3431342080485ab6a14c00c293597c6842d902be13ef4ae51` |
