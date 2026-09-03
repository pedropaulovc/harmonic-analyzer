"""Cross-sheet offline contracts for the eight current gear drawings.

Every gear sheet follows cad/docs/drawing-simplicity-policy.md: gears are not
on the GD&T allowlist (no datums, no frames, no basics), a roughness symbol
appears only on a surface that RUNS in the assembly, the notes are at most
four part-specific lines beside a compact GEAR DATA block, and (since the
machinist review of 2026-09-02) that block carries the one thing a
micrometer can check -- the measurement over two pins from ``_gear_inspection``
-- while the dense gears show their axial stack in a cut-face-only section.
"""

from __future__ import annotations

from pathlib import Path

import _config
import _gear_drawing_entities
import _gear_inspection
import alignment_pinion_spec
import cone_gear_spec
import crank_drive_gear_spec
import crank_pinion_spec
import cylinder_gear_spec
import draw_alignment_pinion
import draw_cone_gear
import draw_crank_drive_gear
import draw_crank_pinion
import draw_cylinder_gear
import draw_rack_pinion
import draw_transgear_feed_pinion
import draw_transgear_pinion
import rack_pinion_spec
import transgear_feed_pinion_spec
import transgear_pinion_spec


SHEETS = (
    ("alignment-pinion", alignment_pinion_spec, draw_alignment_pinion),
    ("cone-gear", cone_gear_spec, draw_cone_gear),
    ("crank-drive-gear", crank_drive_gear_spec, draw_crank_drive_gear),
    ("crank-pinion", crank_pinion_spec, draw_crank_pinion),
    ("cylinder-gear", cylinder_gear_spec, draw_cylinder_gear),
    ("rack-pinion", rack_pinion_spec, draw_rack_pinion),
    ("transgear-feed-pinion", transgear_feed_pinion_spec, draw_transgear_feed_pinion),
    ("transgear-pinion", transgear_pinion_spec, draw_transgear_pinion),
)

# Every gear in the fleet now carries the same computed over-pins acceptance
# and treats whole depth as cutter-setting reference data.

# Surfaces that RUN in the assembly (policy rule 5): the cylinder gear spins
# free on the cylinder-gear shaft and its cam O.D. is the connecting-rod
# ring's track; the reducer disc and the feed pinion locked to it spin free on
# the transgear stud.  Every other gear is keyed, pressed, soldered or locked
# to its shaft, so its bore carries no roughness symbol.
RUNNING_SURFACE_SHEETS = {
    "cylinder-gear": ("cylinder_gear_bore", "cam_track"),
    "rack-pinion": ("bore",),
    "transgear-feed-pinion": ("bore",),
}

# Sheets whose projected side view was a black band of tooth edges: the side
# view is a cut-face-only SECTION A-A through the axis instead.
SECTION_SHEETS = {
    "alignment-pinion",
    "cone-gear",
    "crank-drive-gear",
    "crank-pinion",
    "cylinder-gear",
    "rack-pinion",
}

GDT_HELPERS = (
    "add_datum_feature(",
    "add_feature_control_frame(",
    "set_basic_dimension(",
    "project_part_pmi(",
    "visible_tooth_tip_silhouette(",
)

TITLE_BLOCK_OWNED_NOTE_TEXT = (
    "ALL DIMENSIONS",
    "BREAK EDGES",
    "BREAK SHARP",
    "DEBUR",
    "EDGE BREAK",
    "FINISH:",
    "GENERAL TOLERANCE",
    "MATERIAL:",
    "REMOVE BURR",
    "SHARP EDGES",
    "U.O.S.",
    "UNLESS OTHERWISE SPECIFIED",
    " UOS",
)

# GD&T vocabulary and cross-references that a note must never carry (policy
# rule 6): a datum letter, a runout, another part's number.  A roughness
# grade is a symbol on the view, never a note.
GDT_NOTE_TEXT = ("DATUM", "RUNOUT", "PERPENDICULAR", "FCF", "MHA-")


def _source(module) -> str:
    return Path(module.__file__).read_text(encoding="utf-8")


def _bore_dimension(spec) -> str:
    (feature,) = (name for name in spec.DRAWING_DIMENSIONS if name.endswith("BoreProfile"))
    (dimension,) = spec.DRAWING_DIMENSIONS[feature]
    return dimension


def test_notes_do_not_repeat_title_block_metadata() -> None:
    for part_name, spec, _module in SHEETS:
        notes = spec.DRAWING_NOTES.upper()
        for duplicate in TITLE_BLOCK_OWNED_NOTE_TEXT:
            assert duplicate not in notes, f"{part_name}: {duplicate}"


def test_finish_field_does_not_repeat_generic_edge_break_instruction() -> None:
    for part_name, _spec, _module in SHEETS:
        finish = str(_config.parts(part_name)["finish"]).upper()
        assert "DEBUR" not in finish, part_name
        assert "REMOVE BURR" not in finish, part_name
        assert "BREAK SHARP" not in finish, part_name


def test_notes_do_not_repeat_title_block_quantity() -> None:
    for part_name, spec, _module in SHEETS:
        if part_name == "cone-gear":
            # One of each configuration is essential family-table scope, not a
            # repeat of the per-configuration title-block quantity.
            continue
        assert " REQUIRED" not in spec.DRAWING_NOTES.upper(), part_name


def test_notes_are_at_most_four_lines_and_carry_no_gdt() -> None:
    for part_name, spec, _module in SHEETS:
        lines = spec.DRAWING_NOTES.split("\n")
        assert 1 <= len(lines) <= 4, f"{part_name}: {len(lines)} note lines"
        assert all(line.strip() for line in lines), f"{part_name}: blank note line"
        notes = spec.DRAWING_NOTES.upper()
        for word in GDT_NOTE_TEXT:
            assert word not in notes, f"{part_name}: {word}"
        assert "Ra " not in spec.DRAWING_NOTES, f"{part_name}: a roughness grade in a note"


def test_no_gear_sheet_carries_gdt() -> None:
    # Gears are not on the drawing-simplicity-policy.md rule-3 allowlist.
    for part_name, spec, module in SHEETS:
        source = _source(module)
        for helper in GDT_HELPERS:
            assert helper not in source, f"{part_name}: {helper}"
        assert "GEOMETRIC_TOLERANCES_MM" not in source, part_name
        assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM"), part_name
        assert not hasattr(spec, "GEOMETRIC_CONTROLS"), part_name
        assert not hasattr(spec, "PART_DATUMS"), part_name


def test_roughness_symbols_only_on_running_surfaces() -> None:
    for part_name, spec, module in SHEETS:
        source = _source(module)
        keys = RUNNING_SURFACE_SHEETS.get(part_name)
        if keys is not None:
            controls = spec.SURFACE_FINISHES
            assert tuple(control.key for control in controls) == keys, part_name
            for control in controls:
                assert control.roughness_um == 1.6, f"{part_name}: {control.key}"
                assert (
                    f'control=surface_finish_by_key(SURFACE_FINISHES, "{control.key}")'
                    in source
                ), f"{part_name}: {control.key}"
            assert controls[0].face.diameter_mm == spec.BORE_DIA, part_name
            assert source.count("add_surface_finish(") == len(controls), part_name
            assert "bore_edge = visible_circle_edge(" in source, part_name
            assert source.count("entity=bore_edge") == 1, part_name
            continue
        assert spec.SURFACE_FINISHES == (), part_name
        assert "add_surface_finish(" not in source, part_name
        assert "visible_circle_edge(" not in source, part_name
        assert "surface_finish_by_key(" not in source, part_name


def test_gear_data_blocks_share_the_compact_row_vocabulary() -> None:
    for part_name, spec, module in SHEETS:
        data = spec.GEAR_DATA
        lines = data.split("\n")
        assert lines[0] == "GEAR DATA", part_name
        assert len(lines) <= 13, f"{part_name}: {len(lines)} gear-data lines"
        for field in (
            "NUMBER OF TEETH",
            "DIAMETRAL PITCH",
            "PRESSURE ANGLE",
            "PITCH DIAMETER (REF)",
            "OUTSIDE DIAMETER",
            "WHOLE DEPTH",
            "FACE WIDTH",
            "TOOTH FORM",
        ):
            assert field in data, f"{part_name}: {field}"
        for banned in ("MODULE", "ISO 1328", "BASE-TANGENT", "DATUM", "RUNOUT"):
            assert banned not in data, f"{part_name}: {banned}"
        source = _source(module)
        assert 'adapter, "Gear Data"' in source, part_name
        assert 'adapter, "Manufacturing Notes"' in source, part_name


def test_gear_data_blocks_carry_a_computed_over_pins_acceptance() -> None:
    """The one row a micrometer can check, never typed by hand.

    Each spec's pin is the Handbook 1.92/P wire from ``_gear_inspection`` and
    the reading is regenerated from DP / N / PA (and the helix + thinning on
    the crank-drive gear), so the row on the sheet can only drift if the tooth
    system does.  The whole depth reads as reference beside it: a cutter
    setting is not an acceptance.
    """
    for part_name, spec, _module in SHEETS:
        data = spec.GEAR_DATA
        assert "WHOLE DEPTH (REF):" in data, part_name
        assert spec.PIN_DIA_MM == _gear_inspection.preferred_pin_dia_mm(
            spec.DIAMETRAL_PITCH
        ), part_name
        assert spec.OVER_PINS.usable, part_name
        assert spec.OVER_PINS.teeth == spec.TEETH, part_name
        assert spec.OVER_PINS.pin_dia_mm == spec.PIN_DIA_MM, part_name
        label, value = _gear_inspection.over_pins_row(spec.OVER_PINS)
        assert f"{label}:  {value}" in data, part_name
        assert value.endswith(_gear_inspection.OVER_PINS_BAND_TEXT), part_name
        # The DP row carries the generated tooth spacing without false decimals.
        assert (
            f"DIAMETRAL PITCH:  {_gear_inspection.diametral_pitch_text(spec.DIAMETRAL_PITCH)}"
            in data
            or f"DIAMETRAL PITCH (TRANSVERSE):  "
            f"{_gear_inspection.diametral_pitch_text(spec.DIAMETRAL_PITCH)}" in data
        ), part_name


def test_bore_callouts_name_the_process_and_hold_three_decimals() -> None:
    for part_name, spec, module in SHEETS:
        bore = _bore_dimension(spec)
        callout = module.DIMENSION_CALLOUTS[bore]
        assert callout.startswith("REAM THRU"), f"{part_name}: {callout!r}"
        assert module.DIMENSION_PRECISION[bore] == 3, part_name
        marked = set().union(*spec.DRAWING_DIMENSIONS.values())
        assert set(module.DIMENSION_CALLOUTS) <= marked, part_name
        assert set(module.DIMENSION_PRECISION) <= marked, part_name


def test_side_views_are_cut_face_sections_where_the_tooth_ring_hid_the_bore() -> None:
    for part_name, _spec, module in SHEETS:
        source = _source(module)
        if part_name in SECTION_SHEETS:
            assert "create_section_view(" in source, part_name
            assert "show_only_cut_face(adapter, section" in source, part_name
            assert 'section_label="A"' in source, part_name
            assert "RIGHT_CENTER" not in source, part_name
            assert "set_hidden_lines_visible(adapter, front)" in source, part_name
            # The cut runs vertically through the front view's axis.
            assert module.SECTION_LINE[0][0] == module.SECTION_LINE[1][0], part_name
            assert module.SECTION_LINE[0][0] == module.FRONT_CENTER[0], part_name
            assert module.SECTION_LINE[0][1] < module.FRONT_CENTER[1] < module.SECTION_LINE[1][1]
            continue
        assert "create_section_view(" not in source, part_name
        assert (
            "for view in (front, right):\n        set_hidden_lines_visible" in source
        ), part_name
    helper = _source(_gear_drawing_entities)
    assert "SetDisplayOnlySurfaceCut(True)" in helper
    assert "GetDisplayOnlySurfaceCut()" in helper


def test_hidden_lines_on_in_every_orthographic_view() -> None:
    for part_name, _spec, module in SHEETS:
        source = _source(module)
        assert "set_hidden_lines_visible(" in source, part_name
        if part_name == "alignment-pinion":
            assert "set_hidden_lines_removed" not in source, part_name  # no iso
            continue
        assert "set_hidden_lines_removed(adapter, iso)" in source, part_name
        assert source.count("set_hidden_lines_removed(") == 1, part_name


def test_every_gear_sweep_goes_through_the_traced_chokepoint() -> None:
    """No helper may re-implement the GetVisibleComponents/GetVisibleEntities2
    walk privately.

    Three of them did, and the walk is the single most expensive COM step in a
    gear drawing -- so 43.8 min of 193.7 min of drawing build time sat inside
    `drawing.build` covered by no child span. One spring_hook run took 724 s
    with every named span fast; 693 s of it was unattributable. Routing through
    `visible_view_entities` is what makes the sweep show up as its own timed
    child instead of vanishing into the caller.
    """
    helper_source = Path(_gear_drawing_entities.__file__).read_text(
        encoding="utf-8"
    )
    # The CALL forms, not the names -- both docstrings discuss these APIs by
    # name, and recording why they are expensive is the point of this change.
    assert "view.GetVisibleComponents(" not in helper_source
    assert "view.GetVisibleEntities2(" not in helper_source
    assert "from _drawing_common import visible_view_entities" in helper_source
    assert helper_source.count("visible_view_entities(") == 2  # circle + tooth tip


def test_the_circle_pick_prices_each_step_separately() -> None:
    """Every timer must bracket exactly ONE operation, binding included.

    `curve_s` first enclosed `_early_bound(edge.GetCurve(), "ICurve")`, so it
    priced the COM call AND the wrapper resolution together and reported
    24.6 ms for a call that measures 18.2 ms (Codex P2). That inflation hid the
    real finding: `_early_bound` is 7.0 s of a 27.7 s pick, comparable to
    `GetCurve`'s 8.8 s, and unlike it is not COM at all.
    """
    helper_source = Path(_gear_drawing_entities.__file__).read_text(
        encoding="utf-8"
    )
    for attribute in ("curve_s=", "classify_s=", "params_s=", "bind_s="):
        assert attribute in helper_source, attribute
    # The COM call is timed alone -- binding the result happens after the stamp.
    assert "raw_curve = edge.GetCurve()" in helper_source
    assert "_early_bound(edge.GetCurve()" not in helper_source


def test_the_refuted_sweep_optimisations_keep_their_measurements() -> None:
    """Both ways to avoid `GetCurve` were measured and both failed. The numbers
    stay next to the code so the next pass does not re-walk them."""
    helper_source = Path(_gear_drawing_entities.__file__).read_text(
        encoding="utf-8"
    )
    # GetCurveParams2 is 10x cheaper but flags 1 of 121 circles as closed.
    assert "closed=1" in helper_source
    # A second identical silhouette sweep costs the same as the first.
    assert "21.2 s" in helper_source
    # And the corrected per-call price, not the paired one it replaced.
    assert "18.2 ms" in helper_source
