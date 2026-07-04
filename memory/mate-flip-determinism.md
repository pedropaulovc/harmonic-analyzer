---
name: mate-flip-determinism
description: Mate flip-recovery is deterministic per mate; release *-logs.zip are mineable; convert to signed-offset rather than caching the flip
metadata:
  type: reference
---

The `_mate` flip-recovery (add distance mate `flip=False` → readback → delete + re-add
flipped) fires **116–154× per full release build** (v0.14: channel 73, drive_train 58).
Mining 6 releases (v0.9.1→v0.14.0) proved the correct side is **deterministic per mate** —
every apparent cross-release inconsistency is a part-lifecycle event (adds, renames like
drive_train `cone-post*`→`cone-platform*` at v0.14, channel-count changes), never a random
flip.

**Fix = eliminate the two-sidedness, not cache the guess.** `plane_distance_mate` (COINCIDENT
to a *signed* offset plane) has one solution, no flip, no readback. Proof: **frame**, converted
at v0.13, went 5 flips → 0. Residual mates that can't offset off an assembly datum: pass the
known `flip=True` literal at the call site — `_mate(..., flip=)` already seeds the first solve,
readback stays as backstop. A learned flip-cache is the wrong tool (band-aid + staleness surface
over code the signed-offset refactor deletes).

**Technique — release logs are mineable telemetry.** Each GH release ships a
`harmonic-analyzer-vX.Y.Z-logs.zip` asset; inside, `assembly-*.log` carries the
`LABEL: moved N mm -> re-adding flipped` line (strip the `.. [ Ns + Ns]` timing prefix, else
every label looks unique). Confounds when comparing across releases: cache-hit builds log no
flips (not "flip=False was correct"), pre-mechanism releases predate the logging, and labels
embed volatile coords/dims. Filter to releases where the assembly was actually rebuilt (≥1 flip).

**Naming convention (user directive):** every signed-offset seat plane MUST get a semantic
name — `create_plane` auto-names `Plane1/Plane2/…`, which ship as anonymous features. Use
`_assembly.seat_plane_name(descriptor)` → PascalCase + `Seat` suffix (e.g. `ConePlatformHeightSeat`,
`TubeFrame1RightSeat`, `Ch01SpringZPlanaritySeat`) and `adapter.rename_feature(...)` right after
`create_plane`, then mate on the new name. `plane_distance_mate` (frame, offsets off a *component*
plane) and `_assembly.seat_signed` (the bare-datum + AXIS variant, shared by drive-train & channel)
both do this. Part-build scripts name their planes via `name_last_feature` (watch the trap: it
renames the SKETCH, not the plane, if called after `create_sketch`+`exit_sketch`). Landed in #176.

**Conversion status:** frame (#138, 5→0). drive-train + part-plane naming = PR #176 (`_seat_signed`
local). channel = PR #179 (stacked on #176) — promoted `_seat_signed` → shared `_assembly.seat_signed`,
converted 7 bare-datum seats; DEFERRED the 2 part-to-part seats (base is a *component* plane) + the J3
bar amplitude driver (`free_dof_key` — must stay a suppressible distance driver, not a hard coincident).
Both #176 & #179 are STATIC-only (py_compile + ruff); need a live `doit assembly:<x> verify:soundness
verify:kinematics` with zero `flipped=True` before merge — seat was busy. Residual flips after channel:
pen (2), paper_drive (1) — trivial follow-up.

Full writeup posted to issue #64 (comment 4883506231). Related: [[drive-chain-front-plane]],
[[default-free-dof-park-drivers]], [[verify-assumptions-live-sw]].
