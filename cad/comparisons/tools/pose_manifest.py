"""Pure manifest updates shared by Pose Studio and its tests."""

from __future__ import annotations


NEUTRAL_ALIGN = {"scale": 1.0, "dx_px": 0, "dy_px": 0}


def update_pair_pose(
    pair: dict,
    *,
    az_deg: float,
    el_deg: float,
    roll_deg: float,
    zoom: float,
    target_mm: list[float] | None,
    focal_length_mm: float | None,
) -> tuple[bool, bool]:
    """Persist a studio pose and discard transforms the preview did not show.

    Pose Studio aligns the camera against the reference image at its native
    scale and offset.  Retaining a legacy ``align`` transform would apply a
    second zoom/pan when the gallery composite is generated.

    Returns ``(cleared_frame_components, reset_align)`` for the UI report.
    """
    camera = pair.setdefault("camera", {})
    camera["mode"] = "euler"
    camera["az_deg"] = round(az_deg, 2)
    camera["el_deg"] = round(el_deg, 2)
    camera["roll_deg"] = round(roll_deg, 2)
    camera["zoom"] = round(zoom, 3)
    camera["target_mm"] = (
        [round(value, 2) for value in target_mm]
        if target_mm is not None
        else None
    )
    camera["perspective"] = (
        {"focal_length_mm": round(focal_length_mm, 2)}
        if focal_length_mm is not None
        else None
    )

    cleared_frame_components = camera.pop("frame_components", None) is not None
    reset_align = pair.get("align") != NEUTRAL_ALIGN
    pair["align"] = dict(NEUTRAL_ALIGN)
    return cleared_frame_components, reset_align
