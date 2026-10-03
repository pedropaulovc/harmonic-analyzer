r"""SolidWorks cross-check of crank_boss_rim: the 64T's real distance to MHA-DT-005.

``crank_boss_rim`` sizes the 64T's face against MHA-DT-005 from an analytic
envelope of the gear (a solid disc at its tip diameter).  This measures the
built drive train: ``IModelDoc2::ClosestDistance`` between the placed
crank-drive gear and cone pivot post, and reads which post feature the
nearest point lies on, next to the model's nominal prediction for the nearest
feature.  The positive control for the print-worst numbers (user ruling
2026-09-28).

The real gear is cut: its tips lie on the envelope only where a tooth
happens to stand, so the measured distance may exceed the prediction, and
land on a different feature (a tip-approached feature is reached only where
a tooth stands; a face-approached one reads the envelope exactly).  It must
never undercut it: that would mean the envelope misses real material.
"""

from __future__ import annotations

import math
from typing import Any

import _telemetry
import dt_cone_pivot_post_spec as post
import crank_boss_rim
from _common import _early_bound

GEAR_COMPONENT = "dt-crank-drive-gear-1"
POST_COMPONENT = "dt-cone-pivot-post-1"
# The measured distance may undercut the envelope's by this much at most:
# ClosestDistance's own resolution, well under crank_boss_rim's 0.25 floor.
UNDERCUT_LIMIT_MM = 0.05
POST_FEATURES = ("crank boss", "head", "body", "cone boss end")
# Predicted features this close to the least are a tie, reported together.
TIE_MM = 1e-3
# How near a measured point must lie to a surface to be on it.
ON_SURFACE_MM = 0.02


def post_features_at(point: tuple[float, float, float]) -> tuple[str, ...]:
    """Every MHA-DT-005 surface a point (crank_boss_rim's frame, mm) lies on.

    A corner lies on several and a flush pair (the cone boss's end faces are
    tangent to the Ø42 body) can tie, so this names all of them, never a pick.
    """
    x, y, z = point
    tol = ON_SURFACE_MM
    face_z = post.CRANK_BOSS_NORTH_FACE
    boss_r = post.CRANK_BOSS_DIA / 2.0
    crank_radial = math.hypot(x, y - crank_boss_rim.CRANK_AXIS_Y)
    along = x * crank_boss_rim.SIN_I + z * crank_boss_rim.COS_I
    off_cone_axis = math.sqrt(max(0.0, x * x + y * y + z * z - along * along))
    post_radial = math.hypot(x, z)
    features = {
        "crank boss": (abs(z - face_z) <= tol and crank_radial <= boss_r + tol)
        or (abs(crank_radial - boss_r) <= tol and z <= face_z + tol),
        "cone boss end": abs(along - post.CONE_BOSS_LENGTH / 2.0) <= tol
        and off_cone_axis <= post.CONE_BOSS_DIA / 2.0 + tol,
        "head": abs(post_radial - post.HEAD_DIA / 2.0) <= tol
        and crank_boss_rim.HEAD_Y[0] - tol <= y <= crank_boss_rim.HEAD_Y[1] + tol,
        "body": abs(post_radial - post.BLOCK_DIA / 2.0) <= tol
        and crank_boss_rim.BODY_Y[0] - tol <= y <= crank_boss_rim.HEAD_Y[0] + tol,
    }
    return tuple(name for name, hit in features.items() if hit) or ("unclassified",)


def measure(adapter: Any, *, post_origin: tuple[float, float, float], gear_offset: float) -> dict[str, Any]:
    """Measure, log, and fail if the real gear comes nearer than the envelope.

    ``post_origin`` is where the cone axis crosses the post axis in machine
    mm (build_drive_train_assembly's _PPOST).
    """
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
        measured_features = post_features_at(near)
        nominal = crank_boss_rim.clearances(gear_offset=gear_offset, worst=False)
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
        # Every feature, nominal and at print-worst, with the governing one:
        # the leaf's trace answers the whole stack without its console log.
        worst = crank_boss_rim.clearances(gear_offset=gear_offset)
        for name in POST_FEATURES:
            slug = name.replace(" ", "_")
            sp.set_attribute(f"gear64_post.nominal.{slug}", round(nominal[name], 4))
            sp.set_attribute(f"gear64_post.print_worst.{slug}", round(worst[name], 4))
        governing = min(worst, key=worst.__getitem__)
        sp.set_attribute("gear64_post.print_worst_governing", governing)
        _telemetry.info(f"64T to MHA-DT-005, SolidWorks vs crank_boss_rim nominal: {record}")
        _telemetry.info(
            "64T to MHA-DT-005 by feature (nominal / print-worst, floor "
            f"{crank_boss_rim.FLOOR_CLEARANCE_MM}): "
            + "; ".join(f"{name} {nominal[name]:.3f} / {worst[name]:.3f}" for name in POST_FEATURES)
            + f"; governing {governing}"
        )
        if set(measured_features) != set(predicted_features):
            _telemetry.info(
                f"64T to MHA-DT-005: the envelope's nearest is {record['predicted_feature']}, "
                f"SolidWorks' is {record['measured_feature']}. The prediction is the "
                "untoothed 64T (a solid disc to its tip diameter); the cut gear reaches "
                "a tip-approached feature only where a tooth stands, so it may read "
                "farther and elsewhere, never nearer"
            )
        if measured < predicted - UNDERCUT_LIMIT_MM:
            raise RuntimeError(
                f"the placed 64T comes {measured:.3f} from MHA-DT-005's "
                f"{record['measured_feature']}, nearer than crank_boss_rim's nominal "
                f"{predicted:.3f} ({record['predicted_feature']}): the envelope misses "
                "real material"
            )
        return record
