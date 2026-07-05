---
name: mate-flip-determinism
description: Mate flip side is deterministic; distance-mate + sign-derived flip seeding beat signed-offset planes on perf; orientation-aware sigs fix mirror/rotation-twin collisions
metadata:
  type: reference
---

The `_mate` readback-and-reflip recovery (add mate → readback → if the component
moved past `_MATE_TOL_MM`, or SW created it in a HARD error state (`GetErrorCode2`,
e.g. 47 "dimension flipped" that fails IN PLACE with no motion — added by #186),
delete + re-add flipped) fires 100–170× per full cold build. The correct side is
**deterministic per mate** — apparent randomness is always a part-lifecycle event
or a signature collision (see below), never a coin flip.

**Winner = distance mate + SIGN-DERIVED flip, NOT signed-offset planes (#185).**
Two ways to kill a flip: (a) convert the distance mate to a COINCIDENT to a signed
offset *plane* (`plane_distance_mate`/`seat_signed`) — one solution, but pays a
~10 s `create_plane` per seat; (b) keep the distance mate and SEED the correct
side. Mining/measuring proved (b) is far faster: **channel 1630 s (0 flips, 0
planes) vs 2176 s plane+dedupe vs 4616 s plane**; drive-train ~900 s. Planes were
abandoned — **#176/#179 (drive/channel signed-offset) closed, superseded by #185**.
Frame keeps its 6 `plane_distance_mate` seats (0-flip, 162 s, cheapest there).

**The mechanism (`_assembly.py`, shipped #185).** `distance_driver` takes the
SIGNED coordinate (call sites pass `coord`, not `abs(coord)`) and seeds
`flip = (signed < 0) XOR (_flip_sig(label)+_orient_suffix(...) in _FLIP_INVERT)`.
The sign handles the great majority; `_FLIP_INVERT` is the per-signature learned
polarity for references whose default side is inverted. `_mate`'s readback +
#186's hard-error check stay as the safety net AND regression alarm: any real
recovery emits a loud `flip-seed MISS` **warn** naming the exact sig to add — a
flip in a normal build means the heuristic broke for that mate.

**Learn once, from the build's own warns.** Build with `_FLIP_INVERT` empty →
every inverted seat warns its sig → paste them in → rebuild = 0 flips. Re-derive
after any mate/geometry change. Final set: **54 sigs, 7 orientation-tagged.**

**Signature collision = the real "non-determinism" (orientation fix, #185).**
`_flip_sig` strips the instance index so a 20-channel pattern collapses to ONE
entry — but that also collapses **mirror/rotation twins that need OPPOSITE
polarity**. The NORTH arbor pedestal is the SOUTH casting ROTATED 180° about Y, so
its X/Z plane normals invert (Y unchanged) → pedestal-1 and -2 need opposite flip
on datum X/Z, yet share one sig → whichever polarity is seeded, the twin
flips+recovers **every build** (looks random; is fully deterministic per
instance). Fix: `_orient_suffix(adapter, comp)` tags the sig with the sign of the
component's rotation-matrix diagonal (`""` = identity, dropped; ` @npn`/` @ppn` =
a twin) so same-oriented instances still share one entry while a twin gets its own.
Auto-caught every twin — arbor pedestal, mirrored pivot block, magnifier lever,
pinch head, pinion spring. Diagnose a collision by comparing which instance flips
across two builds with opposite membership (`-1` in one, `-2` in the other).

**Technique — release logs / build output are mineable telemetry.** The
`LABEL: … -> re-adding flipped` / `flip-seed MISS` lines carry the sig to seed.
Strip the `.. [ Ns + Ns]` timing prefix. Confounds: cache-hit builds log no flips;
labels embed volatile coords (use `_flip_sig` to canonicalise).

**Naming (still true for the residual plane seats):** signed-offset seat planes
get a semantic name via `_assembly.seat_plane_name(descriptor)` (frame's
`plane_distance_mate`). Part-build planes use `name_last_feature` (trap: renames
the SKETCH, not the plane, after `create_sketch`+`exit_sketch`).

**History:** frame #138 (5→0, planes, kept). drive #176 + channel #179 = planes,
CLOSED. **#185 = distance + sign-derived flip + orientation-aware sigs, MERGED**
(rebased through #182 drive rewrite, #186 hard-error `_mate`, main→v0.15.0).
Related: [[default-free-dof-park-drivers]],
[[verify-assumptions-live-sw]], [[park-driver-singularities]].
