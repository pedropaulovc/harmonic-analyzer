r"""SolidWorks cross-check of crank_boss_rim: the 64T's real distance to MHA-016.

``crank_boss_rim`` sizes MHA-016's spot face from an analytic envelope of the
64T (a solid disc at its tip diameter).  This measures the built drive train:
``IModelDoc2::ClosestDistance`` between the placed crank-drive gear and cone
pivot post, and reads which post feature the nearest point lies on, next to
the model's nominal prediction for the nearest feature.  The positive control
for the print-worst numbers (user ruling, 2026-09-27).

The real gear is cut: its tips lie on the envelope only where a tooth
happens to stand, so the measured distance may exceed the prediction.  It
must never undercut it: that would mean the envelope misses real material.
"""

from __future__ import annotations

import math
from typing import Any

import _telemetry
import cone_pivot_post_spec as post
import crank_boss_rim
from _common import _early_bound

GEAR_COMPONENT = "crank-drive-gear-1"
POST_COMPONENT = "cone-pivot-post-1"
# The measured distance may undercut the envelope's by this much at most:
# ClosestDistance's own resolution, well under the 0.75 target.
UNDERCUT_LIMIT_MM = 0.05
POST_FEATURES = ("crank boss", "collar", "body", "cone boss end")


def post_feature_at(point: tuple[float, float, float], face_z: float) -> str:
    """Which MHA-016 feature a point (crank_boss_rim's frame, mm) lies on."""
    x, y, z = point
    tol = 0.02
    crank_radial = math.hypot(x, y - crank_boss_rim.CRANK_AXIS_Y)
    if crank_radial <= post.CRANK_BOSS_DIA / 2.0 + tol and abs(z - face_z) <= tol:
        return "crank boss"
    along = x * crank_boss_rim.SIN_I + z * crank_boss_rim.COS_I
    if abs(along - post.CONE_BOSS_LENGTH / 2.0) <= tol:
        return "cone boss end"
    if abs(z - face_z) <= tol:
        return "spot-face run-out"
    if y >= crank_boss_rim.COLLAR_Y[0]:
        return "collar"
    return "body"


def measure(adapter: Any, *, post_origin: tuple[float, float, float], gear_offset: float) -> dict[str, Any]:
    """Measure, log, and fail if the real gear comes nearer than the envelope.

    ``post_origin`` is where the cone axis crosses the post axis in machine
    mm (build_drive_train_assembly's _PPOST).
    """
    spot = crank_boss_rim.spot_face(
        post.CRANK_SPOT_FACE_RETREAT, post.CRANK_SPOT_FACE_WIDTH, post.CRANK_SPOT_FACE_RUN_OUT
    )
    with _telemetry.span("verify.gear64_post_distance") as sp:
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        assembly = _early_bound(adapter.currentModel, "IAssemblyDoc")
        gear = assembly.GetComponentByName(GEAR_COMPONENT)
        post_component = assembly.GetComponentByName(POST_COMPONENT)
        if gear is None or post_component is None:
            raise RuntimeError(f"{GEAR_COMPONENT} or {POST_COMPONENT} is not in the assembly")
        result = model.ClosestDistance(gear, post_component)
        distance_m, _gear_point, post_point = result
        if distance_m is None or distance_m < 0.0:
            raise RuntimeError(f"ClosestDistance found no solution: {result!r}")
        measured = distance_m * 1000.0
        near = tuple(1000.0 * float(c) - o for c, o in zip(post_point, post_origin, strict=True))
        feature = post_feature_at(near, spot.face_z)
        predicted = crank_boss_rim.clearances(gear_offset=gear_offset, spot=spot, worst=False)
        least = min(POST_FEATURES, key=predicted.get)
        record = {
            "measured_mm": round(measured, 4),
            "measured_feature": feature,
            "measured_point_post_frame_mm": [round(c, 3) for c in near],
            "predicted_mm": round(predicted[least], 4),
            "predicted_feature": least,
            "delta_mm": round(measured - predicted[least], 4),
        }
        for key, value in record.items():
            sp.set_attribute(f"gear64_post.{key}", str(value))
        _telemetry.info(f"64T to MHA-016, SolidWorks vs crank_boss_rim nominal: {record}")
        if measured < predicted[least] - UNDERCUT_LIMIT_MM:
            raise RuntimeError(
                f"the placed 64T comes {measured:.3f} from MHA-016's {feature}, nearer than "
                f"crank_boss_rim's nominal {predicted[least]:.3f} ({least}): the envelope "
                "misses real material"
            )
        return record
