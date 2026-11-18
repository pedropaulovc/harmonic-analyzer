"""MHA-DT-12's printed cam-phase band: the NotchPhase angle from the cam lobe
to the alignment notch, 1.5 deg +/- ``NOTCH_PHASE_TOLERANCE_DEG``.

The cam turning fixture MHA-DT-12-TL-01 gives each gear's phase two parts:

* its own, the gear-to-gear scatter (bore float and tooth form), up to
  .13 deg (``dt_cylinder_gear_tl_cam_fixture_spec.PHASE_PER_PART_WORST_DEG``).
  The error budget books it on each channel independently (error_budget.yaml
  ``cam_phase``, ``dt_cylinder_gear_spec.CAM_PHASE_TOLERANCE_DEG``,
  +/-.25 deg);
* the phase common to all 20 gears that the fixture leaves with its holes at
  the shop's +/-.002 row, up to .47 deg (``PHASE_FIXED_WORST_DEG``). It is a
  common cam phase of the same kind as the drive train's half-pitch lock
  (#749): error_budget.yaml records it as
  ``reserved.nominal_residual_mae.fixture_common_cam_phase_deg`` and the
  report scores it.

The band holds every gear's worst total (.68 deg, asserted by the fixture
spec). Delegated ruling 2026-11-17 (option 1 on #2361), for the owner's
after-the-fact review on #2144; no owner precedent (the nearest recorded case
is #749's 1.5 deg common phase, which the budget carries waived):
https://github.com/pedropaulovc/harmonic-analyzer/issues/2361#issuecomment-6970972769

It lives here, not in ``dt_cylinder_gear_spec``: that spec is the channel's
shared geometry, read by some 60 native leaves (the connecting rods, cone
gears, pinion and frame parts among them), while this band is read only by
the gear's builder and the fixture.
"""

from __future__ import annotations

NOTCH_PHASE_TOLERANCE_DEG = 0.7
