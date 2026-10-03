"""Export drawing requirements from pure CAD contracts and certified STEP bytes.

No SolidWorks document is opened or saved. ``export_models --features`` writes
each part's adjacent STEP and ``neutral.json`` receipt, then calls
``write_manifests(parts, out=CAD_OUT)`` to write ``features/<stem>/features.toml``.
The standalone CLI accepts underscore or dashed stems and requires those
per-part receipts, not a full-release certificate.

Construction is one_piece unless a <stem>_notes module explicitly supplies
BUILT_UP_PERMISSION_NOTE, whose exact, nonempty text must occur in DRAWING_NOTES.
A material/process alternative (casting or solid stock) is not built-up permission.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import importlib.util
import json
import math
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable

import _config
import _hole_spec
import _surface_finish
import cone_gear_shaft_spec as cone_shaft
import cone_pivot_post_spec as cone
import pivot_bracket_spec as bracket
import pivot_shaft_spec as shaft
import rocker_arm_notes as rocker_notes
import rocker_arm_spec as rocker
import rocker_bank_layout as bank
from _gtol_spec import CylinderFace, FaceSpec, PlanarFace, SphereFace
from _printed_tolerance import printed_band_mm, printed_deviations

SUPPORTED_PARTS = ("rocker_arm", "pivot_shaft", "pivot_bracket", "cone_pivot_post")
REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "cad" / "out"
UNKNOWN = "unknown"


def source_paths() -> tuple[Path, ...]:
    """Source/citation inputs not visible through ordinary import traversal."""
    from _buildgraph import module_deps_of

    modules = (
        _config, _hole_spec, _surface_finish, cone_shaft, cone, bracket,
        shaft, rocker_notes, rocker, bank,
    )
    paths = {Path(module.__file__).resolve() for module in modules}
    script = Path(__file__).resolve()
    paths.add(script)
    paths.update(Path(path).resolve() for path in module_deps_of(script))
    # Imported geometry contracts also read machine/fits/material documents
    # through dynamic _config accessors. Conservatively include those YAML
    # inputs rather than omitting a dimension-bearing indirect read.
    paths.update(path.resolve() for path in _config.CONFIG_DIR.rglob("*.yaml"))
    for stem in SUPPORTED_PARTS:
        note_spec = importlib.util.find_spec(f"{stem}_notes")
        if note_spec is not None and note_spec.origin is not None:
            paths.add(Path(note_spec.origin).resolve())
    paths.update(REPO / "cad" / "scripts" / name for name in (
        "_common.py", "_drawing_common.py", "draw_rocker_arm.py", "build_rocker_arm.py",
        "draw_pivot_shaft.py", "build_pivot_shaft.py",
        "draw_cone_pivot_post.py", "build_cone_pivot_post.py", "build_pivot_bracket.py",
    ))
    return tuple(sorted(paths))


def feature_sources_sha256() -> str:
    """Bind requirements/citations to raw canonical source bytes, not mtimes.

    YAML comments can move a citation even without changing geometry; they
    therefore remain in this identity. A release-only revision bump is excluded
    because the certificate independently preserves the exported revision.
    """
    release = (_config.CONFIG_DIR / "release.yaml").resolve()
    digest = hashlib.sha256()
    for path in sorted(set(source_paths()) - {release}):
        content = path.read_bytes()
        # Match the shared source-cache Git text heuristic without importing
        # dodo or its runtime dependencies into this portable manifest reader.
        if b"\0" not in content[:8000]:
            content = content.replace(b"\r\n", b"\n")
        digest.update(path.relative_to(REPO).as_posix().encode("utf-8") + b"\0")
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


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
            "strap_faces": tuple(PlanarFace((0, 0, sign), rocker.ARM_THICKNESS / 2) for sign in (-1, 1)),
            "top_edge": (CylinderFace(2 * rocker.R_TOP),),
            "profile_outer": (CylinderFace(2 * rocker.R_BOTTOM), *right, *tips),
        }
    if stem == "pivot_shaft":
        north = -shaft.JOURNAL_LENGTH
        south = shaft.SHOULDER_SOUTH_Z_MM
        return {
            "pivot_bearing": (shaft.SURFACE_FINISHES[0].face,),
            "pivot_journal": (shaft.SURFACE_FINISHES[1].face,),
            "shoulder_od": (CylinderFace(shaft.SHOULDER_DIA),),
            "shoulder_thrust": (
                PlanarFace((0, 0, 1), north), shaft.SURFACE_FINISHES[2].face,
            ),
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
    if stem == "pivot_bracket":
        return {
            "shaft_bore": (CylinderFace(bracket.BORE_DIA),),
            "foot": (
                PlanarFace((0, -1, 0), 0),
                PlanarFace((0, 1, 0), bracket.FOOT_H),
                *(PlanarFace((sign, 0, 0), bracket.FOOT_W / 2) for sign in (-1, 1)),
                PlanarFace((0, 0, 1), bracket.FOOT_Z1),
            ),
            "ear": (
                CylinderFace(bracket.EAR_W),
                *(PlanarFace((sign, 0, 0), bracket.EAR_W / 2) for sign in (-1, 1)),
                *(PlanarFace((0, 0, sign), bracket.EAR_T / 2) for sign in (-1, 1)),
            ),
            **{
                f"hold_down_{index}": (CylinderFace(bracket.HOLE_DIA, contains_z_mm=z),)
                for index, z in enumerate(bracket.HOLE_Z, start=1)
            },
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
            "lower_z": (-rocker.ARM_THICKNESS / 2, ("ARM_THICKNESS",)), "datum": ("B", ("ARM_THICKNESS",)),
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
        "profile_outer": _feature(rocker, "profile", ["bottom_radius", "bottom_arc_len", "tip_land", "land_angle_deg", "mirror_symmetric"], {
            "bottom_radius": (_band(rocker.R_BOTTOM, p), ("R_BOTTOM",)),
            "bottom_radius_nominal": (rocker.R_BOTTOM, ("R_BOTTOM",)),
            "arc_centre": ([0.0, rocker.CENTER_Y, 0.0], ("CENTER_Y",)), "top_edge_feature": ("top_edge", ("R_TOP",)),
            "bottom_arc_len": (_band(rocker.BOT_ARC_LEN, p), ("BOT_ARC_LEN",)),
            "tip_land": (_band(rocker.TIP_FACE, p), ("TIP_FACE",)),
            "land_angle_deg": (UNKNOWN, ("TIP_FACE",)),
            "land_angle_nominal_deg": (land_angle, ("TOP_END_X", "TOP_END_Y", "ROD_TIP_X", "TIP_FACE", "R_TOP", "CENTER_Y")),
            "mirror_symmetric": (True, ("R_BOTTOM",)), "depth_ref": (rocker.ARM_DEPTH, ("ARM_DEPTH",)),
            "bottom_end": (list(bottom), ("BOT_END_X", "R_BOTTOM", "CENTER_Y")),
            "radial_tip_end": (list(tip), ("ROD_TIP_X", "TOP_END_Y", "TIP_FACE", "R_TOP", "CENTER_Y")),
            "datum": ("C", ("TIP_FACE",)),
        }, precision={"bottom_radius": p, "bottom_arc_len": p, "tip_land": p, "land_angle_deg": UNKNOWN}),
    }
    notes_cite = _cite(rocker_notes, "DRAWING_NOTES")
    for name in ("pivot_bore", "strap_faces", "top_edge", "profile_outer", "hub_od"):
        for key in result[name]["cite"]:
            result[name]["cite"][key] += notes_cite
    result["hub_od"]["cite"]["coaxiality_dia"] = _cite(rocker_notes, "HUB_COAXIALITY_DIA", "DRAWING_NOTES")
    result["rod_hole"]["cite"]["nominal_dia"] += _cite(_hole_spec, "NUMBER_DRILL_MM")
    result["rod_hole"]["cite"]["dia"] += _cite(_hole_spec, "NUMBER_DRILL_MM")
    result["rod_hole"]["cite"]["dia"] += [
        "harmonic-analyzer/cad/scripts/build_rocker_arm.py:510-516",
        "harmonic-analyzer/cad/scripts/draw_rocker_arm.py:435-445",
        "harmonic-analyzer/cad/scripts/_drawing_common.py:1860-1874,1901,1949-1966",
    ]
    result["rod_hole"]["cite"]["position_datums"] = ["harmonic-analyzer/cad/scripts/draw_rocker_arm.py:539-549"]
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
    result["shoulder_thrust"] = _feature(shaft, "face", ["length", "finish_ra"], {
        "length": (_band(shaft.SHOULDER_LENGTH, p["ShoulderLength"]), ("SHOULDER_LENGTH",)),
        "length_nominal": (shaft.SHOULDER_LENGTH, ("SHOULDER_LENGTH",)),
        "upper_z": (-shaft.JOURNAL_LENGTH, ("JOURNAL_LENGTH",)),
        "lower_z": (shaft.SHOULDER_SOUTH_Z_MM, ("SHOULDER_SOUTH_Z_MM",)),
        "finish_ra": (_surface_finish.MACHINED_UM, ("SURFACE_FINISHES",)),
        "note": ("Ra applies only to the south shoulder face; the north face only seats on the ear.", ("SURFACE_FINISHES",)),
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
            "base_z": (z, ("__frame__",)), "note": (shaft.DOME_CALLOUT, ("DOME_CALLOUT",)),
        }, precision={"height": p["DomeHeight"]})
    result["south_dome"]["cite"]["base_z"] = _cite(bank, "PIVOT_SHAFT_LENGTH")
    return result


def _bracket_features() -> dict[str, dict[str, Any]]:
    # There is no curated bracket drawing or marked dimension contract. Do not
    # turn geometry/design-stack assumptions into invented acceptance limits.
    result = {
        "shaft_bore": _feature(bracket, "hole", UNKNOWN, {
            "at": ([0.0, bracket.BORE_H, 0.0], ("BORE_H",)), "axis": ([0.0, 0.0, 1.0], ("__frame__",)),
            "nominal_dia": (bracket.BORE_DIA, ("BORE_DIA",)), "dia": (UNKNOWN, ("BORE_DIA",)),
            "thru": (True, ("BORE_DIA", "EAR_T")),
        }),
        "foot": _feature(bracket, "profile", UNKNOWN, {
            "nominal_width": (bracket.FOOT_W, ("FOOT_W",)), "width": (UNKNOWN, ("FOOT_W",)),
            "nominal_height": (bracket.FOOT_H, ("FOOT_H",)), "height": (UNKNOWN, ("FOOT_H",)),
            "nominal_length": (bracket.FOOT_LEN, ("FOOT_LEN",)), "length": (UNKNOWN, ("FOOT_LEN",)),
        }),
        "ear": _feature(bracket, "profile", UNKNOWN, {
            "nominal_width": (bracket.EAR_W, ("EAR_W",)), "width": (UNKNOWN, ("EAR_W",)),
            "nominal_thickness": (bracket.EAR_T, ("EAR_T",)), "thickness": (UNKNOWN, ("EAR_T",)),
            "nominal_radius": (bracket.EAR_ARCH_R, ("EAR_ARCH_R",)), "radius": (UNKNOWN, ("EAR_ARCH_R",)),
        }),
    }
    for index, z in enumerate(bracket.HOLE_Z, start=1):
        result[f"hold_down_{index}"] = _feature(bracket, "hole", UNKNOWN, {
            "at": ([0.0, bracket.FOOT_H, z], ("FOOT_H", "HOLE_Z")), "axis": ([0.0, -1.0, 0.0], ("__frame__",)),
            "nominal_dia": (bracket.HOLE_DIA, ("HOLE_DIA",)), "dia": (UNKNOWN, ("HOLE_DIA",)),
            "thru": (bracket.HOLD_DOWN_HOLE_SPEC.end == "through_all", ("HOLD_DOWN_HOLE_SPEC",)),
            "station_nominal": (z, ("HOLE_Z",)), "station": (UNKNOWN, ("HOLE_Z",)),
        })
    for feature in result.values():
        feature["precision"] = UNKNOWN
        feature["note"] = "No curated manufacturing drawing exists; nominal model geometry is not a tolerance."
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
    for side, x, dim in (("west", -cone.ATTACHMENT_X, "MountWestX"), ("east", cone.ATTACHMENT_X, "MountEastX")):
        name = f"mount_{side}"
        result[name] = _feature(cone, "hole", ["dia", "thru", "station"], {
            "at": ([x, cone.BLOCK_HEIGHT, 0.0], ("ATTACHMENT_X", "BLOCK_HEIGHT")), "axis": ([0.0, -1.0, 0.0], ("__frame__",)),
            "dia": (_drilled_band(cone.ATTACHMENT_THRU_DIA, p[dim]), ("ATTACHMENT_THRU_DIA",)),
            "nominal_dia": (cone.ATTACHMENT_THRU_DIA, ("ATTACHMENT_THRU_DIA",)), "thru": (True, ("ATTACHMENT_THRU_DIA",)),
            "station": (_band(cone.ATTACHMENT_X, p[dim]), ("ATTACHMENT_X",)), "station_nominal": (x, ("ATTACHMENT_X",)),
        }, precision={"dia": p[dim], "station": p[dim]})
        result[f"{name}_counterbore"] = _feature(cone, "counterbore", ["dia", "depth"], {
            "parent": (name, ("ATTACHMENT_THRU_DIA",)),
            "dia": (_band(cone.ATTACHMENT_CBORE_DIA, p[dim]), ("ATTACHMENT_CBORE_DIA",)), "nominal_dia": (cone.ATTACHMENT_CBORE_DIA, ("ATTACHMENT_CBORE_DIA",)),
            "depth": (_band(cone.ATTACHMENT_CBORE_DEPTH, p[dim]), ("ATTACHMENT_CBORE_DEPTH",)), "depth_ref": (cone.ATTACHMENT_CBORE_DEPTH, ("ATTACHMENT_CBORE_DEPTH",)),
        }, precision={"dia": p[dim], "depth": p[dim]})
        result[name]["cite"]["dia"] += [
            "harmonic-analyzer/cad/scripts/build_cone_pivot_post.py:116-123",
            "harmonic-analyzer/cad/scripts/draw_cone_pivot_post.py:1269-1280",
            "harmonic-analyzer/cad/scripts/_drawing_common.py:1860-1874,1901,1949-1966",
        ]
    return result


def _construction(stem: str) -> tuple[str, list[str]]:
    name = f"{stem}_notes"
    if importlib.util.find_spec(name) is None:
        return "one_piece", ["harmonic-analyzer/cad/scripts/export_features.py:1"]
    module = importlib.import_module(name)
    permission = getattr(module, "BUILT_UP_PERMISSION_NOTE", None)
    if permission is None:
        return "one_piece", _cite(module, "DRAWING_NOTES")
    if not isinstance(permission, str) or not permission.strip() or permission not in getattr(module, "DRAWING_NOTES", ""):
        raise ValueError(f"{name}.BUILT_UP_PERMISSION_NOTE must be explicit text in DRAWING_NOTES")
    return "built_up_permitted", _cite(module, "BUILT_UP_PERMISSION_NOTE", "DRAWING_NOTES")


def requirement_manifest(stem: str) -> dict[str, Any]:
    """Pure requirement data, before binding it to certified STEP face names."""
    stem = _stem(stem)
    dashed = stem.replace("_", "-")
    module = {"rocker_arm": rocker, "pivot_shaft": shaft, "pivot_bracket": bracket, "cone_pivot_post": cone}[stem]
    features = {"rocker_arm": _rocker_features, "pivot_shaft": _shaft_features, "pivot_bracket": _bracket_features, "cone_pivot_post": _cone_features}[stem]()
    construction, construction_cite = _construction(stem)
    row = _config.parts(dashed)
    registry_path = _config.CONFIG_DIR / "parts" / f"{dashed}.yaml"
    registry_cite = (
        f"harmonic-analyzer/cad/config/parts/{dashed}.yaml:"
        f"1-{len(registry_path.read_text(encoding='utf-8').splitlines())}"
    )
    general = {
        f"linear_{places}pl": printed_band_mm(places) for places in (1, 2, 3)
    }
    general.update({"angular_deg": float(_config.title_block("angular")["value_deg"]), "drilled_hole_plus": float(_config.title_block("drilled_hole")["plus_mm"]), "drilled_hole_minus": float(_config.title_block("drilled_hole")["minus_mm"]), "edge_break_r": float(_config.title_block("edge_break")["radius_mm"]), "chamfer_max": float(_config.title_block("edge_break")["chamfer_max_mm"])})
    general["cite"] = {key: f"harmonic-analyzer/cad/config/title_block.yaml:{line}" for key, line in (("linear_1pl", 25), ("linear_2pl", 26), ("linear_3pl", 27), ("angular_deg", 28), ("drilled_hole_plus", 66), ("drilled_hole_minus", 66), ("edge_break_r", 45), ("chamfer_max", 45))}
    for feature in features.values():
        for key in feature.get("precision", {}) if isinstance(feature.get("precision"), dict) else ():
            if stem == "rocker_arm":
                feature["cite"][f"precision.{key}"] = _cite(
                    rocker_notes, "DRAWING_PRECISION", "DEFAULT_DRAWING_PRECISION",
                )
            if key in feature["cite"] and isinstance(feature.get(key), list) and len(feature[key]) == 2:
                feature["cite"][key].append("harmonic-analyzer/cad/config/title_block.yaml:25-28,66")
        if "finish_ra" in feature:
            feature["cite"]["finish_ra"] += _cite(
                _surface_finish,
                "MACHINED_UM" if feature["finish_ra"] == _surface_finish.MACHINED_UM else "SEAT_UM",
            )
            if isinstance(feature.get("precision"), dict):
                feature["precision"]["finish_ra"] = _finish_precision()
                feature["cite"]["precision.finish_ra"] = _cite(_surface_finish, "ra")
        feature["faces"] = UNKNOWN
    notes_module = rocker_notes if stem == "rocker_arm" else module
    notes = getattr(notes_module, "DRAWING_NOTES", None)
    frame_cite = _cite(module, "__frame__")
    if stem == "rocker_arm":
        frame_cite += [
            "harmonic-analyzer/cad/scripts/build_rocker_arm.py:396-403",
            "harmonic-analyzer/cad/scripts/build_rocker_arm.py:424-434",
        ]
    elif stem == "cone_pivot_post":
        frame_cite += ["harmonic-analyzer/cad/scripts/build_cone_pivot_post.py:10-16,372-395"]
    for feature in features.values():
        for key in ("axis", "at", "normal", "plane"):
            if key in feature:
                feature["cite"][key] += frame_cite
    frames: dict[str, Any] = {"model": {"origin": [0.0, 0.0, 0.0], "x": [1.0, 0.0, 0.0], "y": [0.0, 1.0, 0.0], "z": [0.0, 0.0, 1.0], "cite": frame_cite}, "setup": UNKNOWN}
    datums: dict[str, Any] | str = UNKNOWN if stem == "pivot_bracket" else {}
    if stem == "rocker_arm":
        for name, sign in (("A", 1), ("B", -1)):
            frames[name] = {"origin": [0.0, rocker.PIVOT_MID_Y, sign * rocker.HUB_LENGTH / 2], "x": [1.0, 0.0, 0.0], "y": [0.0, float(sign), 0.0], "z": [0.0, 0.0, float(sign)], "binding": UNKNOWN, "cite": _cite(rocker, "PIVOT_MID_Y", "HUB_LENGTH")}
        datums = {
            "A": {"feature": "pivot_bore", "surface": "pivot bore cylinder", "cite": "harmonic-analyzer/cad/scripts/draw_rocker_arm.py:476-495"},
            "B": {"feature": "strap_faces", "surface": UNKNOWN, "cite": "harmonic-analyzer/cad/scripts/draw_rocker_arm.py:510-529"},
            "C": {"feature": "profile_outer", "surface": "rod-side (+X) radial tip land", "cite": "harmonic-analyzer/cad/scripts/draw_rocker_arm.py:530-538"},
        }
    elif stem == "cone_pivot_post":
        datums = {"A": {"feature": "journal_bore", "surface": "cone journal bore cylinder", "cite": _cite(cone, "PART_DATUMS")}, "B": {"feature": "foot_seat", "surface": "foot seat plane", "cite": _cite(cone, "PART_DATUMS")}}
    return {
        "part": dashed, "units": "mm", "precision": rocker_notes.DEFAULT_DRAWING_PRECISION if stem == "rocker_arm" else UNKNOWN,
        "step": f"{dashed}.STEP", "step_sha256": UNKNOWN, "construction": construction, "cite_root": "harmonic-analyzer",
        "cite": {"construction": construction_cite, "units": frame_cite, "precision": _cite(rocker_notes, "DEFAULT_DRAWING_PRECISION") if stem == "rocker_arm" else frame_cite, "frames": frame_cite},
        "drawing": {"number": row["number"], "revision": UNKNOWN, "cite": [registry_cite, "harmonic-analyzer/cad/config/release.yaml:1-3", "harmonic-analyzer/cad/scripts/_common.py:1751-1765"]},
        "material": {"spec": row.get("material_specification", UNKNOWN), "name": row.get("material", UNKNOWN), "finish": row.get("finish", UNKNOWN), "thickness": UNKNOWN, "cite": [registry_cite, "harmonic-analyzer/cad/config/parts/_defaults.yaml:21-27"]},
        "notes": {"manufacturing": notes.splitlines() if notes is not None else UNKNOWN, "process": row.get("process", UNKNOWN), "edge_break": f"REMOVE BURRS AND BREAK SHARP EDGES {_config.title_block('edge_break')['display_r']} OR CHAMFER {_config.title_block('edge_break')['display_chamfer']} MAX", "cite": ([registry_cite, "harmonic-analyzer/cad/config/title_block.yaml:43-45"] + (_cite(notes_module, "DRAWING_NOTES") if notes else []))},
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
    lines = ["# Generated from CAD drawing contracts and certified STEP bytes; do not hand edit."]
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


def _certified_bytes(path: Path, record: Any) -> bytes:
    if not isinstance(record, dict) or record.get("path") != path.name:
        raise ValueError(f"certified feature bundle path differs: {path}")
    content = path.read_bytes()
    if (
        not content
        or type(record.get("bytes")) is not int
        or record["bytes"] != len(content)
        or record.get("sha256") != hashlib.sha256(content).hexdigest()
    ):
        raise ValueError(f"certified feature bundle bytes/SHA-256 differ: {path}; rerun --features")
    return content


def write_manifests(parts: Iterable[str] | None = None, *, out: Path | None = None) -> list[Path]:
    """Write adjacent manifests only after every requested bundle validates.

    Receipts bind the current requirement sources and exact raw STEP bytes.
    Exporter/native identities are recorded by the producer; checking them
    never imports COM or requires native files outside the portable bundle.
    A final receipt's manifest must still be its certified bytes.
    """
    from _export_feature_faces import step_face_sets

    output = OUT if out is None else Path(out)
    selected = SUPPORTED_PARTS if parts is None else tuple(dict.fromkeys(_stem(stem) for stem in parts))
    if not selected:
        return []
    source_digest = feature_sources_sha256()
    pending = []
    for stem in selected:
        dashed = stem.replace("_", "-")
        bundle = output / "features" / stem
        receipt_path = bundle / "neutral.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if not isinstance(receipt, dict) or receipt.get("schema") != "harmonic-analyzer/features-neutral@1":
            raise ValueError(f"unsupported feature neutral receipt schema: {stem}; rerun --features")
        if receipt.get("stem") != stem:
            raise ValueError(f"feature neutral receipt stem differs: {stem}")
        exporter = receipt.get("exporter")
        native_digest = receipt.get("native_sha256")
        if not isinstance(exporter, str) or not exporter.strip():
            raise ValueError(f"feature neutral receipt exporter identity is missing: {stem}")
        if (
            not isinstance(native_digest, str)
            or len(native_digest) != 64
            or any(char not in "0123456789abcdef" for char in native_digest)
        ):
            raise ValueError(f"feature neutral receipt native SHA-256 is invalid: {stem}")
        if receipt.get("feature_sources_sha256") != source_digest:
            raise ValueError(f"feature neutral requirement sources changed: {stem}; rerun --features")
        revision = receipt.get("drawing_revision", UNKNOWN)
        if not isinstance(revision, str) or not revision.strip():
            raise ValueError(f"feature neutral receipt drawing revision is invalid: {stem}")
        path = bundle / f"{dashed}.STEP"
        record = receipt.get("step")
        content = _certified_bytes(path, record)
        manifest = requirement_manifest(stem)
        selectors = feature_selectors(stem)
        if selectors.keys() != manifest["features"].keys():
            raise ValueError(f"feature selector/requirement domains differ: {stem}")
        faces = step_face_sets(content.decode("latin-1"), selectors.keys())
        used = set()
        for name, feature in manifest["features"].items():
            labels = faces.get(name)
            if not labels or used.intersection(labels):
                raise ValueError(f"missing or overlapping STEP face set: {stem}.{name}")
            used.update(labels)
            feature["faces"] = labels
            feature["cite"]["faces"] = [
                f"harmonic-analyzer/cad/out/features/{stem}/{dashed}.STEP",
                f"harmonic-analyzer/cad/out/features/{stem}/neutral.json",
            ]
        manifest["step_sha256"] = record["sha256"]
        manifest["cite"]["step_sha256"] = [
            f"harmonic-analyzer/cad/out/features/{stem}/neutral.json",
            f"harmonic-analyzer/cad/out/features/{stem}/{dashed}.STEP",
        ]
        if stem != "pivot_bracket":
            manifest["drawing"]["revision"] = revision
            manifest["drawing"]["cite"].append(f"harmonic-analyzer/cad/out/features/{stem}/neutral.json")
        manifest_path = bundle / "features.toml"
        manifest_bytes = _toml(manifest).encode("utf-8")
        if "features" in receipt and _certified_bytes(manifest_path, receipt["features"]) != manifest_bytes:
            raise ValueError(f"certified feature manifest differs from receipt requirements: {stem}; rerun --features")
        pending.append((manifest_path, manifest_bytes))
    for path, content in pending:
        partial = path.with_suffix(".toml.partial")
        partial.write_bytes(content)
        partial.replace(path)
    return [path for path, _content in pending]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parts", nargs="+", help="supported part stems (space- or comma-separated)")
    args = parser.parse_args(argv)
    parts = None
    if args.parts is not None:
        parts = [_stem(part) for item in args.parts for part in item.split(",")]
    for path in write_manifests(parts):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
