---
name: per-seat-part-order
description: Cold-build part order on the COM spine is permuted per seat (hostname-seeded) so two machines split the work via the shared cache instead of duplicating it
metadata:
  type: project
---

Two machines cold-building at once used to both walk parts in the SAME (sorted)
order, so they marched in lock-step: each MISSED the shared remote cache on the
same next part and built it in parallel — N seats did N× the COM work. Fixed
(2026-07-03, PR #150) by permuting the parts at the head of the
COM spine per seat: `_seat_part_order()` in `dodo.py` sorts `part_stems()` by
`md5(seed\0stem)`, seed = `socket.gethostname()` (override `HARMONIC_BUILD_ORDER_SEED`).
Seat A climbs one way, seat B another, so the slower seat usually HITs the cache on
a part the faster one already published — the fleet builds each part ~once.

**Why:** parts have no inter-part deps (`_part_file_deps` never lists another part's
`.SLDPRT`), so any part order with every part before every assembly is a valid COM
linearization — order is purely scheduling and never feeds a cache key or digest, so
permuting is always safe.

**How to apply:** the seed MUST be hostname-based via `hashlib`, NOT the builtin
`hash()` — str hashing is `PYTHONHASHSEED`-salted, so a `-n` worker would compute a
DIFFERENT permutation than the parent, disagree on a part's spine predecessor, and
let two COM tasks go ready at once → deadlock the single STA seat (the exact thing
[[release-perf-incremental]]'s COM spine exists to prevent). Tests in
`test_dodo_recipe.py` (`check:recipe`) pin: permutation-completeness, per-seed
determinism, cross-seat divergence, parts-before-assemblies. Offline-validated only
(no SW seat here) — logic is SolidWorks-free so the unit tests fully cover it.
