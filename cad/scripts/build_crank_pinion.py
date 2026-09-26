r"""DIAG v3 (#906, NOT FOR MERGE) -- reproduction script: crank pinion (book ch. 11/12, pp. 16, 19, 20).

The pinion on the crankshaft that meshes the dark steel crank-drive gear
at the cone set's large end (`build_crank_drive_gear.py`), implementing
the book-stated 4:1 crank-to-cone reduction (p. 16). Tooth count/DP per
the Appendix C #9 split, with DP 25.7311 fixed by the manually
rederived v2 post's cast-in crank axis. A plain straight spur
with a root-relieved floor; the crossed-mesh accommodation lives on the
64T (see its docstring for the full rederivation). On its outboard face
a plain hub boss at the tooth root (ch12 p.19 page002_img02 / img06)
carries the 1/8 in retention pin that keys the pinion to the crankshaft
through a match-drilled radial cross-hole (crank_pinion_spec).

Dimensions: cad/config/dimensions.yaml ch12 crank-drive gear row +
Appendix C #9. Face slightly wider than the drive gear's (meshing-pair
practice, axial alignment slack).

Layout: gear axis = Z through the origin, teeth z = 0..10.4 mm, boss
z = 10.4..24.9 mm, pin cross-hole along X at z = 17.65 (W15).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_pinion.py
"""

from __future__ import annotations

import json
import math
import sys

import _telemetry
from _common import (
    SketchDims,
    _feature_by_name,
    _early_bound,
    _read_member,
    discard_open_documents,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    name_bore_axis,
    check,
    define_circle,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
)
from _drawing_marks import (
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _gear import build_fixed_gear, volume_check
from _holes import cross_hole_volume_mm3, wizard_hole_on_cylinder
from _part_pmi import author_part_pmi
from crank_pinion_spec import (
    BORE_DIA,
    BORE_DIA_BAND,
    BOSS_DIA,
    BOSS_LENGTH,
    DIAMETRAL_PITCH,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FACE_WIDTH,
    GEAR_DATA,
    OUTSIDE_DIA,
    OVERALL_LENGTH,
    PIN_DIA,
    PIN_HOLE_SPEC,
    PIN_STATION,
    PRESSURE_ANGLE_DEG,
    SURFACE_FINISHES,
)

PART_NAME = "crank-pinion"
MATERIAL = "Plain Carbon Steel"  # steel like its mate (p.19/20)

TEETH = 16  # DIMENSIONS.md ch12 / Appendix C #9 estimate (low)
DP = DIAMETRAL_PITCH  # the 64T's normal-plane cutter, cut square (crank_pinion_spec)
PA_DEG = PRESSURE_ANGLE_DEG
# FACE_WIDTH (10.4: spans the 64T row north of the v2 crank boss) lives in
# crank_pinion_spec with the boss and pin it sizes; build_drive_train_assembly's
# PINION_FACE asserts equality. (The old 12.0 "slightly wider than the drive
# gear's 10" was a low-confidence read; 11.0 fit the line-of-centres overhang
# model but grazed the true rim minimum at the tight 2026-07-14 fit.)
BORE_DIAMETER = BORE_DIA  # the crankshaft's Ø9.0 pinion seat (crank_pinion_spec)




async def _boss_standard(adapter, volume: float) -> tuple[float, list]:
    from solidworks_mcp.adapters.base import RevolveParameters

    drive_jobs: list[tuple[str, str]] = []
    boss = SketchDims()
    check("create_sketch boss", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    boss_axis = check(
        "boss axis centerline",
        await adapter.add_centerline(0.0, 0.0, -OVERALL_LENGTH, 0.0),
    )
    boss_pts = [
        (0.0, 0.0),
        (0.0, BOSS_DIA / 2.0),
        (-OVERALL_LENGTH, BOSS_DIA / 2.0),
        (-OVERALL_LENGTH, 0.0),
    ]
    boss_lines = await add_line_chain(adapter, boss_pts)
    # Construction-only side-view witnesses for the other two turned
    # diameters.  The gear helper's blank circle and the bore circle must stay
    # on Front to create their features, but rule 2 permits a construction
    # reference sketch whose own driving dimension carries the printed value.
    # Keeping the witnesses in this Right-plane profile lets every turned
    # diameter import natively beside its axial extent without changing the
    # solid or showing hidden bore lines.
    outside_ref = check(
        "outside-diameter reference line",
        await adapter.add_line(0.0, OUTSIDE_DIA / 2.0, -FACE_WIDTH, OUTSIDE_DIA / 2.0),
    )
    bore_ref = check(
        "bore-diameter reference line",
        await adapter.add_line(0.0, BORE_DIAMETER / 2.0, -OVERALL_LENGTH, BORE_DIAMETER / 2.0),
    )
    set_sketch_direct_db(adapter, False)
    for line in (outside_ref, bore_ref):
        segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
        segment.ConstructionGeometry = True
        if not bool(segment.ConstructionGeometry):
            raise RuntimeError(f"{line}: failed to become construction geometry")
    for i, line in enumerate(boss_lines):
        (_, y1), (_, y2) = boss_pts[i], boss_pts[(i + 1) % len(boss_lines)]
        direction = "horizontal" if y1 == y2 else "vertical"
        check(
            f"boss {direction} {line}",
            await adapter.add_sketch_constraint(line, None, direction),
        )
    for label, line in (
        ("outside-diameter reference", outside_ref),
        ("bore-diameter reference", bore_ref),
    ):
        check(
            f"{label} horizontal",
            await adapter.add_sketch_constraint(line, None, "horizontal"),
        )
        check(
            f"{label} starts at faced end",
            await adapter.add_sketch_constraint(
                f"{line}.start", f"{boss_lines[0]}.start", "vertical_points"
            ),
        )
    check(
        "bore-diameter reference ends at boss end",
        await adapter.add_sketch_constraint(
            f"{bore_ref}.end", f"{boss_lines[2]}.end", "vertical_points"
        ),
    )
    boss_outline = boss_lines[1]
    await dimension_between(
        adapter,
        f"{boss_outline}.start",
        f"{boss_outline}.end",
        "horizontal_distance",
        OVERALL_LENGTH,
        "boss OverallLength",
    )
    boss.record("OverallLength", '"FaceWidth" + "BossLength"')
    await add_diametric_linear_dimension(
        adapter,
        boss_axis,
        boss_outline,
        (-OVERALL_LENGTH / 2.0, BOSS_DIA / 2.0 + 5.0),
        "BossDia",
    )
    boss.record("BossDia", '"BossDia"')
    # The outside-diameter witness stops at the tooth face, so its axial
    # attachment says which cylinder the diameter belongs to.  Its span is
    # definition-only and therefore deliberately stays auto-named/unmarked.
    await dimension_between(
        adapter,
        f"{outside_ref}.start",
        f"{outside_ref}.end",
        "horizontal_distance",
        FACE_WIDTH,
        "outside-diameter reference span",
    )
    boss.record(None, None)
    await add_diametric_linear_dimension(
        adapter,
        boss_axis,
        f"{outside_ref}.start",
        (-FACE_WIDTH / 2.0, OUTSIDE_DIA / 2.0 + 5.0),
        "OutsideDia",
    )
    boss.record("OutsideDia", '"OutsideDia"')
    await add_diametric_linear_dimension(
        adapter,
        boss_axis,
        f"{bore_ref}.start",
        (-OVERALL_LENGTH / 2.0, BORE_DIAMETER / 2.0 + 3.0),
        "BoreDia",
    )
    boss.record("BoreDia", '"BoreDia"')
    await anchor_point_to_origin(
        adapter, f"{boss_lines[0]}.start", 0.0, 0.0, "boss anchor"
    )
    await ensure_fully_defined(adapter, "boss sketch")
    check("exit_sketch boss", await adapter.exit_sketch())
    name_last_feature(adapter, "BossProfile")
    drive_jobs += boss.apply(adapter, "BossProfile")
    check(
        "revolve boss", await adapter.create_revolve(RevolveParameters(angle=360.0))
    )
    name_last_feature(adapter, "Boss")
    v_boss = math.pi * (BOSS_DIA / 2.0) ** 2 * BOSS_LENGTH
    volume = await volume_check(adapter, "hub boss", volume + v_boss, 0.01 * v_boss)
    return volume, drive_jobs


async def _pin_hole(adapter, volume: float) -> tuple[float, list]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    drive_jobs: list[tuple[str, str]] = []
    # Retention-pin cross-hole (crank_pinion_spec): a native 1/8 in drill
    # radially through the boss wall on local -X at the boss's mid-length,
    # through-all so it exits the far wall too (the pin is flush both sides).
    # The station rides an offset plane whose distance is the printed
    # PinStation dimension; the Top plane pins the azimuth. Match-drilled at
    # assembly with the crankshaft, whose own hole carries the mesh clocking.
    check(
        "create_plane PinStationPlane",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=PIN_STATION
            )
        ),
    )
    name_last_feature(adapter, "PinStationPlane")
    drive_jobs += [
        (
            name_dimensions(adapter, "PinStationPlane", ["PinStation"])[0],
            '"FaceWidth" + "BossLength" / 2',
        )
    ]
    wizard_hole_on_cylinder(
        adapter,
        PIN_HOLE_SPEC,
        [-BOSS_DIA / 2.0, 0.0, PIN_STATION],
        "retention-pin cross-hole",
        name="PinHole",
        point_planes=("PinStationPlane", "Top Plane"),
    )
    # Two boss walls = the full-cylinder cross-drill minus the bore's share.
    v_pin_hole = cross_hole_volume_mm3(PIN_DIA, BOSS_DIA) - cross_hole_volume_mm3(
        PIN_DIA, BORE_DIAMETER
    )
    volume = await volume_check(
        adapter, "retention-pin cross-hole", volume - v_pin_hole, 0.02 * v_pin_hole
    )
    return volume, drive_jobs


async def _geometry(
    adapter, *, hole: bool = True, boss_from_face_width: bool = False
) -> dict:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): every length carries the load-bearing
    # mm suffix (INCH document; the equation manager reads bare numbers in
    # document units, so an unsuffixed length blows the part up 25.4x).
    # FaceWidth drives the gear blank's extrude depth, OutsideDia its tip
    # circle: both are printed dimensions, so both are knobs. TEETH/DP stay
    # module constants -- the tooth gap and pattern are built by
    # build_fixed_gear with literal numerics, off this self-naming path.
    await set_global(adapter, "FaceWidth", f"{FACE_WIDTH}mm")
    await set_global(adapter, "OutsideDia", f"{OUTSIDE_DIA}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIAMETER}mm")
    await set_global(adapter, "BossDia", f"{BOSS_DIA}mm")
    await set_global(adapter, "BossLength", f"{BOSS_LENGTH}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Root-relieved floor (real dedendum): the mating 64T's tips reach
    # 0.71 mm BELOW this 16T's base circle at working depth -- the stock
    # base-chord gap floor (fine for the big-count train pairs) starves a
    # 16-tooth pinion, and was half of why the old mesh could not close
    # (2026-07-14 rederive; see build_crank_drive_gear.py's docstring).
    # The pinion stays a plain straight spur otherwise -- the book's
    # removable "gear on the crankshaft can be changed" stock member; the
    # crossing accommodation (helix + backlash) lives on the 64T.
    volume = await build_fixed_gear(
        adapter, TEETH, FACE_WIDTH, dp=DP, pa_deg=PA_DEG, root_relief=True,
    )

    # build_fixed_gear is shared by five recipes, so it leaves the blank under
    # the adapter's default names. Name the blank extrude and its absorbed
    # profile sketch here: the two sizes the turner sets before a cutter
    # touches the part -- face width and outside diameter -- print as NATIVE
    # model dimensions (drawing-simplicity-policy.md rule 1), which means they
    # must be named, driven, toleranced and marked like any other. Driving both
    # is also the guard on these default names: a rename that resolved the
    # wrong feature would move the blank and the equation-neutral volume gate
    # below would fail loud instead of printing a dimension of something else.
    _feature_by_name(adapter, "Boss-Extrude1").Name = "GearBlank"
    _telemetry.success("feature 'Boss-Extrude1' -> 'GearBlank'")
    drive_jobs += [
        (name_dimensions(adapter, "GearBlank", ["FaceWidth"])[0], '"FaceWidth"')
    ]
    _feature_by_name(adapter, "Sketch1").Name = "GearBlankProfile"
    _telemetry.success("feature 'Sketch1' -> 'GearBlankProfile'")
    drive_jobs += [
        (
            name_dimensions(adapter, "GearBlankProfile", ["OutsideDia"])[0],
            '"OutsideDia"',
        )
    ]

    # Hub boss (ch12 p.19): the root-circle cylinder from the SAME faced end
    # as the teeth, through the toothed length and BOSS_LENGTH past it, so its
    # length IS the part's overall length -- one conspicuous native dimension
    # from one faced end (policy rule 7). Inside the toothed length the
    # cylinder lies within the blank's solid core (its surface is the relieved
    # gap floors' own root arc), so the merge adds exactly the outboard stub,
    # which the volume gate proves. It is a REVOLVE of a half-profile on the
    # Right plane (local x -> model -Z, local y -> model Y) rather than an
    # extruded circle: a turned part prints its diameter beside its length on
    # the side view (rule 7), and only a dimension whose sketch plane is
    # parallel to that view imports there natively -- the boss diameter as a
    # doubled centerline-to-outline dim, the overall length along the outline.
    if boss_from_face_width:
        volume, jobs = await _boss_from_face_width(adapter, volume)
    else:
        volume, jobs = await _boss_standard(adapter, volume)
    drive_jobs += jobs


    # On-axis bore (centre 0,0) through teeth and boss: define_circle emits
    # only the diameter dim, so only the "Dia" slot is recorded -- the X/Z
    # names are ignored.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, BORE_DIAMETER / 2.0, "bore", dims=bore,
        names=("BoreCx", "BoreCz", "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=OVERALL_LENGTH + 2.0)
        ),
    )
    name_last_feature(adapter, "Bore")
    v_bore = math.pi * (BORE_DIAMETER / 2.0) ** 2 * OVERALL_LENGTH
    volume = await volume_check(adapter, "bore", volume - v_bore, 0.01 * v_bore)

    # Named bore/central axis for view-independent assembly mate
    # selection (M6 mated-DOF drive train). Stays Axis2: the cross-hole comes
    # after it and creates no axis of its own.
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "bore axis")

    if hole:
        volume, jobs = await _pin_hole(adapter, volume)
        drive_jobs += jobs
    await force_rebuild(adapter)
    return {"volume": volume, "drive_jobs": drive_jobs, "v_bore": v_bore}


async def _boss_from_face_width(adapter, volume: float) -> tuple[float, list]:
    """Step 3 variant: the boss revolve starts AT the tooth face, so it never
    overlaps the gap floors' root arcs."""
    from solidworks_mcp.adapters.base import RevolveParameters

    drive_jobs: list[tuple[str, str]] = []
    boss = SketchDims()
    check("create_sketch boss", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    boss_axis = check(
        "boss axis centerline",
        await adapter.add_centerline(-FACE_WIDTH, 0.0, -OVERALL_LENGTH, 0.0),
    )
    boss_pts = [
        (-FACE_WIDTH, 0.0),
        (-FACE_WIDTH, BOSS_DIA / 2.0),
        (-OVERALL_LENGTH, BOSS_DIA / 2.0),
        (-OVERALL_LENGTH, 0.0),
    ]
    boss_lines = await add_line_chain(adapter, boss_pts)
    set_sketch_direct_db(adapter, False)
    for i, line in enumerate(boss_lines):
        (_, y1), (_, y2) = boss_pts[i], boss_pts[(i + 1) % len(boss_lines)]
        direction = "horizontal" if y1 == y2 else "vertical"
        check(
            f"boss {direction} {line}",
            await adapter.add_sketch_constraint(line, None, direction),
        )
    boss_outline = boss_lines[1]
    await dimension_between(
        adapter,
        f"{boss_outline}.start",
        f"{boss_outline}.end",
        "horizontal_distance",
        BOSS_LENGTH,
        "boss BossLength",
    )
    boss.record("BossLength", '"BossLength"')
    await add_diametric_linear_dimension(
        adapter,
        boss_axis,
        boss_outline,
        (-(FACE_WIDTH + OVERALL_LENGTH) / 2.0, BOSS_DIA / 2.0 + 5.0),
        "BossDia",
    )
    boss.record("BossDia", '"BossDia"')
    await anchor_point_to_origin(
        adapter, f"{boss_lines[0]}.start", -FACE_WIDTH, 0.0, "boss anchor"
    )
    boss.record(None, None)
    await ensure_fully_defined(adapter, "boss sketch")
    check("exit_sketch boss", await adapter.exit_sketch())
    name_last_feature(adapter, "BossProfile")
    drive_jobs += boss.apply(adapter, "BossProfile")
    check(
        "revolve boss", await adapter.create_revolve(RevolveParameters(angle=360.0))
    )
    name_last_feature(adapter, "Boss")
    v_boss = math.pi * (BOSS_DIA / 2.0) ** 2 * BOSS_LENGTH
    volume = await volume_check(adapter, "hub boss", volume + v_boss, 0.01 * v_boss)
    return volume, drive_jobs


# ---------------------------------------------------------------------------
# DIAG v3 (#906, not for merge).  Why does PinHole fail on the first
# equation-driven regen?  Each step builds a FRESH document, so no step
# inherits another's damage, and logs the PinHole placement face (the boss
# cylinder containing the pin point) before and after its regen: radius,
# edges, area, z extent and its persistent reference, plus whether the
# pre-regen reference still resolves to the same face.
# ---------------------------------------------------------------------------

_PIN_POINT_MM = (-BOSS_DIA / 2.0, 0.0, PIN_STATION)
# swFeatureError_e (the enum GetWhatsWrong's codes use); _common's
# _FEATURE_ERROR labels code 1 "warning", but 1 is swFeatureErrorUnknown.
_SW_FEATURE_ERROR = {
    0: "none",
    1: "unknown",
    30: "extrusion-disjoint",
    31: "extrusion-no-end",
    32: "extrusion-bad-geometric-conditions",
    71: "cut-not-intersect-model",
    73: "missing-items-in-feature",
}


def _encode(reference) -> str:
    import base64

    return base64.b64encode(bytes((int(v) & 0xFF) for v in reference)).decode("ascii")


def _decode(encoded: str) -> list[int]:
    import base64

    return list(base64.b64decode(encoded.encode("ascii")))


def _face_row(face) -> dict:
    surface = _early_bound(face.GetSurface(), "ISurface")
    params = [float(v) for v in surface.CylinderParams]
    box = [float(v) * 1000.0 for v in face.GetBox()]
    return {
        "radius_mm": round(params[6] * 1000.0, 5),
        "axis": [round(v, 6) for v in params[3:6]],
        "edges": int(face.GetEdgeCount()),
        "area_mm2": round(float(face.GetArea()) * 1e6, 4),
        "z_mm": [round(box[2], 4), round(box[5], 4)],
    }


def _contains_pin_point(face) -> bool:
    surface = _early_bound(face.GetSurface(), "ISurface")
    params = [float(v) for v in surface.CylinderParams]
    point = [v / 1000.0 for v in _PIN_POINT_MM]
    origin, axis, radius = params[:3], params[3:6], params[6]
    rel = [point[i] - origin[i] for i in range(3)]
    axial = sum(rel[i] * axis[i] for i in range(3))
    radial = [rel[i] - axial * axis[i] for i in range(3)]
    if abs(sum(v * v for v in radial) ** 0.5 - radius) > 1e-6:
        return False
    box = [float(v) for v in face.GetBox()]
    return all(box[i] - 1e-6 <= point[i] <= box[i + 3] + 1e-6 for i in range(3))


def _messages(adapter) -> list[str]:
    """Read-and-clear SolidWorks' session message stack."""
    answer = adapter._attempt(
        lambda: _early_bound(adapter.swApp, "ISldWorks").GetErrorMessages(),
        default=None,
    )
    if isinstance(answer, (list, tuple)) and len(answer) >= 2:
        return [str(text) for text in (answer[1] or [])]
    return []


def _snapshot(adapter, tag: str, reference: str | None = None) -> dict:
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    extension = _early_bound(_read_member(model, "Extension"), "IModelDocExtension")
    part = _early_bound(model, "IPartDoc")
    title = str(_read_member(model, "GetTitle") or "")
    snap: dict = {"tag": tag, "doc": title}
    try:
        bodies = part.GetBodies2(0, False) or ()
        snap["bodies"] = len(bodies)
        body = _early_bound(bodies[0], "IBody2") if bodies else None
        if body is not None:
            snap["body_box_mm"] = [round(float(v) * 1000.0, 4) for v in body.GetBodyBox()]
        blank = part.FeatureByName("GearBlank")
        if blank is not None:
            data = _early_bound(
                _early_bound(blank, "IFeature").GetDefinition(), "IExtrudeFeatureData2"
            )
            snap["blank_reverse"] = bool(data.ReverseDirection)
            snap["blank_depth_fwd_mm"] = round(float(data.GetDepth(True)) * 1000.0, 5)
            dim = _early_bound(model.Parameter("FaceWidth@GearBlank"), "IDimension")
            snap["blank_dim_mm"] = round(float(dim.SystemValue) * 1000.0, 6)
        boss_faces, pin_face = [], None
        for raw in (body.GetFaces() if body is not None else None) or ():
            face = _early_bound(raw, "IFace2")
            if not _early_bound(face.GetSurface(), "ISurface").IsCylinder():
                continue
            row = _face_row(face)
            if abs(row["radius_mm"] - BOSS_DIA / 2.0) > 1e-3:
                continue
            row["holds_pin_point"] = _contains_pin_point(face)
            boss_faces.append(row)
            if row["holds_pin_point"]:
                pin_face = raw
        snap["boss_faces"] = boss_faces
        if pin_face is not None:
            snap["pin_face_persist"] = _encode(extension.GetPersistReference3(pin_face))
            if reference is not None:
                snap["pin_face_same_persist"] = snap["pin_face_persist"] == reference
        if reference is not None:
            answer = extension.GetObjectByPersistReference3(_decode(reference))
            if isinstance(answer, (tuple, list)) and len(answer) == 2:
                obj, state = answer
                snap["old_ref_state"] = int(state)
                if obj is not None:
                    snap["old_ref_face"] = _face_row(_early_bound(obj, "IFace2"))
            else:
                snap["old_ref_answer"] = repr(type(answer))
        hole = part.FeatureByName("PinHole")
        if hole is not None:
            answer = _early_bound(hole, "IFeature").GetErrorCode2()
            snap["pinhole_error"] = repr(answer)
        wrong = extension.GetWhatsWrong()
        if isinstance(wrong, (list, tuple)) and len(wrong) >= 4:
            _ok, features, codes, warnings = wrong[:4]
            snap["whats_wrong"] = [
                {
                    "feature": str(_read_member(feature, "Name")),
                    "code": int(code or 0),
                    "error": _SW_FEATURE_ERROR.get(int(code or 0), "other"),
                    "is_warning": bool(warning),
                }
                for feature, code, warning in zip(
                    list(features or []), list(codes or []), list(warnings or []),
                    strict=False,
                )
            ]
        messages = _messages(adapter)
        snap["messages_this_doc"] = [m for m in messages if title and title in m]
        snap["messages_other_docs"] = len(messages) - len(snap["messages_this_doc"])
    except Exception as exc:  # diagnostic only: never lose the rest of the run
        snap["snapshot_error"] = repr(exc)
    _telemetry.info(f"DIAG {tag} {json.dumps(snap, default=str)}")
    return snap


async def _rebuild(adapter, tag: str, reference: str | None = None) -> dict:
    result = await adapter.rebuild_model()
    snap = _snapshot(adapter, tag, reference)
    snap["rebuild_ok"] = bool(getattr(result, "is_success", result))
    _telemetry.info(f"DIAG {tag} rebuild_ok={snap['rebuild_ok']}")
    return snap


def _clean(snap: dict) -> bool:
    return bool(snap.get("rebuild_ok")) and not snap.get("whats_wrong")


async def _step0_control(adapter) -> bool:
    await _geometry(adapter)
    ref = _snapshot(adapter, "s0 built").get("pin_face_persist")
    return _clean(await _rebuild(adapter, "s0 ForceRebuild3, no drive", ref))


async def _step1_value_set(adapter) -> bool:
    await _geometry(adapter)
    ref = _snapshot(adapter, "s1 built").get("pin_face_persist")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    dim = _early_bound(model.Parameter("FaceWidth@GearBlank"), "IDimension")
    value = float(dim.SystemValue)
    status = dim.SetSystemValue3(value, 2, None)  # swSetValue_InAllConfigurations
    _telemetry.info(f"DIAG s1 SetSystemValue3({value!r}) -> {status!r}")
    return _clean(await _rebuild(adapter, "s1 FaceWidth value re-set, no equation", ref))


async def _step1_equation(adapter) -> bool:
    geometry = await _geometry(adapter)
    ref = _snapshot(adapter, "s1e built").get("pin_face_persist")
    dim_name, expr = geometry["drive_jobs"][0]
    await drive_dimension(adapter, dim_name, expr)
    return _clean(await _rebuild(adapter, f"s1e equation {dim_name} = {expr}", ref))


async def _step2_hole_after(adapter) -> bool:
    geometry = await _geometry(adapter, hole=False)
    for dim_name, expr in geometry["drive_jobs"]:
        await drive_dimension(adapter, dim_name, expr)
        snap = await _rebuild(adapter, f"s2 equation {dim_name}")
        if not _clean(snap):
            return False
    volume, jobs = await _pin_hole(adapter, geometry["volume"])
    for dim_name, expr in jobs:
        await drive_dimension(adapter, dim_name, expr)
    snap = await _rebuild(adapter, "s2 hole added after equations")
    ref = snap.get("pin_face_persist")
    if not _clean(snap):
        return False
    # The nudge: a real equation-driven change and back.
    await set_global(adapter, "OutsideDia", f"{OUTSIDE_DIA + 0.01}mm")
    if not _clean(await _rebuild(adapter, "s2 nudge OutsideDia +0.01", ref)):
        return False
    await set_global(adapter, "OutsideDia", f"{OUTSIDE_DIA}mm")
    if not _clean(await _rebuild(adapter, "s2 nudge OutsideDia back", ref)):
        return False
    await volume_check(adapter, "s2 driven pinion", volume, 0.01 * geometry["v_bore"])
    return True


async def _step3_boss_from_face_width(adapter) -> bool:
    geometry = await _geometry(adapter, boss_from_face_width=True)
    ref = _snapshot(adapter, "s3 built").get("pin_face_persist")
    for dim_name, expr in geometry["drive_jobs"]:
        await drive_dimension(adapter, dim_name, expr)
        if not _clean(await _rebuild(adapter, f"s3 equation {dim_name}", ref)):
            return False
    return True


async def build(adapter) -> dict[str, str]:
    steps = (
        ("s0 control: ForceRebuild3, no drive", _step0_control),
        ("s1 FaceWidth value re-set, no equation", _step1_value_set),
        ("s1e FaceWidth equation (the known failure)", _step1_equation),
        ("s2 hole after the equations, then the nudge", _step2_hole_after),
        ("s3 boss from FaceWidth (diag only)", _step3_boss_from_face_width),
    )
    verdicts: dict[str, str] = {}
    for label, step in steps:
        _messages(adapter)  # drain: the stack is session-global
        with _telemetry.span("diag.step", step=label):
            try:
                verdicts[label] = "clean" if await step(adapter) else "FAILED"
            except Exception as exc:  # each step is independent
                verdicts[label] = f"ERROR {exc!r}"
                _telemetry.error(f"DIAG {label}: {exc!r}")
            finally:
                discard_open_documents(adapter)
        _telemetry.info(f"DIAG verdict {label}: {verdicts[label]}")
    _telemetry.info(f"DIAG v3 summary {json.dumps(verdicts)}")
    # Never publish a diag artefact to the cache.
    raise RuntimeError(f"DIAG v3 finished (no artefact by design): {verdicts}")


if __name__ == "__main__":
    sys.exit(run_build(build))
