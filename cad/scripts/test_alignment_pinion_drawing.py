"""Offline contracts for retained alignment-pinion manufacturing data."""

from __future__ import annotations

import math
import re

import pytest

import _config
import alignment_pinion_spec as spec
import pinion_arbor_spec as arbor


def test_gear_data_block_preserves_the_actual_base_chord_profile() -> None:
    data = spec.GEAR_DATA
    assert spec.TEETH == 32
    assert spec.TEETH == int(_config.machine("alignment_pinion", "teeth"))
    assert "NUMBER OF TEETH:  32" in data
    for field in (
        "DIAMETRAL PITCH",
        "MODULE",
        "PRESSURE ANGLE",
        "PITCH DIAMETER",
        "MIN CHORD-FLOOR DIAMETER (mm, REF):  15.780",
        "AS-CUT RADIAL TOOTH DEPTH (mm, REF):  0.777",
        f"TOOTH FORM:  {spec.BASE_CHORD_ROOT_FORM}",
    ):
        assert field in data, field
    assert "FULL DEPTH" not in data
    assert "WHOLE DEPTH" not in data
    assert "X.XX" not in data


def test_bore_and_both_thrust_end_faces_carry_the_machined_finish() -> None:
    """Machinist review of 7f7fc1717: "end faces polished" had no stated
    function.  The drum's ends are thrust faces -- MHA-102's float model stops
    the drum hard forward and hard aft against the MHA-056 straps -- so each
    carries the machined grade on its own face, and the finish field drops
    the polish."""
    import draw_alignment_pinion as drawing
    from _gtol_spec import PlanarFace

    bore, front, back = spec.SURFACE_FINISHES
    assert bore.key == "drum_bore"
    assert bore.face.diameter_mm == 8.0
    assert front.key == "front_end_face"
    assert front.face == PlanarFace((0, 0, -1), 0.0)
    assert back.key == "back_end_face"
    assert back.face == PlanarFace((0, 0, 1), spec.FACE_WIDTH)
    assert {control.roughness_um for control in spec.SURFACE_FINISHES} == {1.6}
    # The float model the thrust claim rests on.
    assert arbor.STRAP_AXIAL_LOCATION == "pinned-shim-set"
    # Either stop puts all the air at one end, so the other end touches.
    assert arbor.STOPS == {"drum forward": 0.0, "drum aft": 1.0}
    assert "polish" not in _config.parts("alignment-pinion")["finish"].lower()
    # Each symbol's leader starts outside the drum and lands on its own end.
    assert drawing.BACK_END_FINISH_SYMBOL_XY[0] < drawing.BACK_END_FACE_XY[0]
    assert drawing.FRONT_END_FINISH_SYMBOL_XY[0] > drawing.FRONT_END_FACE_XY[0]
    assert drawing.FRONT_END_FACE_XY[0] - drawing.BACK_END_FACE_XY[0] == pytest.approx(
        spec.FACE_WIDTH / 1000.0
    )


def test_bonded_slip_fit_clears_the_mha102_journal_within_the_bond_gap() -> None:
    shaft_limits = (
        arbor.SHAFT_DIA + arbor.SHAFT_DIA_BAND[1],
        arbor.SHAFT_DIA + arbor.SHAFT_DIA_BAND[0],
    )
    bore_limits = (
        spec.BORE_DIA + spec.ARBOR_BORE_BAND[1],
        spec.BORE_DIA + spec.ARBOR_BORE_BAND[0],
    )
    # The drum bonds onto MHA-102's bond zone, not its journal lands (U39).
    assert arbor.SHAFT_DIA_BAND != arbor.JOURNAL_DIA_BAND
    assert bore_limits == pytest.approx((8.00, 8.10))
    # A stock 8 mm H7 reamer (8.000-8.015) lands inside the band.
    assert bore_limits[0] <= 8.000 and 8.015 <= bore_limits[1]
    minimum_clearance = bore_limits[0] - shaft_limits[1]
    maximum_clearance = bore_limits[1] - shaft_limits[0]
    assert minimum_clearance == pytest.approx(
        spec.ARBOR_BORE_BAND[1] - arbor.SHAFT_DIA_BAND[0]
    )
    # The drum slides on by hand: the arbor's bond zone sits 0.01 under 8.00.
    assert minimum_clearance == pytest.approx(0.010)
    assert minimum_clearance >= 0.010 - 1e-9
    assert maximum_clearance == pytest.approx(
        spec.ARBOR_BORE_BAND[0] - arbor.SHAFT_DIA_BAND[1]
    )
    assert maximum_clearance == pytest.approx(0.200)
    assert maximum_clearance < spec.RETAINING_COMPOUND_MAX_GAP_MM
    assert spec.BORE_DIA == arbor.SHAFT_DIA  # the CAD models line-to-line


def test_the_drum_bond_is_the_fitup_step_not_a_note() -> None:
    import pinion_arbor_spec as arbor_spec

    notes = spec.DRAWING_NOTES
    # Rule 6 (R3): one note.  The drum is symmetric, so no orientation note;
    # its axial station is stated once, on MHA-102.  The MHA-102 bond-zone
    # band is MHA-102's own native dimension (Codex P1 on #814), the hand
    # slide rides the bore callout (Codex P2 on #832), and the bond itself is
    # the pinion fit-up step MHA-102's spec owns (Main's rule-6 sweep).
    assert notes == "TOOTH FLANKS, TIPS, AND ROOTS: DO NOT CHAMFER OR BLEND."
    assert "BOND ZONE" not in notes
    assert "ARBOR JOURNAL" not in notes
    assert "LOCTITE" not in notes and "ON ASSEMBLY" not in notes
    assert "MHA-002" in arbor_spec.ASSEMBLY_STEP
    assert spec.RETAINING_COMPOUND in arbor_spec.ASSEMBLY_STEP
    assert "j=19" not in notes and "LOCATED FROM" not in notes
    assert "MATES WITH CYLINDER-GEAR BANK" not in notes
    for retired in ("INTERFERENCE", "MATCHED FIT", "ENSURES FULL ENGAGEMENT", "+/-0.5"):
        assert retired not in notes, retired


def test_part_metadata_preserves_material_finish_quantity() -> None:
    config = _config.parts("alignment-pinion")
    assert config["material_specification"] == "C36000 free-machining brass"
    assert config["finish"] == "bore as reamed; teeth as cut"
    assert int(config["quantity"]) == 1


class _FakeNote:
    def __init__(self, linked: str, resolved: str) -> None:
        self.PropertyLinkedText = linked
        self._resolved = resolved

    def GetText(self) -> str:
        return self._resolved


class _FakeDrawing:
    def __init__(self) -> None:
        self.rebuilds = 0

    def ForceRebuild3(self, top_only: bool) -> bool:
        self.rebuilds += 1
        return True


def test_material_readback_rebuilds_before_comparing_resolved_text() -> None:
    import draw_alignment_pinion as draw

    linked = 'MATERIAL: $PRPSHEET:"Material Specification"'
    resolved = "MATERIAL: C36000 free-machining brass"
    drawing = _FakeDrawing()
    draw._verify_title_material_specification(
        drawing, (_FakeNote(linked, resolved), linked, resolved)
    )
    assert drawing.rebuilds == 1


def test_material_readback_names_the_unresolved_text() -> None:
    import draw_alignment_pinion as draw

    linked = 'MATERIAL: $PRPSHEET:"Material Specification"'
    with pytest.raises(RuntimeError, match="got 'MATERIAL: '"):
        draw._verify_title_material_specification(
            _FakeDrawing(),
            (
                _FakeNote(linked, "MATERIAL: "),
                linked,
                "MATERIAL: C36000 free-machining brass",
            ),
        )


def test_tooth_thickness_is_controlled_by_the_model_base_tangent_span() -> None:
    k = spec.BASE_TANGENT_SPAN_TEETH
    # Unroll the model's own base-circle tooth: k tooth arcs plus k-1 pitches.
    unrolled = spec._BASE_RADIUS * (
        2.0 * spec._BASE_TOOTH_HALF_ANGLE + (k - 1) * 2.0 * math.pi / spec.TEETH
    )
    assert spec.BASE_TANGENT_SPAN == pytest.approx(unrolled, abs=1e-9)
    contact_r = math.hypot(spec._BASE_RADIUS, spec.BASE_TANGENT_SPAN / 2.0)
    assert spec._BASE_RADIUS < contact_r < spec.OUTSIDE_DIA / 2.0
    assert abs(contact_r - spec.PITCH_DIA / 2.0) < 0.05
    assert spec.BASE_TANGENT_SPAN_BAND == (0.0, -0.100)
    assert "BASE-TANGENT SPAN, OVER 3 TEETH (mm):  3.964 +0.000/-0.100" in spec.GEAR_DATA


def test_fit_bore_callout_names_its_process() -> None:
    import draw_alignment_pinion as draw

    assert draw.DIMENSION_CALLOUTS["ArborBoreDia"].splitlines()[0] == "REAM THRU"


def test_hand_slide_fit_rides_the_bore_callout_not_a_note() -> None:
    """Rule 6: a matched-fit acceptance belongs on the feature callout or an
    assembly step, never in a general note (Codex P2 on #832)."""
    import draw_alignment_pinion as draw

    callout = draw.DIMENSION_CALLOUTS["ArborBoreDia"]
    assert callout == spec.ARBOR_BORE_CALLOUT
    arbor = _config.parts("pinion-arbor")
    assert callout.splitlines()[1:] == [
        f"SLIDES BY HAND ON {arbor['number']}",
        arbor["title"].upper(),
    ]
    assert arbor["number"] == "MHA-102"
    assert "PINION ARBOR" in callout
    for line in spec.DRAWING_NOTES.splitlines():
        assert "SLIDE" not in line and "BY HAND" not in line, line


def test_od_at_the_general_band_keeps_tip_clearance_and_contact() -> None:
    """The .XX (+/-0.51) OD band is functionally enough for the 120T mesh."""
    import cylinder_gear_spec as gear

    general = 0.51
    alpha = math.radians(spec.PRESSURE_ANGLE_DEG)
    inv = math.tan(alpha) - alpha
    engaged_c2c = float(_config.machine("alignment_pinion", "engaged_center_distance_mm"))
    gear_base_r = gear.TEETH * spec.MODULE_MM * math.cos(alpha) / 2.0
    gear_floor_r = gear_base_r * math.cos(
        math.pi / gear.TEETH - (math.pi / (2.0 * gear.TEETH) + inv)
    )
    gear_tip_r = gear.OUTSIDE_DIA / 2.0
    # The base-chord gap floor stops the 120T tips 0.24 short of standard depth;
    # U28 (user, 2026-09-23) parks the drum 0.2425 further out so the swing
    # lands exactly there -- the configured engaged centre distance IS the
    # seated one.
    seated_c2c = gear_tip_r + spec.MIN_CHORD_FLOOR_DIA / 2.0
    assert seated_c2c - engaged_c2c == pytest.approx(0.0, abs=1e-5)

    def contact_ratio(c2c: float, tip_r: float) -> float:
        working = math.acos((spec._BASE_RADIUS + gear_base_r) / c2c)
        path = (
            math.sqrt(tip_r**2 - spec._BASE_RADIUS**2)
            + math.sqrt(gear_tip_r**2 - gear_base_r**2)
            - c2c * math.sin(working)
        )
        return path / (math.pi * spec.MODULE_MM * math.cos(alpha))

    for c2c in (engaged_c2c, seated_c2c):
        largest_tip_r = (spec.OUTSIDE_DIA + general) / 2.0
        smallest_tip_r = (spec.OUTSIDE_DIA - general) / 2.0
        assert c2c - largest_tip_r - gear_floor_r > 0.20
        assert contact_ratio(c2c, smallest_tip_r) > 1.1


def test_no_note_line_carries_a_dimension() -> None:
    """Rule 6: once part numbers and the named retaining compound are set
    aside, no note line carries a digit (Codex P1 on #814)."""
    for line in spec.DRAWING_NOTES.splitlines():
        text = re.sub(r"MHA-\d+", "", line).replace(spec.RETAINING_COMPOUND, "")
        assert not re.search(r"\d", text), line


# --- The end-face finishes attach to an edge OF the face ----------------------
# Leaf 20260926T113807Z-1-194b1994 (7b21b56c0): a point pick on the back face's
# edge-on line took a longitudinal tooth edge ending there, and the control
# check refused it.  These fakes stand in for the profile's edge scan and the
# faces each edge bounds.


class _Surface:
    def __init__(self, identity: int, **params) -> None:
        self.Identity = identity
        for name, value in params.items():
            setattr(self, name, value)


class _Face:
    def __init__(
        self, surface: _Surface, box: tuple[float, ...], *, reversed_sense=False
    ):
        self.surface = surface
        self.box = box
        self.reversed_sense = reversed_sense

    def GetSurface(self):
        return self.surface

    def GetBox(self):
        return self.box

    def FaceInSurfaceSense(self):
        return self.reversed_sense


class _Edge:
    def __init__(self, *faces: _Face) -> None:
        self.faces = faces

    def GetTwoAdjacentFaces2(self):
        return self.faces


def _profile_faces() -> dict[str, _Face]:
    from _part_pmi import _SURFACE_CYLINDER, _SURFACE_PLANE

    tip_r = spec.OUTSIDE_DIA / 2000.0
    length = spec.FACE_WIDTH / 1000.0
    return {
        "tip": _Face(
            _Surface(_SURFACE_CYLINDER, CylinderParams=(0, 0, length, 0, 0, -1, tip_r)),
            (-tip_r, -tip_r, 0.0, tip_r, tip_r, length),
        ),
        # A tooth flank: neither the tip cylinder nor an end plane.
        "flank": _Face(_Surface(4009), (0.0, 0.0, 0.0, tip_r, tip_r, length)),
        "back": _Face(
            _Surface(_SURFACE_PLANE, PlaneParams=(0, 0, 1, 0, 0, length)),
            (-tip_r, -tip_r, length, tip_r, tip_r, length),
        ),
        "front": _Face(
            _Surface(_SURFACE_PLANE, PlaneParams=(0, 0, -1, 0, 0, 0)),
            (-tip_r, -tip_r, 0.0, tip_r, tip_r, 0.0),
        ),
    }


def _profile_scan(faces: dict[str, _Face]):
    from _drawing_common import ViewEdge, ViewEdges

    tip_r = spec.OUTSIDE_DIA / 2.0
    rise = spec.OUTSIDE_DIA / 4.0  # the leader lands this high on the edge-on line
    flank = ViewEdge(
        edge=_Edge(faces["tip"], faces["flank"]),
        line=((0.0, rise, 0.0), (0.0, rise, spec.FACE_WIDTH)),
        circle=None,
        vertices=None,
    )
    arcs = {
        name: ViewEdge(
            edge=_Edge(faces["tip"], faces[name]),
            line=None,
            circle=(0.0, 0.0, z, 0.0, 0.0, 1.0, tip_r),
            vertices=None,
        )
        for name, z in (("back", spec.FACE_WIDTH), ("front", 0.0))
    }
    return ViewEdges("drum profile", (flank, arcs["back"], arcs["front"])), flank, arcs


@pytest.mark.parametrize(("face", "z_mm"), [("back", spec.FACE_WIDTH), ("front", 0.0)])
def test_end_face_finish_attaches_to_an_edge_of_its_own_face(face, z_mm) -> None:
    import _drawing_common as dc
    import draw_alignment_pinion as drawing
    from _surface_finish import surface_finish_by_key

    faces = _profile_faces()
    scan, flank, arcs = _profile_scan(faces)
    control = surface_finish_by_key(spec.SURFACE_FINISHES, f"{face}_end_face")
    # A point pick at the leader's landing on the edge-on line meets the
    # flank edge, which ENDS there -- and the control check refuses it.
    leader = (0.0, spec.OUTSIDE_DIA / 4.0, z_mm)
    assert leader in flank.line
    with pytest.raises(RuntimeError, match="does not touch controlled"):
        dc._validate_surface_finish_control_face(
            flank.edge, entity_type="EDGE", control=control, label="point pick"
        )
    # The drawing's pick is the tip arc in that face, which the check accepts.
    picked = drawing._end_face_tip_arc(scan, z_mm, label=f"{face} end face tip arc")
    assert picked is arcs[face].edge
    dc._validate_surface_finish_control_face(
        picked, entity_type="EDGE", control=control, label="tip arc"
    )
