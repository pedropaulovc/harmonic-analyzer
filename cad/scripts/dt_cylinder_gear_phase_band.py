"""MHA-DT-12's cam lobe direction and its printed phase: the NotchPhase angle
from the cam lobe to the alignment notch, ``CAM_NOTCH_PHASE_DEG`` (3.0 deg)
+/- ``NOTCH_PHASE_TOLERANCE_DEG``.

The lobe stands on a tooth space, not a crest (owner ruling 2026-11-20 on
#749, "B": cut the lobe on the tooth space opposite the notch). Part +Y is a
tooth crest (``dt_cylinder_gear_spec``); the drive train locks every gear
``gear_train.cylinder_lock_phase_deg`` (half a tooth pitch) counter-clockwise
in this view so it meshes tooth-in-gap with the phase-0 cones. The lobe is
cut that same angle clockwise of the crest, on the next tooth space away from
the notch, so the lock turns it vertical at crank home
(``channel_frame_geom.CAM_HOME_PHASE_DEG``). The notch stays in its tooth
space, ``dt_cylinder_gear_spec.NOTCH_PHASE_DEG`` counter-clockwise of the
crest, so the lobe-to-notch phase is the sum of the two.

The cam turning fixture MHA-DT-12-TL-01 gives each gear's phase two parts:

* its own, the gear-to-gear scatter (bore float and tooth form), up to
  .13 deg (``dt_cylinder_gear_tl_cam_fixture_spec.PHASE_PER_PART_WORST_DEG``).
  The error budget books it on each channel independently (error_budget.yaml
  ``cam_phase``, ``dt_cylinder_gear_spec.CAM_PHASE_TOLERANCE_DEG``,
  +/-.25 deg);
* the phase common to all 20 gears that the fixture leaves with its holes at
  the shop's +/-.002 row, up to .47 deg (``PHASE_FIXED_WORST_DEG``). It is a
  common cam phase: channel i turns i times as fast as the crank, so no crank
  index removes it. error_budget.yaml records it as
  ``reserved.nominal_residual_mae.fixture_common_cam_phase_deg`` and the
  report scores it.

The band holds every gear's worst total (.68 deg, asserted by the fixture
spec). Delegated ruling 2026-11-17 (option 1 on #2361), for the owner's
after-the-fact review on #2144; no owner precedent (the nearest recorded case
was #749's 1.5 deg common phase, since removed by the lobe cut above):
https://github.com/pedropaulovc/harmonic-analyzer/issues/2361#issuecomment-6970972769

It lives here, not in ``dt_cylinder_gear_spec``: that spec is the channel's
shared geometry, read by some 60 native leaves (the connecting rods, cone
gears, pinion and frame parts among them), while the lobe direction and this
band are read only by the gear's builder and drawing and the fixture.
"""

from __future__ import annotations

import math

import _config
import dt_cylinder_gear_spec as gear

# The lobe's turn clockwise of the +Y crest (part view, from +Z): the drive
# train's lock, so the locked lobe stands vertical at crank home.
CAM_LOBE_OFFSET_DEG = float(_config.machine("gear_train", "cylinder_lock_phase_deg"))
# The cam centre (part x, y; mm): the throw along the lobe axis, on the side
# away from the notch (the notch is counter-clockwise of the crest, at -X).
CAM_CENTER_XY = (
    gear.ECCENTRICITY * math.sin(math.radians(CAM_LOBE_OFFSET_DEG)),
    gear.ECCENTRICITY * math.cos(math.radians(CAM_LOBE_OFFSET_DEG)),
)
# NotchPhase, lobe axis to notch radial: the native angular dimension's value.
CAM_NOTCH_PHASE_DEG = gear.NOTCH_PHASE_DEG + CAM_LOBE_OFFSET_DEG
NOTCH_PHASE_TOLERANCE_DEG = 0.7
