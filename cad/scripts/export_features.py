"""Write adjacent drawing requirements bound to the just-exported raw STEP.

No SolidWorks document is opened or saved. The exporter calls
``write_manifest(stem, step, revision=release_revision())`` after naming and
exporting the part's requirement faces. Face sets come from that STEP's labels;
its unmodified bytes supply ``step_sha256``.

Construction is one_piece unless the actual drawing notes explicitly supply
BUILT_UP_PERMISSION_NOTE, whose exact, nonempty text must occur in DRAWING_NOTES.
A material/process alternative (casting or solid stock) is not built-up permission.
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import importlib.util
import json
import math
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any

import _config
import _hole_spec
import _surface_finish
import cone_gear_shaft_spec as cone_shaft
import cone_pivot_post_spec as cone
import pivot_shaft_spec as shaft
import rocker_arm_notes as rocker_notes
import rocker_arm_spec as rocker
import rocker_bank_layout as bank
from _gtol_spec import CylinderFace, FaceSpec, PlanarFace, SphereFace
from _printed_tolerance import printed_band_mm, printed_deviations

SUPPORTED_PARTS = ("rocker_arm", "pivot_shaft", "cone_pivot_post")
REPO = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO / "cad" / "config"
OUT = REPO / "cad" / "out"
UNKNOWN = "unknown"


# Hand-authored source citations live only here. Python line ranges retain
# symbol/number anchors; YAML citations name scalar values by dotted key path.
# The offline tripwire resolves every emitted YAML path, including registry ones.
SOURCE_MAP = {
    "rocker_hole": (
        "harmonic-analyzer/cad/scripts/build_rocker_arm.py:510-516",
        (("ROD_HOLE_SPEC", "expect_dia_mm"),),
    ),
    "rocker_hole_callout": (
        "harmonic-analyzer/cad/scripts/draw_rocker_arm.py:435-445",
        (("add_native_hole_callout", 'label="rod-pin hole"'),),
    ),
    "hole_callout": (
        "harmonic-analyzer/cad/scripts/_drawing_common.py:1860-1874,1901,1949-1966",
        (("dia_tolerance_mm",), ("AddHoleCallout2",), ("compose_hole_callout_prefix",)),
    ),
    "rocker_position": (
        "harmonic-analyzer/cad/scripts/draw_rocker_arm.py:539-549",
        (("add_feature_control_frame", 'datums=("A", "B", "C")'),),
    ),
    "cone_mount": (
        "harmonic-analyzer/cad/scripts/build_cone_pivot_post.py:116-123",
        (("ATTACHMENT_HOLE_SPEC", "CounterBoreDepth"),),
    ),
    "cone_mount_callout": (
        "harmonic-analyzer/cad/scripts/draw_cone_pivot_post.py:1269-1280",
        (("add_native_hole_callout", 'label="mounting counterbores"'),),
    ),
    "rocker_strap_frame": (
        "harmonic-analyzer/cad/scripts/build_rocker_arm.py:396-403",
        (("depth=ARM_THICKNESS", "both_directions=True"),),
    ),
    "rocker_hub_frame": (
        "harmonic-analyzer/cad/scripts/build_rocker_arm.py:424-434",
        (("depth=HUB_LENGTH", "both_directions=True"),),
    ),
    "cone_frame": (
        "harmonic-analyzer/cad/scripts/build_cone_pivot_post.py:10-16,372-395",
        (("body stands on Top at y=0",), ('create_sketch("Top")', "depth=BLOCK_HEIGHT")),
    ),
    "cone_head_frame": (
        "harmonic-analyzer/cad/scripts/build_cone_pivot_post.py:399-429",
        (("HEAD_BASE_Y..BLOCK_HEIGHT", 'base_plane="Top Plane", offset=HEAD_BASE_Y', "depth=HEAD_HEIGHT"),),
    ),
    "cone_crank_axis": (
        "harmonic-analyzer/cad/scripts/build_cone_pivot_post.py:439-478",
        (("Straight crank boss along +Z", "offset=CRANK_BOSS_START_Z", "CRANK_BORE_HEIGHT,", "depth=CRANK_BOSS_LENGTH"),),
    ),
    "cone_journal_axis": (
        "harmonic-analyzer/cad/scripts/build_cone_pivot_post.py:126-136",
        (("journal axis runs through (0, BORE_HEIGHT, 0)", "(sin I, 0, cos I)", "CONE_BOSS_LENGTH/2 either side"),),
    ),
    "rocker_datum_a": (
        "harmonic-analyzer/cad/scripts/draw_rocker_arm.py:476-495",
        (('datum="A"', "_require_datum_on_bore"),),
    ),
    "rocker_datum_b": (
        "harmonic-analyzer/cad/scripts/draw_rocker_arm.py:510-529",
        (("RIGHT_CENTER[0] - ARM_THICKNESS / 2000.0", 'datum="B"'),),
    ),
    "right_view_frame": (
        "harmonic-analyzer/cad/scripts/draw_pivot_shaft.py:66-70",
        (('"*Right"', "Model -Z runs to the sheet's right"),),
    ),
    "rocker_datum_c": (
        "harmonic-analyzer/cad/scripts/draw_rocker_arm.py:530-538",
        (("_sheet_xy(_TIP_FACE_MID_X, _TIP_FACE_MID_Y)", 'datum="C"'),),
    ),
    "drawing_revision": (
        "harmonic-analyzer/cad/config/release.yaml:next_revision",
        (),
    ),
    "drawing_properties": (
        "harmonic-analyzer/cad/scripts/_common.py:1751-1765",
        (("def part_properties", '"Revision": _config.release_revision()'),),
    ),
    "linear_1pl": (
        "harmonic-analyzer/cad/config/title_block.yaml:linear_1pl.display",
        (),
    ),
    "linear_2pl": (
        "harmonic-analyzer/cad/config/title_block.yaml:linear_2pl.display",
        (),
    ),
    "linear_3pl": (
        "harmonic-analyzer/cad/config/title_block.yaml:linear_3pl.display",
        (),
    ),
    "angular": (
        "harmonic-analyzer/cad/config/title_block.yaml:angular.value_deg",
        (),
    ),
    "drilled_hole_plus": (
        "harmonic-analyzer/cad/config/title_block.yaml:drilled_hole.plus_mm",
        (),
    ),
    "drilled_hole_minus": (
        "harmonic-analyzer/cad/config/title_block.yaml:drilled_hole.minus_mm",
        (),
    ),
    "edge_break_r": (
        "harmonic-analyzer/cad/config/title_block.yaml:edge_break.radius_mm",
        (),
    ),
    "chamfer_max": (
        "harmonic-analyzer/cad/config/title_block.yaml:edge_break.chamfer_max_mm",
        (),
    ),
    "edge_break_display_r": (
        "harmonic-analyzer/cad/config/title_block.yaml:edge_break.display_r",
        (),
    ),
    "edge_break_display_chamfer": (
        "harmonic-analyzer/cad/config/title_block.yaml:edge_break.display_chamfer",
        (),
    ),
}


def _source_cite(*keys: str) -> list[str]:
    return [SOURCE_MAP[key][0] for key in keys]


def source_paths() -> tuple[Path, ...]:
    """Import and citation inputs; config accessor reads use doit's _config_deps."""
    from _buildgraph import module_deps_of

    script = Path(__file__).resolve()
    paths = {script, *(Path(path).resolve() for path in module_deps_of(script))}
    paths.update(
        REPO / reference.removeprefix("harmonic-analyzer/").partition(":")[0]
        for reference, _anchors in SOURCE_MAP.values()
    )
    for stem in SUPPORTED_PARTS:
        notes = _notes_module(stem)
        note_path = Path(notes.__file__).resolve()
        paths.add(note_path)
        paths.update(Path(path).resolve() for path in module_deps_of(note_path))
        paths.add(CONFIG_DIR / "parts" / f"{stem.replace('_', '-')}.yaml")
    return tuple(sorted(paths))


def _stem(stem: str) -> str:
    normalized = stem.replace("-", "_")
    if normalized not in SUPPORTED_PARTS:
        raise ValueError(f"unsupported feature-manifest part: {stem!r}")
    return normalized


@lru_cache(maxsize=None)
def _declarations(module: ModuleType) -> dict[str, str]:
    path = Path(module.__file__).resolve()
    relative = path.relative_to(REPO).as_posix()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    doc = tree.body[0]
    result = {"__frame__": f"harmonic-analyzer/{relative}:1-{doc.end_lineno}"}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names = [node.name]
        else:
            continue
        for name in names:
            result[name] = f"harmonic-analyzer/{relative}:{node.lineno}-{node.end_lineno}"
    return result


def _cite(module: ModuleType, *names: str) -> list[str]:
    return [_declarations(module)[name] for name in names]


def _finish_precision() -> int:
    return len(_surface_finish.ra(_surface_finish.MACHINED_UM).partition(".")[2])


def _feature(
    module: ModuleType, kind: str, requirements: list[str] | str,
    fields: dict[str, tuple[Any, tuple[str, ...]]],
    *, precision: dict[str, int | str] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"kind": kind, "frame": "model", "requirements": requirements}
    citations = {}
    for key, (value, names) in fields.items():
        result[key] = list(value) if isinstance(value, tuple) else value
        citations[key] = _cite(module, *names)
    result["cite"] = citations
    if precision is not None:
        result["precision"] = precision
        citations["precision"] = _cite(
            module, "DRAWING_PRECISION" if hasattr(module, "DRAWING_PRECISION") else "__frame__",
        )
    return result


def _band(model: float, places: int, band: tuple[float, float] | None = None) -> list[float]:
    # An explicit native tolerance qualifies the exact source dimension.
    # General grades qualify its printed nominal; use the source's Python
    # formatting convention without inventing a SolidWorks rounding mode.
    if band is not None:
        return [round(model + band[1], 12), round(model + band[0], 12)]
    low, high = printed_deviations(model, places)
    return [round(model + low, 12), round(model + high, 12)]


def _drilled_band(model: float, places: int) -> list[float]:
    row = _config.title_block("drilled_hole")
    # An associative Hole Wizard callout retains its authored native nominal.
    # Precision is metadata, not evidence that a Python-rounded helper string
    # replaced the callout's diameter or re-centred its drilled-hole band.
    return _band(model, places, (float(row["plus_mm"]), -float(row["minus_mm"])))


def _z_mm(
    feature: dict[str, Any], low: float, high: float, cite: list[str],
    frame: tuple[str, dict[str, Any]] | None = None,
) -> None:
    # prechips (rules/turned_profile.py, coordinates.py) reads z_mm as points
    # on the feature frame's +Z axis, resolving that frame only from this
    # manifest. It is the nominal extent of the feature's own surface along
    # its turned axis -- never a cut-to-fit, setup or acceptance requirement.
    feature["z_mm"] = [round(low, 12), round(high, 12)]
    feature["cite"]["z_mm"] = list(cite)
    if frame is not None:
        name, source = frame
        feature["frame"] = name
        feature["cite"]["frame"] = list(source["cite"])
        feature["cite"]["z_mm"] += source["cite"]


def _cone_source_frames() -> dict[str, dict[str, Any]]:
    """Rigid copies of model on the post's authored cylinder axes.

    Geometry only: they carry no binding and propose no setup or fixture;
    ``frames.setup`` stays unknown. Each +Z is a spec axis, so turned
    features off model Z can state their axial z_mm extents.
    """
    # The journal axis, (sin I, 0, cos I): the journal bore's exported axis.
    normal = cone.SURFACE_FINISHES[3].face.normal
    axis = (-normal[0], -normal[2])
    note = "geometry-only source frame on an authored spec axis; not a setup"
    return {
        # Body and head share the vertical post axis; the foot is at y=0.
        "body_axis": {
            "origin": [0.0, 0.0, 0.0], "x": [1.0, 0.0, 0.0], "y": [0.0, 0.0, -1.0], "z": [0.0, 1.0, 0.0],
            "note": note, "cite": [*_cite(cone, "__frame__"), *_source_cite("cone_frame", "cone_head_frame")],
        },
        "crank_axis": {
            "origin": [0.0, cone.CRANK_BORE_HEIGHT, 0.0], "x": [1.0, 0.0, 0.0], "y": [0.0, 1.0, 0.0], "z": [0.0, 0.0, 1.0],
            "note": note, "cite": [*_cite(cone, "CRANK_BORE_HEIGHT"), *_source_cite("cone_frame", "cone_crank_axis")],
        },
        "cone_axis": {
            "origin": [0.0, cone.BORE_HEIGHT, 0.0], "x": [axis[1], 0.0, -axis[0]], "y": [0.0, 1.0, 0.0], "z": [axis[0], 0.0, axis[1]],
            "note": note, "cite": [*_cite(cone, "BORE_HEIGHT", "INCLINE_DEG", "SURFACE_FINISHES"), *_source_cite("cone_frame", "cone_journal_axis")],
        },
    }


def _plane_between(
    start: tuple[float, float], end: tuple[float, float],
) -> PlanarFace:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    normal = (-dy / length, dx / length, 0.0)
    return PlanarFace(normal, normal[0] * start[0] + normal[1] * start[1])


def _rocker_points() -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    top = (rocker.TOP_END_X, rocker.TOP_END_Y)
    bottom = (rocker.BOT_END_X, rocker.CENTER_Y - math.sqrt(rocker.R_BOTTOM**2 - rocker.BOT_END_X**2))
    tip = (rocker.ROD_TIP_X, rocker.TOP_END_Y + rocker.TIP_FACE * (rocker.TOP_END_Y - rocker.CENTER_Y) / rocker.R_TOP)
    return top, tip, bottom


def feature_selectors(stem: str) -> dict[str, tuple[FaceSpec, ...]]:
    """Resolve every matching patch, using disjoint geometric feature domains.

    Cylinders can split at a STEP seam. A selector identifies the geometric
    surface, not an ordinal face; the COM helper names *all* matching patches.
    Shaft crowns require the existing pure SphereFace vocabulary.
    """
    stem = _stem(stem)
    if stem == "rocker_arm":
        top, tip, bottom = _rocker_points()
        right = (_plane_between(top, tip), _plane_between(tip, bottom))
        tips = tuple(
            PlanarFace((-face.normal[0], face.normal[1], 0.0), face.offset_mm)
            for face in right
        )
        return {
            "pivot_bore": (CylinderFace(rocker.PIVOT_HOLE_DIA),),
            "rod_hole": (CylinderFace(_hole_spec.blind_cut_dia_mm(rocker.ROD_HOLE_SPEC)),),
            "hub_od": (CylinderFace(rocker.HUB_DIA),),
            "hub_faces": tuple(PlanarFace((0, 0, sign), rocker.HUB_LENGTH / 2) for sign in (-1, 1)),
            # Standard Right-view sheet +X is model -Z (right_view_frame).
            # The drawing tags sheet LEFT of centre, hence the +Z broad face.
            "strap_datum_b": (PlanarFace((0, 0, 1), rocker.ARM_THICKNESS / 2),),
            "strap_faces": (PlanarFace((0, 0, -1), rocker.ARM_THICKNESS / 2),),
            "top_edge": (CylinderFace(2 * rocker.R_TOP),),
            "tip_land_pos_x": (right[0],),
            "tip_land_neg_x": (tips[0],),
            "profile_outer": (CylinderFace(2 * rocker.R_BOTTOM), right[1], tips[1]),
        }
    if stem == "pivot_shaft":
        north = -shaft.JOURNAL_LENGTH
        south = shaft.SHOULDER_SOUTH_Z_MM
        return {
            "pivot_bearing": (shaft.SURFACE_FINISHES[0].face,),
            "pivot_journal": (shaft.SURFACE_FINISHES[1].face,),
            "shoulder_od": (CylinderFace(shaft.SHOULDER_DIA),),
            "shoulder_north_face": (PlanarFace((0, 0, 1), north),),
            "shoulder_thrust": (shaft.SURFACE_FINISHES[2].face,),
            "north_relief": (
                CylinderFace(shaft.RELIEF_DIA, contains_z_mm=north + shaft.RELIEF_WIDTH / 2),
                PlanarFace((0, 0, -1), -(north + shaft.RELIEF_WIDTH)),
            ),
            "south_relief": (
                CylinderFace(shaft.RELIEF_DIA, contains_z_mm=south - shaft.RELIEF_WIDTH / 2),
                PlanarFace((0, 0, 1), south - shaft.RELIEF_WIDTH),
            ),
            "north_dome": (SphereFace(2 * shaft.DOME_SPHERE_RADIUS, (0, 0, shaft.DOME_HEIGHT - shaft.DOME_SPHERE_RADIUS)),),
            "south_dome": (SphereFace(2 * shaft.DOME_SPHERE_RADIUS, (0, 0, -bank.PIVOT_SHAFT_LENGTH + shaft.DOME_SPHERE_RADIUS - shaft.DOME_HEIGHT)),),
        }
    normal = cone.SURFACE_FINISHES[3].face.normal
    return {
        "body": (CylinderFace(cone.BLOCK_DIA),),
        "head": (CylinderFace(cone.HEAD_DIA), PlanarFace((0, 1, 0), cone.BLOCK_HEIGHT)),
        "foot_seat": (cone.SURFACE_FINISHES[0].face,),
        "crank_bore": (cone.SURFACE_FINISHES[1].face,),
        "journal_bore": (cone.SURFACE_FINISHES[2].face,),
        "crank_boss": (CylinderFace(cone.CRANK_BOSS_DIA),),
        "crank_boss_faces": (
            PlanarFace((0, 0, -1), cone.CRANK_BOSS_NORTH_FACE),
            PlanarFace((0, 0, 1), cone.CRANK_BOSS_END_Z),
        ),
        "cone_boss": (CylinderFace(cone.CONE_BOSS_DIA),),
        "cone_boss_north_face": (cone.SURFACE_FINISHES[3].face,),
        "cone_boss_south_face": (PlanarFace(tuple(-v for v in normal), cone.CONE_BOSS_LENGTH / 2),),
        **{
            f"mount_{side}": (CylinderFace(cone.ATTACHMENT_THRU_DIA, contains_x_mm=x),)
            for side, x in (("west", -cone.ATTACHMENT_X), ("east", cone.ATTACHMENT_X))
        },
        **{
            f"mount_{side}_counterbore": (
                CylinderFace(cone.ATTACHMENT_CBORE_DIA, contains_x_mm=x),
                PlanarFace((0, 1, 0), cone.BLOCK_HEIGHT - cone.ATTACHMENT_CBORE_DEPTH, contains_x_mm=x),
            )
            for side, x in (("west", -cone.ATTACHMENT_X), ("east", cone.ATTACHMENT_X))
        },
    }


def _rocker_features() -> dict[str, dict[str, Any]]:
    p = rocker_notes.DEFAULT_DRAWING_PRECISION
    hub_p = rocker_notes.DRAWING_PRECISION["Hub"]["HubLength"]
    top_p = rocker_notes.DRAWING_PRECISION["TopEdgeReference"]["TopAbovePivot"]
    axis = ((0.0, 0.0, 1.0), ("__frame__",))
    centre = ([0.0, rocker.PIVOT_MID_Y, 0.0], ("PIVOT_MID_Y",))
    top, tip, bottom = _rocker_points()
    tangent = _plane_between(top, tip).normal
    land_angle = math.degrees(math.acos(
        sum((tip[i] - top[i]) * tangent[i] for i in (0, 1)) / rocker.TIP_FACE
    ))
    result = {
        "pivot_bore": _feature(rocker, "hole", ["dia", "thru", "finish_ra", "process"], {
            "at": centre, "axis": axis,
            "dia": (_band(rocker.PIVOT_HOLE_DIA, p, rocker.PIVOT_HOLE_BAND), ("PIVOT_HOLE_DIA", "PIVOT_HOLE_BAND")),
            "nominal_dia": (rocker.PIVOT_HOLE_DIA, ("PIVOT_HOLE_DIA",)),
            "thru": (True, ("PIVOT_HOLE_DIA",)),
            "finish_ra": (_surface_finish.MACHINED_UM, ("SURFACE_FINISHES",)),
            "process": ("ream", ("PIVOT_HOLE_BAND",)), "datum": ("A", ("PIVOT_HOLE_DIA",)),
        }, precision={"dia": p, "finish_ra": 1}),
        "rod_hole": _feature(rocker, "hole", ["at", "dia", "thru", "position_dia"], {
            "at": ([rocker.ROD_HOLE_X, rocker.ROD_HOLE_Y, 0.0], ("ROD_HOLE_X", "ROD_HOLE_Y")),
            "axis": axis, "drill": (rocker.ROD_HOLE_SPEC.size, ("ROD_HOLE_SPEC",)),
            "dia": (_drilled_band(_hole_spec.blind_cut_dia_mm(rocker.ROD_HOLE_SPEC), p), ("ROD_HOLE_SPEC",)),
            "nominal_dia": (_hole_spec.blind_cut_dia_mm(rocker.ROD_HOLE_SPEC), ("ROD_HOLE_SPEC",)),
            "thru": (rocker.ROD_HOLE_SPEC.end == "through_all", ("ROD_HOLE_SPEC",)),
            "position_dia": (float(rocker.GEOMETRIC_TOLERANCES_MM["rod-pin hole position"]), ("GEOMETRIC_TOLERANCES_MM",)),
            "position_datums": (["A", "B", "C"], ("GEOMETRIC_TOLERANCES_MM",)),
            "dimension_type": ("basic", ("ROD_HOLE_X", "ROD_HOLE_Y")),
        }, precision={"at": UNKNOWN, "dia": p, "position_dia": p}),
        "hub_od": _feature(rocker, "boss", ["dia", "coaxiality_dia"], {
            "at": centre, "axis": axis,
            "dia": (_band(rocker.HUB_DIA, p), ("HUB_DIA",)),
            "dia_nominal": (rocker.HUB_DIA, ("HUB_DIA",)),
            "coaxiality_dia": (rocker_notes.HUB_COAXIALITY_DIA, ("HUB_DIA",)),
            "coaxial_to": ("pivot_bore", ("HUB_DIA",)),
        }, precision={"dia": p, "coaxiality_dia": p}),
        "hub_faces": _feature(rocker, "face", ["length"], {
            "length": (_band(rocker.HUB_LENGTH, hub_p, rocker.HUB_LENGTH_BAND), ("HUB_LENGTH", "HUB_LENGTH_BAND")),
            "length_nominal": (rocker.HUB_LENGTH, ("HUB_LENGTH",)),
            "upper_z": (rocker.HUB_LENGTH / 2, ("HUB_LENGTH",)),
            "lower_z": (-rocker.HUB_LENGTH / 2, ("HUB_LENGTH",)),
        }, precision={"length": hub_p}),
        "strap_faces": _feature(rocker, "face", ["thickness"], {
            "thickness": (_band(rocker.ARM_THICKNESS, p), ("ARM_THICKNESS",)),
            "thickness_nominal": (rocker.ARM_THICKNESS, ("ARM_THICKNESS",)),
            "upper_z": (rocker.ARM_THICKNESS / 2, ("ARM_THICKNESS",)),
            "lower_z": (-rocker.ARM_THICKNESS / 2, ("ARM_THICKNESS",)),
        }, precision={"thickness": p}),
        "top_edge": _feature(rocker, "profile", ["height_above_pivot", "radius", "arc_len"], {
            "height_above_pivot": (_band(rocker.TOP_EDGE_ABOVE_PIVOT, top_p, rocker.TOP_EDGE_BAND), ("TOP_EDGE_ABOVE_PIVOT", "TOP_EDGE_BAND")),
            "height_from": ("pivot_bore", ("PIVOT_MID_Y",)),
            "radius": (_band(rocker.R_TOP, p), ("R_TOP",)), "radius_nominal": (rocker.R_TOP, ("R_TOP",)),
            "arc_len": (_band(rocker.TOP_ARC_LEN, p), ("TOP_ARC_LEN",)),
            "arc_centre": ([0.0, rocker.CENTER_Y, 0.0], ("CENTER_Y",)),
            "centre_from_pivot_ref": (rocker.CENTER_Y - rocker.PIVOT_MID_Y, ("CENTER_Y", "PIVOT_MID_Y")),
            "end": (list(_rocker_points()[0]), ("TOP_END_X", "TOP_END_Y")),
        }, precision={"height_above_pivot": top_p, "radius": p, "arc_len": p}),
        "profile_outer": _feature(rocker, "profile", ["bottom_radius", "bottom_arc_len", "mirror_symmetric"], {
            "bottom_radius": (_band(rocker.R_BOTTOM, p), ("R_BOTTOM",)),
            "bottom_radius_nominal": (rocker.R_BOTTOM, ("R_BOTTOM",)),
            "arc_centre": ([0.0, rocker.CENTER_Y, 0.0], ("CENTER_Y",)), "top_edge_feature": ("top_edge", ("R_TOP",)),
            "bottom_arc_len": (_band(rocker.BOT_ARC_LEN, p), ("BOT_ARC_LEN",)),
            "mirror_symmetric": (True, ("R_BOTTOM",)), "depth_ref": (rocker.ARM_DEPTH, ("ARM_DEPTH",)),
            "bottom_end": (list(bottom), ("BOT_END_X", "R_BOTTOM", "CENTER_Y")),
            "radial_tip_end": (list(tip), ("ROD_TIP_X", "TOP_END_Y", "TIP_FACE", "R_TOP", "CENTER_Y")),
        }, precision={"bottom_radius": p, "bottom_arc_len": p}),
    }
    result["strap_datum_b"] = _feature(rocker, "face", ["thickness"], {
        "thickness": (_band(rocker.ARM_THICKNESS, p), ("ARM_THICKNESS",)),
        "thickness_nominal": (rocker.ARM_THICKNESS, ("ARM_THICKNESS",)),
        "plane": ({"frame": "model", "axis": "z", "value": rocker.ARM_THICKNESS / 2}, ("ARM_THICKNESS",)),
        "datum": ("B", ("ARM_THICKNESS",)),
    }, precision={"thickness": p})
    result["strap_datum_b"]["cite"]["datum"] = _source_cite("rocker_datum_b", "right_view_frame")
    result["pivot_bore"]["cite"]["datum"] = _source_cite("rocker_datum_a")
    for name, sign in (("tip_land_pos_x", 1), ("tip_land_neg_x", -1)):
        result[name] = _feature(rocker, "face", ["tip_land", "land_angle_deg"], {
            "tip_land": (_band(rocker.TIP_FACE, p), ("TIP_FACE",)),
            "land_angle_deg": (UNKNOWN, ("TIP_FACE",)),
            "land_angle_nominal_deg": (land_angle, ("TOP_END_X", "TOP_END_Y", "ROD_TIP_X", "TIP_FACE", "R_TOP", "CENTER_Y")),
            "radial_tip_end": ([sign * tip[0], tip[1]], ("ROD_TIP_X", "TOP_END_Y", "TIP_FACE", "R_TOP", "CENTER_Y")),
            "top_edge_feature": ("top_edge", ("R_TOP",)),
        }, precision={"tip_land": p, "land_angle_deg": UNKNOWN})
    result["tip_land_pos_x"]["datum"] = "C"
    result["tip_land_pos_x"]["cite"]["datum"] = _source_cite("rocker_datum_c")
    notes_cite = _cite(rocker_notes, "DRAWING_NOTES")
    for name in ("pivot_bore", "strap_faces", "strap_datum_b", "top_edge", "profile_outer", "tip_land_pos_x", "tip_land_neg_x", "hub_od"):
        for key in result[name]["cite"]:
            result[name]["cite"][key] += notes_cite
    result["hub_od"]["cite"]["coaxiality_dia"] = _cite(rocker_notes, "HUB_COAXIALITY_DIA", "DRAWING_NOTES")
    result["rod_hole"]["cite"]["nominal_dia"] += _cite(_hole_spec, "NUMBER_DRILL_MM")
    result["rod_hole"]["cite"]["dia"] += _cite(_hole_spec, "NUMBER_DRILL_MM")
    result["rod_hole"]["cite"]["dia"] += _source_cite("rocker_hole", "rocker_hole_callout", "hole_callout")
    result["rod_hole"]["cite"]["position_datums"] = _source_cite("rocker_position")
    return result


def _shaft_features() -> dict[str, dict[str, Any]]:
    p = shaft.DRAWING_PRECISION_BY_NAME
    result = {}
    for name, probe, length in (
        ("pivot_bearing", shaft.BODY_PROBE_Z_MM, None),
        ("pivot_journal", shaft.JOURNAL_PROBE_Z_MM, shaft.JOURNAL_LENGTH),
    ):
        fields = {
            "at": ([0.0, 0.0, probe], ("BODY_PROBE_Z_MM" if length is None else "JOURNAL_PROBE_Z_MM",)),
            "axis": ([0.0, 0.0, 1.0], ("__frame__",)),
            "dia": (_band(shaft.SHAFT_DIA, p["ShaftDia"], shaft.SHAFT_DIA_BAND), ("SHAFT_DIA", "SHAFT_DIA_BAND")),
            "dia_nominal": (shaft.SHAFT_DIA, ("SHAFT_DIA",)),
            "finish_ra": (_surface_finish.MACHINED_UM, ("SURFACE_FINISHES",)),
        }
        requirements = ["dia", "finish_ra"]
        precision = {"dia": p["ShaftDia"], "finish_ra": 1}
        if length is not None:
            fields["length"] = (_band(length, p["JournalLength"]), ("JOURNAL_LENGTH",))
            fields["length_nominal"] = (length, ("JOURNAL_LENGTH",))
            requirements.append("length")
            precision["length"] = p["JournalLength"]
        else:
            fields["length_ref"] = (bank.PIVOT_SHAFT_LENGTH, ("LENGTH_CALLOUT",))
            fields["note"] = (shaft.LENGTH_CALLOUT, ("LENGTH_CALLOUT",))
        result[name] = _feature(shaft, "shaft", requirements, fields, precision=precision)
    result["pivot_bearing"]["cite"]["length_ref"] += _cite(bank, "PIVOT_SHAFT_LENGTH")
    result["shoulder_od"] = _feature(shaft, "boss", ["dia"], {
        "dia": (_band(shaft.SHOULDER_DIA, p["ShoulderDia"]), ("SHOULDER_DIA",)),
        "dia_nominal": (shaft.SHOULDER_DIA, ("SHOULDER_DIA",)),
    }, precision={"dia": p["ShoulderDia"]})
    result["shoulder_north_face"] = _feature(shaft, "face", ["length"], {
        "length": (_band(shaft.SHOULDER_LENGTH, p["ShoulderLength"]), ("SHOULDER_LENGTH",)),
        "length_nominal": (shaft.SHOULDER_LENGTH, ("SHOULDER_LENGTH",)),
        "plane": ({"frame": "model", "axis": "z", "value": -shaft.JOURNAL_LENGTH}, ("JOURNAL_LENGTH",)),
    }, precision={"length": p["ShoulderLength"]})
    result["shoulder_thrust"] = _feature(shaft, "face", ["length", "finish_ra"], {
        "length": (_band(shaft.SHOULDER_LENGTH, p["ShoulderLength"]), ("SHOULDER_LENGTH",)),
        "length_nominal": (shaft.SHOULDER_LENGTH, ("SHOULDER_LENGTH",)),
        "upper_z": (-shaft.JOURNAL_LENGTH, ("JOURNAL_LENGTH",)),
        "lower_z": (shaft.SHOULDER_SOUTH_Z_MM, ("SHOULDER_SOUTH_Z_MM",)),
        "finish_ra": (_surface_finish.MACHINED_UM, ("SURFACE_FINISHES",)),
        "plane": ({"frame": "model", "axis": "z", "value": shaft.SHOULDER_SOUTH_Z_MM}, ("SHOULDER_SOUTH_Z_MM",)),
    }, precision={"length": p["ShoulderLength"], "finish_ra": 1})
    for name, z in (("north_relief", -shaft.JOURNAL_LENGTH + shaft.RELIEF_WIDTH / 2), ("south_relief", shaft.SHOULDER_SOUTH_Z_MM - shaft.RELIEF_WIDTH / 2)):
        result[name] = _feature(shaft, "groove", ["dia", "width"], {
            "dia": (_band(shaft.RELIEF_DIA, p["ReliefDia"]), ("RELIEF_DIA",)),
            "dia_nominal": (shaft.RELIEF_DIA, ("RELIEF_DIA",)),
            "width": (_band(shaft.RELIEF_WIDTH, p["ReliefWidth"]), ("RELIEF_WIDTH",)),
            "width_nominal": (shaft.RELIEF_WIDTH, ("RELIEF_WIDTH",)),
            "at": ([0.0, 0.0, z], ("JOURNAL_LENGTH", "SHOULDER_LENGTH", "RELIEF_WIDTH")),
        }, precision={"dia": p["ReliefDia"], "width": p["ReliefWidth"]})
    for name, z in (("north_dome", 0.0), ("south_dome", -bank.PIVOT_SHAFT_LENGTH)):
        result[name] = _feature(shaft, "dome", ["height"], {
            "height": (_band(shaft.DOME_HEIGHT, p["DomeHeight"]), ("DOME_HEIGHT",)),
            "height_nominal": (shaft.DOME_HEIGHT, ("DOME_HEIGHT",)),
            "sphere_radius": (shaft.DOME_SPHERE_RADIUS, ("DOME_SPHERE_RADIUS",)),
            "base_radius": (shaft.SHAFT_DIA / 2, ("SHAFT_DIA",)),
            "base_z": (z, ("__frame__",)), "note": (shaft.DOME_CALLOUT, ("DOME_CALLOUT",)),
        }, precision={"height": p["DomeHeight"]})
    result["south_dome"]["cite"]["base_z"] = _cite(bank, "PIVOT_SHAFT_LENGTH")
    # Model Z is the turned axis, origin at the north end of the cylinder.
    # Each O.D. spans its drawn length; the relief grooves overlay it at the
    # shoulder faces, as prechips gives a groove priority over its cylinder.
    # Each dome rises from a cylinder end to its apex.
    north, south = -shaft.JOURNAL_LENGTH, shaft.SHOULDER_SOUTH_Z_MM
    shoulder = ("JOURNAL_LENGTH", "SHOULDER_LENGTH", "SHOULDER_SOUTH_Z_MM")
    length = bank.PIVOT_SHAFT_LENGTH
    for name, low, high, names, bank_names in (
        ("north_dome", 0.0, shaft.DOME_HEIGHT, ("DOME_HEIGHT",), ()),
        ("pivot_journal", north, 0.0, ("JOURNAL_LENGTH",), ()),
        ("north_relief", north, north + shaft.RELIEF_WIDTH, ("JOURNAL_LENGTH", "RELIEF_WIDTH"), ()),
        ("shoulder_od", south, north, shoulder, ()),
        ("south_relief", south - shaft.RELIEF_WIDTH, south, (*shoulder, "RELIEF_WIDTH"), ()),
        ("pivot_bearing", -length, south, shoulder, ("PIVOT_SHAFT_LENGTH",)),
        ("south_dome", -length - shaft.DOME_HEIGHT, -length, ("DOME_HEIGHT",), ("PIVOT_SHAFT_LENGTH",)),
    ):
        _z_mm(result[name], low, high, [*_cite(shaft, *names), *_cite(bank, *bank_names)])
    return result


def _cone_features() -> dict[str, dict[str, Any]]:
    p = cone.DRAWING_PRECISION_BY_NAME
    def size(kind: str, fields: dict[str, tuple[str, str]]) -> dict[str, Any]:
        values = {}
        precision = {}
        for key, (constant, dimension) in fields.items():
            model = getattr(cone, constant)
            values[key] = (_band(model, p[dimension]), (constant,))
            values[f"{key}_nominal"] = (model, (constant,))
            precision[key] = p[dimension]
        return _feature(cone, kind, list(fields), values, precision=precision)
    normal = cone.SURFACE_FINISHES[3].face.normal
    result = {
        "body": size("boss", {"dia": ("BLOCK_DIA", "MainBodyDia"), "height": ("BLOCK_HEIGHT", "MainBodyHt")}),
        "head": size("boss", {"dia": ("HEAD_DIA", "HeadDia"), "height": ("HEAD_HEIGHT", "HeadHt")}),
        "crank_boss": size("boss", {"dia": ("CRANK_BOSS_DIA", "CrankBossDia")}),
        "crank_boss_faces": size("face", {"length": ("CRANK_BOSS_LENGTH", "CrankBossLen"), "station": ("CRANK_BOSS_NORTH_FACE", "CrankBossStartZ")}),
        "cone_boss": size("boss", {"dia": ("CONE_BOSS_DIA", "ConeBossDia")}),
        "cone_boss_north_face": size("face", {"length": ("CONE_BOSS_LENGTH", "ConeBossLen")}),
        "cone_boss_south_face": _feature(cone, "face", [], {"normal": (tuple(-v for v in normal), ("SURFACE_FINISHES",))}),
        "foot_seat": _feature(cone, "face", ["finish_ra"], {
            "normal": ([0.0, -1.0, 0.0], ("SURFACE_FINISHES",)), "finish_ra": (_surface_finish.SEAT_UM, ("SURFACE_FINISHES",)),
            "datum": ("B", ("PART_DATUMS",)), "plane": ({"frame": "model", "axis": "y", "value": 0.0}, ("__frame__",)),
        }, precision={"finish_ra": 1}),
    }
    result["cone_boss_north_face"]["normal"] = list(normal)
    result["cone_boss_north_face"]["finish_ra"] = _surface_finish.MACHINED_UM
    result["cone_boss_north_face"]["requirements"].append("finish_ra")
    result["cone_boss_north_face"]["cite"].update({"finish_ra": _cite(cone, "SURFACE_FINISHES"), "normal": _cite(cone, "SURFACE_FINISHES")})
    for name, diameter, height, dimension in (
        ("journal_bore", cone.BORE_DIA, cone.BORE_HEIGHT, "JournalBoreDia"),
        ("crank_bore", cone.CRANK_BORE_DIA, cone.CRANK_BORE_HEIGHT, "CrankBoreDia"),
    ):
        constants = ("BORE_DIA", "BORE_HEIGHT") if name == "journal_bore" else ("CRANK_BORE_DIA", "CRANK_BORE_HEIGHT")
        result[name] = _feature(cone, "hole", ["dia", "thru", "finish_ra"], {
            "at": ([0.0, height, 0.0], (constants[1],)),
            "axis": ([-normal[0], 0.0, -normal[2]] if name == "journal_bore" else [0.0, 0.0, 1.0], ("INCLINE_DEG",)),
            "dia": (_band(diameter, p[dimension], cone.RUNNING_BORE_BAND), (constants[0], "RUNNING_BORE_BAND")),
            "nominal_dia": (diameter, (constants[0],)), "thru": (True, (constants[0],)),
            "finish_ra": (_surface_finish.MACHINED_UM, ("SURFACE_FINISHES",)),
        }, precision={"dia": p[dimension], "finish_ra": 1})
    journal = result["journal_bore"]
    journal.update({"height": _band(cone.BORE_HEIGHT, p["JournalAxisY"], (cone.JOURNAL_AXIS_HEIGHT_TOLERANCE_MM, -cone.JOURNAL_AXIS_HEIGHT_TOLERANCE_MM)), "height_from": "foot_seat", "datum": "A", "note": cone_shaft.POST_JOURNAL_RIM_BREAK})
    # The schema has no per-feature rim-break field. Preserve the sourced
    # note and unresolved inspection identity instead of declaring it absent.
    journal["requirements"] += ["height", UNKNOWN]
    journal["precision"]["height"] = p["JournalAxisY"]
    journal["cite"].update({"height": _cite(cone, "BORE_HEIGHT", "JOURNAL_AXIS_HEIGHT_TOLERANCE_MM"), "height_from": _cite(cone, "BORE_HEIGHT"), "datum": _cite(cone, "PART_DATUMS"), "note": _cite(cone_shaft, "POST_JOURNAL_RIM_BREAK", "THRUST_EDGE_BREAK_MAX")})
    crank = result["crank_bore"]
    control = cone.GEOMETRIC_CONTROLS[0]
    crank.update({"separation": _band(cone.CRANK_ABOVE_CONE, p["CrankAboveCone"], cone.CRANK_ABOVE_CONE_BAND), "height_from": "journal_bore", "height_nominal": cone.CRANK_BORE_HEIGHT, "angularity_dia": float(control.tolerance), "angularity_datums": list(control.datums), "dimension_type": "basic", "land_angle_nominal_deg": cone.INCLINE_DEG})
    crank["requirements"] += ["separation", "angularity_dia", "angularity_datums"]
    crank["precision"].update({
        "separation": p["CrankAboveCone"],
        "angularity_dia": len(control.tolerance.partition(".")[2]),
        "land_angle_nominal_deg": p["InclineAngle"],
    })
    crank["cite"].update({"separation": _cite(cone, "CRANK_ABOVE_CONE", "CRANK_ABOVE_CONE_BAND"), "height_from": _cite(cone, "CRANK_ABOVE_CONE"), "height_nominal": _cite(cone, "CRANK_BORE_HEIGHT"), "angularity_dia": _cite(cone, "CRANK_BORE_ANGULARITY_MM", "GEOMETRIC_CONTROLS"), "angularity_datums": _cite(cone, "GEOMETRIC_CONTROLS"), "dimension_type": _cite(cone, "BASIC_DIMENSIONS"), "land_angle_nominal_deg": _cite(cone, "INCLINE_DEG", "BASIC_DIMENSIONS")})
    # The angularity zone over the boss length bounds the bore axis direction
    # to this angle: a derived landing allowance, not a printed angle band,
    # so it never joins the requirements beside the BASIC angle and its frame.
    crank["angle_tol_deg"] = cone.CRANK_BORE_ANGLE_LIMIT_DEG
    crank["cite"]["angle_tol_deg"] = _cite(cone, "CRANK_BORE_ANGLE_LIMIT_DEG")
    for side, x, dim in (("west", -cone.ATTACHMENT_X, "MountWestX"), ("east", cone.ATTACHMENT_X, "MountEastX")):
        name = f"mount_{side}"
        result[name] = _feature(cone, "hole", ["dia", "thru", "station"], {
            "at": ([x, cone.BLOCK_HEIGHT, 0.0], ("ATTACHMENT_X", "BLOCK_HEIGHT")), "axis": ([0.0, -1.0, 0.0], ("__frame__",)),
            "dia": (_drilled_band(cone.ATTACHMENT_THRU_DIA, p[dim]), ("ATTACHMENT_THRU_DIA",)),
            "nominal_dia": (cone.ATTACHMENT_THRU_DIA, ("ATTACHMENT_THRU_DIA",)), "thru": (True, ("ATTACHMENT_THRU_DIA",)),
            "station": (_band(x, p[dim]), ("ATTACHMENT_X",)), "station_nominal": (x, ("ATTACHMENT_X",)),
        }, precision={"dia": p[dim], "station": p[dim]})
        result[f"{name}_counterbore"] = _feature(cone, "counterbore", ["dia", "depth"], {
            "parent": (name, ("ATTACHMENT_THRU_DIA",)),
            "dia": (_band(cone.ATTACHMENT_CBORE_DIA, p[dim]), ("ATTACHMENT_CBORE_DIA",)), "nominal_dia": (cone.ATTACHMENT_CBORE_DIA, ("ATTACHMENT_CBORE_DIA",)),
            "depth": (_band(cone.ATTACHMENT_CBORE_DEPTH, p[dim]), ("ATTACHMENT_CBORE_DEPTH",)), "depth_ref": (cone.ATTACHMENT_CBORE_DEPTH, ("ATTACHMENT_CBORE_DEPTH",)),
        }, precision={"dia": p[dim], "depth": p[dim]})
        result[name]["cite"]["dia"] += _source_cite("cone_mount", "cone_mount_callout", "hole_callout")
    # Axial extents along each cylinder's own spec axis. The body's O.D. ends
    # where the coaxial, larger head begins; both bosses span their authored
    # end faces (crank: CrankBossStartZ + CrankBossLen; cone: mid-plane pads).
    frames = _cone_source_frames()
    head = ("HEAD_BASE_Y", "BLOCK_HEIGHT", "HEAD_HEIGHT")
    crank_ends = ("CRANK_BOSS_START_Z", "CRANK_BOSS_NORTH_FACE", "HEAD_DIA", "CRANK_BOSS_END_Z", "CRANK_BOSS_LENGTH", "CRANK_BOSS_LENGTH_IN")
    for name, frame, low, high, names in (
        ("body", "body_axis", 0.0, cone.HEAD_BASE_Y, head),
        ("head", "body_axis", cone.HEAD_BASE_Y, cone.BLOCK_HEIGHT, head),
        ("crank_boss", "crank_axis", cone.CRANK_BOSS_START_Z, cone.CRANK_BOSS_END_Z, crank_ends),
        ("cone_boss", "cone_axis", -cone.CONE_BOSS_LENGTH / 2, cone.CONE_BOSS_LENGTH / 2, ("CONE_BOSS_LENGTH", "BLOCK_DIA")),
    ):
        _z_mm(result[name], low, high, _cite(cone, *names), (frame, frames[frame]))
    return result


def _notes_module(stem: str) -> ModuleType:
    name = f"{stem}_notes"
    if importlib.util.find_spec(name) is not None:
        return importlib.import_module(name)
    # These specs supply the native Manufacturing Notes property consumed by
    # the corresponding drawings' property-linked note.
    return {"pivot_shaft": shaft, "cone_pivot_post": cone}[stem]


def _construction(module: ModuleType) -> tuple[str, list[str]]:
    permission = getattr(module, "BUILT_UP_PERMISSION_NOTE", None)
    if permission is None:
        return "one_piece", _cite(module, "DRAWING_NOTES")
    if not isinstance(permission, str) or not permission.strip() or permission not in module.DRAWING_NOTES:
        raise ValueError(f"{module.__name__}.BUILT_UP_PERMISSION_NOTE must be explicit text in DRAWING_NOTES")
    return "built_up_permitted", _cite(module, "DRAWING_NOTES")


def requirement_manifest(stem: str) -> dict[str, Any]:
    """Pure drawing requirement data, before binding it to STEP face names."""
    stem = _stem(stem)
    dashed = stem.replace("_", "-")
    module = {"rocker_arm": rocker, "pivot_shaft": shaft, "cone_pivot_post": cone}[stem]
    features = {"rocker_arm": _rocker_features, "pivot_shaft": _shaft_features, "cone_pivot_post": _cone_features}[stem]()
    notes_module = _notes_module(stem)
    construction, construction_cite = _construction(notes_module)
    row = _config.parts(dashed)
    registry = _config._doc("parts")
    registry_row = registry["parts"][dashed]
    registry_reference = f"harmonic-analyzer/cad/config/parts/{dashed}.yaml:{dashed}"
    defaults_reference = "harmonic-analyzer/cad/config/parts/_defaults.yaml"

    def registry_cite(*keys: str) -> list[str]:
        citations = []
        for key in keys:
            if key in {"material", "material_specification"} and "material_family" in registry_row:
                family = registry_row["material_family"]
                citations += [
                    f"{registry_reference}.material_family",
                    f"{defaults_reference}:material_families.{family}.{key}",
                ]
            elif key in registry_row:
                citations.append(f"{registry_reference}.{key}")
            elif key in registry.get("defaults", {}):
                citations.append(f"{defaults_reference}:defaults.{key}")
        return list(dict.fromkeys(citations))

    general = {
        f"linear_{places}pl": printed_band_mm(places) for places in (1, 2, 3)
    }
    general.update({"angular_deg": float(_config.title_block("angular")["value_deg"]), "drilled_hole_plus": float(_config.title_block("drilled_hole")["plus_mm"]), "drilled_hole_minus": float(_config.title_block("drilled_hole")["minus_mm"]), "edge_break_r": float(_config.title_block("edge_break")["radius_mm"]), "chamfer_max": float(_config.title_block("edge_break")["chamfer_max_mm"])})
    general["cite"] = {
        key: _source_cite(source)
        for key, source in (
            ("linear_1pl", "linear_1pl"), ("linear_2pl", "linear_2pl"),
            ("linear_3pl", "linear_3pl"), ("angular_deg", "angular"),
            ("drilled_hole_plus", "drilled_hole_plus"), ("drilled_hole_minus", "drilled_hole_minus"),
            ("edge_break_r", "edge_break_r"), ("chamfer_max", "chamfer_max"),
        )
    }
    for feature in features.values():
        for key in feature.get("precision", {}) if isinstance(feature.get("precision"), dict) else ():
            if stem == "rocker_arm":
                feature["cite"][f"precision.{key}"] = _cite(
                    rocker_notes, "DRAWING_PRECISION", "DEFAULT_DRAWING_PRECISION",
                )
            if key in feature["cite"] and isinstance(feature.get(key), list) and len(feature[key]) == 2:
                feature["cite"][key] += _source_cite(f"linear_{feature['precision'][key]}pl", "angular", "drilled_hole_plus", "drilled_hole_minus")
        if "finish_ra" in feature:
            feature["cite"]["finish_ra"] += _cite(
                _surface_finish,
                "MACHINED_UM" if feature["finish_ra"] == _surface_finish.MACHINED_UM else "SEAT_UM",
            )
            if isinstance(feature.get("precision"), dict):
                feature["precision"]["finish_ra"] = _finish_precision()
                feature["cite"]["precision.finish_ra"] = _cite(_surface_finish, "ra")
        feature["faces"] = UNKNOWN
    notes = notes_module.DRAWING_NOTES
    frame_cite = _cite(module, "__frame__")
    if stem == "rocker_arm":
        frame_cite += _source_cite("rocker_strap_frame", "rocker_hub_frame")
    elif stem == "cone_pivot_post":
        frame_cite += _source_cite("cone_frame")
    for feature in features.values():
        for key in ("axis", "at", "normal", "plane"):
            if key in feature:
                feature["cite"][key] += frame_cite
        if "z_mm" in feature:
            # Source frames are rigid copies of model; cite each shared fact once.
            feature["cite"]["z_mm"] = list(dict.fromkeys([*feature["cite"]["z_mm"], *frame_cite]))
    frames: dict[str, Any] = {"model": {"origin": [0.0, 0.0, 0.0], "x": [1.0, 0.0, 0.0], "y": [0.0, 1.0, 0.0], "z": [0.0, 0.0, 1.0], "cite": frame_cite}, "setup": UNKNOWN}
    datums: dict[str, Any] = {}
    if stem == "rocker_arm":
        for name, sign in (("A", 1), ("B", -1)):
            frames[name] = {"origin": [0.0, rocker.PIVOT_MID_Y, sign * rocker.HUB_LENGTH / 2], "x": [1.0, 0.0, 0.0], "y": [0.0, float(sign), 0.0], "z": [0.0, 0.0, float(sign)], "binding": UNKNOWN, "cite": _cite(rocker, "PIVOT_MID_Y", "HUB_LENGTH")}
        datums = {
            "A": {"feature": "pivot_bore", "surface": "pivot bore cylinder", "cite": _source_cite("rocker_datum_a")},
            "B": {"feature": "strap_datum_b", "surface": "+Z broad strap face", "cite": _source_cite("rocker_datum_b", "right_view_frame")},
            "C": {"feature": "tip_land_pos_x", "surface": "rod-side (+X) radial tip land", "cite": _source_cite("rocker_datum_c")},
        }
    elif stem == "cone_pivot_post":
        datums = {"A": {"feature": "journal_bore", "surface": "cone journal bore cylinder", "cite": _cite(cone, "PART_DATUMS")}, "B": {"feature": "foot_seat", "surface": "foot seat plane", "cite": _cite(cone, "PART_DATUMS")}}
        frames.update(_cone_source_frames())
    volume = {"volume_mm3": cone.HARVESTED_VOLUME_MM3, "volume_cite": _cite(cone, "HARVESTED_VOLUME_MM3")} if stem == "cone_pivot_post" else {}
    return {
        "part": dashed, "units": "mm", "precision": rocker_notes.DEFAULT_DRAWING_PRECISION if stem == "rocker_arm" else UNKNOWN,
        "step": f"{dashed}.STEP", "step_sha256": UNKNOWN, "construction": construction, **volume, "cite_root": "harmonic-analyzer",
        "cite": {"construction": construction_cite, "units": frame_cite, "precision": _cite(rocker_notes, "DEFAULT_DRAWING_PRECISION") if stem == "rocker_arm" else frame_cite, "frames": frame_cite},
        "drawing": {"number": row["number"], "revision": UNKNOWN, "cite": [*registry_cite("number"), *_source_cite("drawing_revision", "drawing_properties")]},
        "material": {"spec": row.get("material_specification", UNKNOWN), "name": row.get("material", UNKNOWN), "finish": row.get("finish", UNKNOWN), "thickness": UNKNOWN, "cite": registry_cite("material_specification", "material", "finish")},
        "notes": {"manufacturing": notes.splitlines(), "process": row.get("process", UNKNOWN), "edge_break": f"REMOVE BURRS AND BREAK SHARP EDGES {_config.title_block('edge_break')['display_r']} OR CHAMFER {_config.title_block('edge_break')['display_chamfer']} MAX", "cite": [*registry_cite("process"), *_source_cite("edge_break_display_r", "edge_break_display_chamfer"), *_cite(notes_module, "DRAWING_NOTES")]},
        "general_tolerances": general, "frames": frames, "datums": datums, "features": features,
    }


def _toml(data: dict[str, Any]) -> str:
    # All manifest containers are dictionaries or scalar/list values; inline
    # tables retain per-value citations without a TOML runtime dependency.
    def value(item: Any) -> str:
        if isinstance(item, str):
            return json.dumps(item, ensure_ascii=False)
        if isinstance(item, bool):
            return "true" if item else "false"
        if isinstance(item, (int, float)):
            if not math.isfinite(item):
                raise ValueError("non-finite manifest number")
            return repr(item)
        if isinstance(item, (list, tuple)):
            return "[" + ", ".join(value(entry) for entry in item) + "]"
        if isinstance(item, dict):
            return "{ " + ", ".join(f"{value(key)} = {value(entry)}" for key, entry in item.items()) + " }"
        raise TypeError(f"unsupported TOML value: {type(item).__name__}")
    lines = ["# Generated from CAD drawing contracts and adjacent raw STEP bytes; do not hand edit."]
    def table(node: dict[str, Any], path: tuple[str, ...] = ()) -> None:
        if path:
            lines.extend(("", "[" + ".".join(value(key) for key in path) + "]"))
        for key, item in node.items():
            if not isinstance(item, dict) or key in {"cite", "precision", "plane", "bounds"}:
                lines.append(f"{value(key)} = {value(item)}")
        for key, item in node.items():
            if isinstance(item, dict) and key not in {"cite", "precision", "plane", "bounds"}:
                table(item, (*path, key))
    table(data)
    return "\n".join(lines) + "\n"


def write_manifest(stem: str, step: Path, *, revision: str) -> Path:
    """Bind all labelled STEP faces and write the adjacent requirements TOML."""
    from prechips.model import Features

    from _export_feature_faces import step_face_sets

    stem = _stem(stem)
    step = Path(step)
    content = step.read_bytes()
    manifest = requirement_manifest(stem)
    selectors = feature_selectors(stem)
    if selectors.keys() != manifest["features"].keys():
        raise ValueError(f"feature selector/requirement domains differ: {stem}")
    faces = step_face_sets(content.decode("latin-1"), selectors.keys())
    step_cite = f"harmonic-analyzer/cad/out/features/{stem}/{step.name}"
    for name, feature in manifest["features"].items():
        feature["faces"] = faces[name]
        feature["cite"]["faces"] = [step_cite]
    manifest["step"] = step.name
    manifest["step_sha256"] = hashlib.sha256(content).hexdigest()
    manifest["cite"]["step_sha256"] = [step_cite]
    manifest["drawing"]["revision"] = revision
    Features.model_validate(manifest)
    path = step.with_name("features.toml")
    partial = path.with_suffix(".toml.partial")
    partial.write_text(_toml(manifest), encoding="utf-8", newline="\n")
    partial.replace(path)
    return path
