---
name: mate-flip-determinism
description: Mate flip side is deterministic; distance-mate + sign-derived flip seeding beat signed-offset planes on perf; orientation-aware sigs fix mirror/rotation-twin collisions
metadata:
  type: reference
---

The `_mate` readback GUARD (add mate → readback → is the component past
`_MATE_TOL_MM`, or did SW create it in a HARD error state (`GetErrorCode2`,
e.g. 47 "dimension flipped" that fails IN PLACE with no motion — added by #186)?)
detects a wrong-side flip. The correct side is **deterministic per mate** —
apparent randomness is always a part-lifecycle event or a signature collision
(see below), never a coin flip — so a detected flip is a SEEDING BUG.

**#195: a flip is now a HARD ERROR, not a self-healed recovery.** `_mate` used
to delete + re-add flipped (self-heal) and emit a `flip-seed MISS` **warn**; that
inefficient reflip fired every build for any unseeded reference — the exact cost
the seeding system exists to kill. The recovery is REMOVED: detection stays, but a
miss now **raises** a `RuntimeError` naming the exact sig to toggle in
`_FLIP_INVERT`. Zero flips is thus ENFORCED — the build fails loud on the first
un/mis-seeded mate instead of silently paying for a per-build reflip.

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
#186's hard-error check stay as the regression alarm, but now FATAL (#195): a
wrong side **raises** `flip-seed MISS: … landed on the WRONG side … toggle sig
{sig!r} in _FLIP_INVERT`, naming the exact sig — a flip in a normal build means
the heuristic broke for that mate and the build stops until it is re-seeded.

**Learn from the build's own output.** Post-#195 a miss ERRORS, so a hard-error
build surfaces only the FIRST missing sig then halts — fix-one-rebuild-repeat, or
to bulk-learn temporarily restore the warn+self-heal path, collect every
`flip-seed MISS` in one pass, paste them in, then re-arm the raise. Re-derive
after any mate/geometry change. Set as of #195: **57 sigs** (add crank wheel /
knob wheel / rack pinion disc axial from the belt/chain drive), 7
orientation-tagged. A full cold `doit build` over all 8 assemblies is 0-flip.

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
`flip-seed MISS: … toggle sig …` error (pre-#195: `-> re-adding flipped` warn)
carries the sig to seed.
Strip the `.. [ Ns + Ns]` timing prefix. Confounds: cache-hit builds log no flips;
labels embed volatile coords (use `_flip_sig` to canonicalise).

**Naming (still true for the residual plane seats):** signed-offset seat planes
get a semantic name via `_assembly.seat_plane_name(descriptor)` (frame's
`plane_distance_mate`). Part-build planes use `name_last_feature` (trap: renames
the SKETCH, not the plane, after `create_sketch`+`exit_sketch`).

**`_FLIP_INVERT` is GLOBAL — do NOT split it per-assembly (tried, reverted PR #193).**
A seed is keyed by `_flip_sig(label)[+orient]`, and the SAME sig recurs across
assemblies — e.g. `"lever axial seat"` is exercised by mates in BOTH `channel` and
`drive_train`. A disjoint per-assembly `cad/config/flip_seeds/<stem>.yaml` split
under-populated `drive_train` (the sig sat only in `channel.yaml`) → a `flip-seed
MISS` every build (self-healed, but broke the 0-flip invariant). A CORRECT scheme
would give every assembly the full set — which is just the module-global
`_FLIP_INVERT`. Since the table is a universal dep of every assembly either way,
externalizing it to config buys NO cache-narrowing over keeping it in `_assembly.py`
next to the `_seed_flip`/`_flip_sig`/`_orient_suffix` logic it keys. Keep it there.
(Contrast: placement/`mirror_plane` IS genuinely per-part disjoint data — that split,
`_config_asm.placement` #156, is correct.)

**History:** frame #138 (5→0, planes, kept). drive #176 + channel #179 = planes,
CLOSED. **#185 = distance + sign-derived flip + orientation-aware sigs, MERGED**
(rebased through #182 drive rewrite, #186 hard-error `_mate`, main→v0.15.0).
**#195 = flip-seed MISS promoted warn→ERROR (recovery removed, zero flips
enforced), + #194 pinion_bracket deterministic pin-seat cut, main→v0.16.0.**
Related: [[default-free-dof-park-drivers]],
[[verify-assumptions-live-sw]], [[park-driver-singularities]].
