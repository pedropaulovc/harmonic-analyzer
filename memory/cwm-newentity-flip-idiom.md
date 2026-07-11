---
name: cwm-newentity-flip-idiom
description: The correct CopyWithMates2 idiom for a re-valued external dim is Repeat=false + NewEntityToMateTo (honours FlipDimension); a MIXED Repeat array works, so touch only the dim slot
metadata:
  type: project
---

The production `CopyWithMates2` ladders re-value an external distance dim. On
the **Repeat=true** path a re-valued dim's `FlipDimension` **RESETS to false**
(the seed's side is not inherited). Two different workarounds had grown around
that and were BOTH removed in PR #236 (2026-07-10, supersedes #228):

- channel (#226): an always-positive cumulative ladder off the SEED's gap
  bushing (`PITCH/2 + k*PITCH`), formulated so the wanted side is the false side.
- drive-train (#228): a post-copy `set_distance_flip` (`ModifyDefinition`) heal.

**The correct idiom** (measured, scratchpad `diag_cwm_mixed.py`): re-point the
external DIM slot with **Repeat=false + NewEntityToMateTo** and carry the wanted
side in the `flips` array — `FlipDimension` IS honoured on a Repeat=false slot
(z flipped +45 vs seed −20 in the probe). And a **MIXED Repeat array works**:
one slot Repeat=false (dim re-pointed, flip honoured) while the others stay
Repeat=true keeps all copied mates intact (2/2, none dropped). So the change is
surgical — touch ONLY the dim slot; leave the shared-reference slots (concentric
to a shared shaft) on Repeat=true. No need to resolve every external entity or
worry about non-dim slot alignment.

`_cwm.copy_with_mates` gained per-slot `repeat` + `new_entities`; `resolve_entity`
turns a `named_ref` into the COM entity a `NewEntityToMateTo` slot wants (select
via `_select_mate_entity` + `GetSelectedObject6`). The pywin32 marshalling is the
same VT_ARRAY|VT_DISPATCH of `_oleobj_` pointers proven in `diag_cwm_min.py`.

- **channel J1a**: each copy now references ITS OWN gap bushing
  (`pivot_bushing_by_gap[j]`) at the local `PITCH/2` seat — the authored #110
  neighbour idiom — so a copy is topologically identical to an authored channel.
- **drive-train cone-gear**: the axial-seat slot re-points to the shared cone
  shaft's Front plane with `FlipDimension=seed_flip` honoured in the copy call.

Both assemblies rebuilt fully GREEN on real geometry (2026-07-10): all copies
placed on pose, DOF-necessity intact (drive-train 4 free DOF; channel 60), 0
interference, health 0-error. The free-DOF **solver-state ATTRACTOR is
independent** of this (X-wander was identical across every Repeat/NewEntity/flip
combination in the 2×2 table), so the channel's `put+driver` landing STAYS. See
[[cwm-free-dof-by-design]].

Extends [[verify-assumptions-live-sw]]; relates to
[[default-free-dof-park-drivers]].
