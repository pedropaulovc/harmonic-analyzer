"""Cross-sheet offline contracts for the eight current gear drawings."""

from __future__ import annotations

from pathlib import Path

import _config
import _gear_drawing_entities
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
    ("alignment-pinion", alignment_pinion_spec),
    ("cone-gear", cone_gear_spec),
    ("crank-drive-gear", crank_drive_gear_spec),
    ("crank-pinion", crank_pinion_spec),
    ("cylinder-gear", cylinder_gear_spec),
    ("rack-pinion", rack_pinion_spec),
    ("transgear-feed-pinion", transgear_feed_pinion_spec),
    ("transgear-pinion", transgear_pinion_spec),
)

DRAWING_MODULES = (
    draw_alignment_pinion,
    draw_cone_gear,
    draw_crank_drive_gear,
    draw_crank_pinion,
    draw_cylinder_gear,
    draw_rack_pinion,
    draw_transgear_feed_pinion,
    draw_transgear_pinion,
)

CRANK_PAIR_MODULES = (
    draw_crank_drive_gear,
    draw_crank_pinion,
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


def test_notes_do_not_repeat_title_block_metadata() -> None:
    for part_name, spec in SHEETS:
        notes = spec.DRAWING_NOTES.upper()
        for duplicate in TITLE_BLOCK_OWNED_NOTE_TEXT:
            assert duplicate not in notes, f"{part_name}: {duplicate}"


def test_finish_field_does_not_repeat_generic_edge_break_instruction() -> None:
    for part_name, _spec in SHEETS:
        finish = str(_config.parts(part_name)["finish"]).upper()
        assert "DEBUR" not in finish, part_name
        assert "REMOVE BURR" not in finish, part_name
        assert "BREAK SHARP" not in finish, part_name


def test_notes_do_not_repeat_title_block_quantity() -> None:
    for part_name, spec in SHEETS:
        if part_name == "cone-gear":
            # One of each configuration is essential family-table scope, not a
            # repeat of the per-configuration title-block quantity.
            continue
        assert " REQUIRED" not in spec.DRAWING_NOTES.upper(), part_name


def test_bore_annotations_use_explicit_nonconflicting_selectors() -> None:
    for module in DRAWING_MODULES:
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "bore_edge = visible_circle_edge(" in source, module.__name__
        if module in CRANK_PAIR_MODULES:
            assert "edge_xy=bore_top" not in source, module.__name__
            assert source.count("entity=bore_edge") == 2, module.__name__
            assert source.count("leader_attach_xy=(") == 1, module.__name__
            assert "position_tolerance_m=0.080" in source, module.__name__
            assert "shoulder=True" in source, module.__name__
            continue
        assert "edge_xy=bore_top" in source, module.__name__
        assert "edge_xy=bore_bottom" not in source, module.__name__
        assert source.count("entity=bore_edge") == 1, module.__name__
        expected_tolerance = (
            "position_tolerance_m=0.008"
            if module.__name__ == "draw_cylinder_gear"
            else "position_tolerance_m=0.0001"
        )
        assert expected_tolerance in source, module.__name__
        assert "shoulder=True" in source, module.__name__


def test_crank_pair_runout_uses_tooth_tip_silhouette_topology() -> None:
    helper_source = Path(_gear_drawing_entities.__file__).read_text(
        encoding="utf-8"
    )
    # Silhouette kind (4), reached through the shared traced chokepoint rather
    # than a private GetVisibleEntities2 walk -- see
    # test_every_gear_sweep_goes_through_the_traced_chokepoint.
    assert "visible_view_entities(\n        view, 4," in helper_source
    for module in CRANK_PAIR_MODULES:
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "tooth_tip_silhouette = visible_tooth_tip_silhouette(" in source
        assert "entity=tooth_tip_silhouette" in source


def test_tooth_runout_is_stated_against_the_bore_axis_datum() -> None:
    for (part_name, spec), module in zip(SHEETS, DRAWING_MODULES, strict=True):
        if module in CRANK_PAIR_MODULES:
            source = Path(module.__file__).read_text(encoding="utf-8")
            assert 'characteristic="circular_runout"' in source, part_name
            assert 'datums=("A",)' in source, part_name
            assert 'quantity="TOOTH TIPS"' in source, part_name
            continue
        notes = spec.DRAWING_NOTES.upper()
        assert (
            "GEAR TEETH: CIRCULAR RUNOUT 0.05 MAX ABOUT DATUM A, "
            "MEASURED AT THE TOOTH TIPS" in notes
        ), part_name
        assert "WITHIN 0.05 TIR" not in notes, part_name


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


def test_the_circle_pick_prices_its_three_com_calls_separately() -> None:
    """`GetCurve` is 24.6 ms an edge against `IsCircle`'s 3.8 ms and
    `CircleParams`' 3.6 ms -- a 7x spread that one aggregate duration hides.

    Without the split, the obvious optimisation reads as "drop IsCircle" (worth
    1.8 s of 25.3 s) instead of "GetCurve is the entire bill".
    """
    helper_source = Path(_gear_drawing_entities.__file__).read_text(
        encoding="utf-8"
    )
    for attribute in ("curve_s=", "classify_s=", "params_s="):
        assert attribute in helper_source, attribute


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
