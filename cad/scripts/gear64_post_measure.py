r"""SolidWorks cross-check of crank_boss_rim: the 64T's real distance to MHA-016.

``crank_boss_rim`` sizes MHA-016's spot face from an analytic envelope of the
64T (a solid disc at its tip diameter).  This measures the built drive train:
``IModelDoc2::ClosestDistance`` between the placed crank-drive gear and cone
pivot post, and reads which post feature the nearest point lies on, next to
the model's nominal prediction for the nearest feature.  The positive control
for the print-worst numbers (user ruling, 2026-09-27).

The real gear is cut: its tips lie on the envelope only where a tooth
happens to stand, so the measured distance may exceed the prediction, and
land on a different feature (rim-124f: the envelope's nearest is the collar,
1.668, reached by the tip cylinder; SolidWorks read 1.6812 on the Ø42 body,
reached by the gear's south face).  It must never undercut it: that would
mean the envelope misses real material.
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
# ClosestDistance's own resolution, well under crank_boss_rim's 0.25 floor.
UNDERCUT_LIMIT_MM = 0.05
POST_FEATURES = ("crank boss", "collar", "body", "cone boss end")
# Predicted features this close to the least are a tie, reported together.
TIE_MM = 1e-3
# How near a measured point must lie to a surface to be on it.
ON_SURFACE_MM = 0.02


def post_features_at(
    point: tuple[float, float, float], spot: crank_boss_rim.SpotFace
) -> tuple[str, ...]:
    """Every MHA-016 surface a point (crank_boss_rim's frame, mm) lies on.

    A corner lies on several and a flush pair (the cone boss's end faces are
    tangent to the Ø42 body) can tie, so this names all of them, never a pick.
    """
    x, y, z = point
    tol = ON_SURFACE_MM
    on_face = abs(z - spot.face_z) <= tol
    crank_radial = math.hypot(x, y - crank_boss_rim.CRANK_AXIS_Y)
    run_out_bottom = crank_boss_rim.CRANK_AXIS_Y - spot.run_out
    half_width = (spot.width or 0.0) / 2.0
    within_width = abs(x) <= half_width + tol
    along = x * crank_boss_rim.SIN_I + z * crank_boss_rim.COS_I
    off_cone_axis = math.sqrt(max(0.0, x * x + y * y + z * z - along * along))
    post_radial = math.hypot(x, z)
    features = {
        "crank boss": on_face and crank_radial <= post.CRANK_BOSS_DIA / 2.0 + tol,
        "spot-face run-out": on_face
        and crank_radial > post.CRANK_BOSS_DIA / 2.0 + tol
        and within_width
        and run_out_bottom - tol <= y <= crank_boss_rim.CRANK_AXIS_Y + tol,
        "run-out step": abs(y - run_out_bottom) <= tol
        and within_width
        and z >= spot.face_z - tol,
        "cone boss end": abs(along - post.CONE_BOSS_LENGTH / 2.0) <= tol
        and off_cone_axis <= post.CONE_BOSS_DIA / 2.0 + tol,
        "collar": abs(post_radial - post.HEAD_DIA / 2.0) <= tol
        and crank_boss_rim.COLLAR_Y[0] - tol <= y <= crank_boss_rim.COLLAR_Y[1] + tol,
        "body": abs(post_radial - post.BLOCK_DIA / 2.0) <= tol
        and crank_boss_rim.BODY_Y[0] - tol <= y <= crank_boss_rim.COLLAR_Y[0] + tol,
    }
    return tuple(name for name, hit in features.items() if hit) or ("unclassified",)


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
        measured_features = post_features_at(near, spot)
        nominal = crank_boss_rim.clearances(gear_offset=gear_offset, spot=spot, worst=False)
        predicted = min(nominal[name] for name in POST_FEATURES)
        predicted_features = tuple(
            name for name in POST_FEATURES if nominal[name] <= predicted + TIE_MM
        )
        record = {
            "measured_mm": round(measured, 4),
            "measured_feature": " + ".join(measured_features),
            "measured_point_post_frame_mm": [round(c, 3) for c in near],
            "predicted_mm": round(predicted, 4),
            "predicted_feature": " + ".join(predicted_features),
            "delta_mm": round(measured - predicted, 4),
        }
        for key, value in record.items():
            sp.set_attribute(f"gear64_post.{key}", value)
        _telemetry.info(f"64T to MHA-016, SolidWorks vs crank_boss_rim nominal: {record}")
        if set(measured_features) != set(predicted_features):
            _telemetry.info(
                f"64T to MHA-016: the envelope's nearest is {record['predicted_feature']}, "
                f"SolidWorks' is {record['measured_feature']}. The prediction is the "
                "untoothed 64T (a solid disc to its tip diameter); the cut gear reaches "
                "a tip-approached feature only where a tooth stands, so it may read "
                "farther and elsewhere, never nearer"
            )
        if measured < predicted - UNDERCUT_LIMIT_MM:
            raise RuntimeError(
                f"the placed 64T comes {measured:.3f} from MHA-016's "
                f"{record['measured_feature']}, nearer than crank_boss_rim's nominal "
                f"{predicted:.3f} ({record['predicted_feature']}): the envelope misses "
                "real material"
            )
        return record
