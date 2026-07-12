---
name: per-seat-part-order
description: Cold-build part order is permuted per seat (hostname-seeded) so two machines split the work via the shared cache instead of duplicating it — now a best-effort scheduling hint under the COM seat lock
metadata:
  type: project
---

Two machines cold-building at once used to both walk parts in the SAME (sorted)
order, so they marched in lock-step: each MISSED the shared remote cache on the
same next part and built it in parallel — N seats did N× the COM work. Fixed
(2026-07-03, PR #150) by permuting the part order per seat: `_seat_part_order()` in
`dodo.py` sorts `part_stems()` by `md5(seed\0stem)`, seed = `socket.gethostname()`
(override `HARMONIC_BUILD_ORDER_SEED`). Seat A climbs one way, seat B another, so the
slower seat usually HITs the cache on a part the faster one already published — the
fleet builds each part ~once.

**Why:** parts have no inter-part deps (`_part_file_deps` never lists another part's
`.SLDPRT`), so the order in which their tasks are offered to the scheduler is free —
purely scheduling, never fed into a cache key or digest, so permuting is always safe.

**How to apply:** since the COM spine was replaced by the runtime seat lock (see
[[com-seat-lock]], 2026-07-11), this order is a **best-effort scheduling hint** only:
`task_part` yields in this order and `build` lists parts this way, but CORRECTNESS now
comes from the seat lock plus a **re-probe of the cache after acquiring the seat**
(`_cached_part_action` / `build_or_refresh` restore again under the lock, so a peer that
published while we waited is picked up). So an imperfectly-honored order costs a little
cache-split efficiency, never a duplicated/skipped build — the old "two `-n` workers
disagree on the spine → deadlock the STA seat" failure mode is GONE. The seed is still
hostname-based via `hashlib` (NOT the `PYTHONHASHSEED`-salted builtin `hash()`) so a
seat's parent + `-n` workers agree, keeping the hint coherent. Tests in
`test_dodo_recipe.py` (`check:recipe`) pin: permutation-completeness, per-seed
determinism, cross-seat divergence, and that `task_part` yields every stem once.
Offline-validated (SolidWorks-free logic).
