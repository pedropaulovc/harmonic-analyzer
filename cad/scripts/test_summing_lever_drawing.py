"""Offline contracts for the summing-lever drawing."""

from __future__ import annotations

import math

import draw_summing_lever
import summing_lever_spec
from _hole_spec import blind_cut_dia_mm
from stock_anchor_geom import ANCHOR_9489T111, ANCHOR_9490T1


def test_anchor_seats_are_the_purchased_anchors_own_threads() -> None:
    """Both lower spring anchors are purchased eyebolts threaded straight into
    this casting -- there is no nut -- so a seat that does not match its
    anchor, or a boss its anchor cannot span, is an unassemblable part."""
    plate, boss = summing_lever_spec.HOLE_SPEC, summing_lever_spec.COUNTER_HOLE_SPEC
    assert (plate.kind, plate.end) == ("tapped", "through_all")
    assert (boss.kind, boss.end) == ("tapped", "through_all")
    assert plate.size == ANCHOR_9489T111.thread_size
    assert boss.size == ANCHOR_9490T1.thread_size
    # Each anchor's thread must span the seat it screws into.
    assert ANCHOR_9489T111.thread_length_mm > summing_lever_spec.PLATE_T
    assert ANCHOR_9490T1.thread_length_mm >= summing_lever_spec.ANCHOR_H
    # ...and each tap must fit the feature it passes through.
    assert blind_cut_dia_mm(boss) < 2.0 * summing_lever_spec.ANCHOR_R
    assert blind_cut_dia_mm(plate) < summing_lever_spec.HOLE_EDGE_OFFSET


def test_knife_profile_is_the_nonregular_hex_detail_a_states() -> None:
    """Detail A's note states a NONREGULAR 6-SIDED PROFILE, so the model has to
    be one and the flat the note is read against has to be the length the print
    dimension carries.

    "Correcting" HEX_H to the across-corners value its across-flats implies
    would make the sheet contradict itself while every dictionary entry still
    looked right -- this fails loudly on exactly that edit.
    """
    across_flats = summing_lever_spec.HEX_W
    across_corners = summing_lever_spec.HEX_H
    # A regular hexagon locks A/F and A/C together; ours is 0.28 mm outside it.
    assert abs(across_corners - across_flats * 2.0 / math.sqrt(3.0)) > 0.2
    # _hex_collar's vertex-up hexagon puts its shoulders at +-HEX_H/4, so the
    # +X vertical flat HexKnifeFrontSideFlat names is exactly HEX_H/2 -- and not
    # the regular hexagon's side HEX_W/sqrt(3). A flat is half the A/C measure,
    # so the second gap is half the bound above.
    half_width, quarter_height = across_flats / 2.0, across_corners / 4.0
    flat = math.dist((half_width, -quarter_height), (half_width, quarter_height))
    assert math.isclose(flat, across_corners / 2.0, rel_tol=0.0, abs_tol=1e-12)
    assert abs(flat - across_flats / math.sqrt(3.0)) > 0.1
    # ...and the flat must reach the print as a model dimension at its own
    # decimal places, which is what the note is read against.
    assert (
        "HexKnifeFrontSideFlat"
        in summing_lever_spec.DRAWING_DIMENSIONS["HexKnifeFrontProfile"]
    )
    assert (
        "HexKnifeFrontSideFlat"
        in summing_lever_spec.DRAWING_PRECISION["HexKnifeFrontProfile"]
    )


def test_midrib_right_end_is_in_the_specs_marked_set() -> None:
    """The gusset's right-hand rib end reaches the print as a model dimension.

    ``DRAWING_PRECISION_BY_NAME`` is derived from the marked set, and the spec
    refuses to import while the two disagree, so this one membership check
    covers both the marking and the decimal places that go with it.
    """
    assert "MidRibRightX" in summing_lever_spec.DRAWING_PRECISION_BY_NAME


def test_manufacturing_note_block_stays_four_lines() -> None:
    """The general-note block is the print's only prose and it must not grow.

    The drawing simplicity policy names a lengthening note block as the disease
    the migration cures, so the block stays at the four statements the review
    rounds settled on. Collapsing them into one multi-line note is the same
    failure and trips this too.
    """
    assert len(draw_summing_lever.MANUFACTURING_NOTES) == 4


def test_printed_arc_centre_lays_the_arc_onto_the_boss() -> None:
    """The R138.8 side arcs are laid out from their printed centre and radius.

    The arc's base end is buried in the cylinder, so the shop can only strike it
    from the centre the print locates (2X 123.2 from the cylinder axis, 2X 64.0
    beyond the plate end).  Rounded to the printed places, that centre and radius
    must still land the arc on the boss quadrant and on the buried base corner
    within the one-place title-block band.
    """
    import build_summing_lever as build

    base_end, tip_end, interior = build._summation_top_arc_points()
    cx, cy = build._circumcenter(base_end, tip_end, interior)
    printed_x = round(abs(cx), 1)
    printed_z = round(cy - base_end[1], 1)
    printed_r = round(math.dist((cx, cy), base_end), 1)
    centre = (-printed_x, base_end[1] + printed_z)
    for end in (tip_end, base_end):
        assert abs(math.dist(centre, end) - printed_r) < 0.8


def _synthetic_lever_brep():
    """The finished lever's locating surfaces, in the shape the B-rep reads them."""
    import build_summing_lever as build

    hole_r = blind_cut_dia_mm(summing_lever_spec.HOLE_SPEC) / 2.0
    base_end, tip_end, interior = build._summation_top_arc_points()
    cx, cy = build._circumcenter(base_end, tip_end, interior)
    web_r = math.dist((cx, cy), base_end)
    cylinders = [
        # Hole axes read at the plate's mid-plane, some with a reversed sense.
        ((build.HOLE_X, 2.54, z), (0.0, (-1.0) ** j, 0.0), hole_r)
        for j, z in enumerate(build.HOLE_Z)
    ]
    cylinders += [
        ((build.TIP_X, 9.0, 0.0), (0.0, 1.0, 0.0), build.ANCHOR_R),
        # The counter tap through the boss: same axis, not a locating feature.
        ((build.TIP_X, 0.0, 0.0), (0.0, 1.0, 0.0), 1.9),
        ((0.0, 0.0, -76.2), (0.0, 0.0, 1.0), build.CYL_R),
        ((0.0, 0.0, 10.0), (0.0, 0.0, -1.0), build.CYL_R),  # split pivot face
        ((cx, 0.0, -cy), (0.0, 1.0, 0.0), web_r),
        ((cx, 0.0, cy), (0.0, -1.0, 0.0), web_r),
    ]
    planes = [
        ((0.0, 0.0, s), (5.0, 1.0, s * z))
        for z in (build.PLATE_L / 2.0, build.HEX_Z_OUTER, build.RIB_OFFSET)
        for s in (1.0, -1.0)
    ]
    return cylinders, planes, (cx, cy)


def _top_plane(points):
    """A Top-plane sketch point (x, y) sits at model (x, 0, -y)."""
    return [(x, 0.0, -y) for x, y in points]


def _pattern_points(station_sign: float):
    import build_summing_lever as build

    first, last = build.HOLE_Z[0], build.HOLE_Z[-1]
    half = build.PLATE_L / 2.0
    return _top_plane(
        [
            (build.HOLE_X, half),
            (build.HOLE_X, station_sign * first),
            (build.HOLE_X, station_sign * last),
            (build.HOLE_X, -half),
        ]
    )


def _boss_points():
    import build_summing_lever as build

    return _top_plane([(build.TIP_X, -build.PLATE_L / 2.0), (build.TIP_X, 0.0)])


def _arc_points(centre):
    import build_summing_lever as build

    cx, cy = centre
    arm = build.CENTRE_CROSS_ARM
    return _top_plane(
        [
            (0.0, build.SUM_BASE),
            (0.0, build.HEX_Z_OUTER),
            (cx, cy),
            (cx + arm, cy),
            (cx - arm, cy),
            (cx, cy + arm),
            (cx, cy - arm),
        ]
    )


def _cylinder_points(radius_error: float = 0.0):
    import build_summing_lever as build

    station = -build.CYLINDER_REFERENCE_Z
    half = build.CYL_R + radius_error
    return _top_plane([(-half, station), (half, station)])


def test_reference_gate_accepts_sketches_on_the_real_features() -> None:
    """Positive control: the R7 authoring (-HOLE_Z on the Top plane) passes."""
    import build_summing_lever as build

    cylinders, planes, centre = _synthetic_lever_brep()
    claims = build._reference_claims(cylinders, planes)
    for name, points in (
        ("PatternReferences", _pattern_points(-1.0)),
        ("BossAxialReference", _boss_points()),
        ("SummationArcReference", _arc_points(centre)),
        ("CylinderReference", _cylinder_points()),
    ):
        problems, worst = build._reference_misses(points, *claims[name])
        assert problems == [], (name, problems)
        assert worst <= build.REFERENCE_COINCIDENCE_TOL_MM


def test_reference_gate_rejects_the_r6_mirrored_spring_field() -> None:
    """Negative control: R1-R6 authored +HOLE_Z, 1.47 mm off both terminal holes."""
    import build_summing_lever as build

    cylinders, planes, _centre = _synthetic_lever_brep()
    targets, required, exempt = build._reference_claims(cylinders, planes)[
        "PatternReferences"
    ]
    problems, _worst = build._reference_misses(
        _pattern_points(1.0), targets, required, exempt
    )
    assert sum("1.4735 mm off spring hole" in problem for problem in problems) == 2
    assert "no point lands on the first spring hole" in problems
    assert "no point lands on the last spring hole" in problems


def test_reference_gate_rejects_an_arc_centre_off_by_a_hundredth_micron() -> None:
    import build_summing_lever as build

    cylinders, planes, (cx, cy) = _synthetic_lever_brep()
    claims = build._reference_claims(cylinders, planes)["SummationArcReference"]
    problems, _worst = build._reference_misses(_arc_points((cx, cy + 1e-5)), *claims)
    assert "is 1e-05 mm off summation-arc axis" in problems[0], problems
    assert problems[-1] == "no point lands on a summation-arc centre"


def test_reference_gate_refuses_a_brep_missing_a_spring_hole() -> None:
    import pytest

    import build_summing_lever as build

    cylinders, planes, _centre = _synthetic_lever_brep()
    with pytest.raises(RuntimeError, match="expected 20 spring-hole axes"):
        build._reference_claims(cylinders[1:], planes)


def test_reference_gate_rejects_a_diameter_line_off_the_cylinder_face() -> None:
    """Negative control: a CylRefDia line 1e-5 mm off the face at each end."""
    import build_summing_lever as build

    cylinders, planes, _centre = _synthetic_lever_brep()
    claims = build._reference_claims(cylinders, planes)["CylinderReference"]
    problems, _worst = build._reference_misses(_cylinder_points(1e-5), *claims)
    assert sum("mm off pivot-cylinder face" in problem for problem in problems) == 2
    assert problems[-1] == "no point lands on the pivot-cylinder face"


def _slab_sources(source: str) -> dict[str, tuple[str, str]]:
    """Per plate-arm builder: (extrusion depth, equation driving that depth).

    Read from the build script's AST, so the guard runs offline and keys no
    part: the extrusion's ``depth=`` expression and the global its depth
    dimension is driven by (the ``drive_jobs.append((name, expr))`` call).
    """
    import ast

    found: dict[str, tuple[str, str]] = {}
    for node in ast.walk(ast.parse(source)):
        if not (
            isinstance(node, ast.AsyncFunctionDef)
            and node.name in ("_coefficients_plate", "_summation_plate")
        ):
            continue
        depth = drive = ""
        for call in (n for n in ast.walk(node) if isinstance(n, ast.Call)):
            if getattr(call.func, "id", "") == "ExtrusionParameters":
                depth = next(
                    ast.unparse(k.value) for k in call.keywords if k.arg == "depth"
                )
            if getattr(call.func, "attr", "") == "append" and call.args:
                pair = call.args[0]
                # The depth dimension's own drive: (<arm>_depth[0], "<global>").
                if (
                    isinstance(pair, ast.Tuple)
                    and ast.unparse(pair.elts[0]).endswith("_depth[0]")
                    and isinstance(pair.elts[1], ast.Constant)
                ):
                    drive = pair.elts[1].value
        found[node.name] = (depth, drive)
    return found


def _is_one_slab(sources: dict[str, tuple[str, str]]) -> bool:
    return set(sources.values()) == {("PLATE_T", '"PlateT"')} and len(sources) == 2


def test_plate_and_web_are_one_slab_by_construction() -> None:
    """The print's "PLATE AND WEB" 5.08 governs both arms.

    Both are mid-plane Top-plane extrusions whose depth is PLATE_T and whose
    depth dimension is driven by the one "PlateT" global; splitting either
    would let the web's thickness drift away from the only 5.08 printed.
    """
    import inspect

    import build_summing_lever as build

    source = inspect.getsource(build)
    assert _slab_sources(source) == {
        "_coefficients_plate": ("PLATE_T", '"PlateT"'),
        "_summation_plate": ("PLATE_T", '"PlateT"'),
    }
    assert _is_one_slab(_slab_sources(source))
    # Negative controls: a split global, and a web built to its own depth.
    split = source.replace("""web_depth[0], '"PlateT"'""", """web_depth[0], '"WebT"'""")
    assert split != source and not _is_one_slab(_slab_sources(split))
    body = inspect.getsource(build._summation_plate)
    own_depth = source.replace(body, body.replace("depth=PLATE_T", "depth=WEB_T"))
    assert own_depth != source and not _is_one_slab(_slab_sources(own_depth))


def _slab_faces(web_half: float):
    """Y-normal faces of the two arms: (normal, root, box centre X)."""
    import build_summing_lever as build

    plate_half = build.PLATE_T / 2.0
    return [
        ((0.0, sign, 0.0), (x, sign * half, 7.0), x)
        for x, half in ((-45.0, web_half), (28.0, plate_half))
        for sign in (1.0, -1.0)
    ]


def test_web_and_plate_gate_accepts_one_slab() -> None:
    """Positive control: both arms on the plate's +-2.54 planes."""
    import build_summing_lever as build

    assert build._slab_misses(_slab_faces(build.PLATE_T / 2.0)) == []


def test_web_and_plate_gate_rejects_a_thicker_web() -> None:
    """Negative control: a web 1e-5 mm proud of the plate on each face."""
    import build_summing_lever as build

    problems = build._slab_misses(_slab_faces(build.PLATE_T / 2.0 + 1e-5))
    assert problems == [
        "no summation web face on y=+2.54",
        "no summation web face on y=-2.54",
    ]


def test_every_reference_sketch_is_saved_hidden() -> None:
    """Each construction-only sketch that carries print dimensions renders
    unless the part blanks it (asm, 2026-09-24: the R138.8 centre cross
    floated off the part in the summing isometric), so every one the drawing
    marks must be in the part's hide list."""
    import build_summing_lever as build

    marked = {
        feature
        for feature in summing_lever_spec.DRAWING_DIMENSIONS
        if feature.endswith(("Reference", "References"))
    }
    assert marked == set(build.DRAWING_REFERENCE_SKETCHES)


def test_only_orthographic_views_show_reference_sketches() -> None:
    """Main's bar: the orthographic views keep the accepted sheet's marks and
    the pictorial shows no reference-sketch geometry at all."""
    import build_summing_lever as build

    assert set(draw_summing_lever.VIEW_SKETCHES) == {
        "form front",
        "form top",
        "spring-pattern plan",
    }
    for sketches in draw_summing_lever.VIEW_SKETCHES.values():
        assert set(sketches) <= set(build.DRAWING_REFERENCE_SKETCHES)
