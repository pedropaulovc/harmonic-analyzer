r"""Create the complete cone-gear batch drawing package (MHA-013).

Every configured family member T006..T120 by six receives a standalone sheet.
Each sheet selects its own part configuration, imports the native model-owned
blank diameter, bore, face width, and driving circular-tooth-thickness
requirement, and carries its own gear data and title-block alloy.  The bore and
tooth-thickness bands are authored by ``build_cone_gear`` from the named shaft
and gear-mesh fits; this drawing only arranges and verifies them.

There are no datums or feature-control frames.  Hidden lines communicate no
additional manufacturing fact on these plain through-bored spur gears, so all
three views remain hidden-lines-removed.  The one finish symbol belongs to the
fitted bore.  The approved attachment note permits solder/silver-braze or
Loctite 638/648 and adds no key, pin, set screw, or hub.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    _INSERT_DIMS_MARKED,
    DrawingOutputs,
    add_note,
    add_property_linked_note,
    add_surface_finish,
    assert_imported_precision,
    check_drawing_layout,
    create_blank_drawing_sheets,
    curate_dimensions,
    delete_unnamed_imports,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from cone_gear_notes import CYLINDER_MATE_NUMBER
from cone_gear_spec import (
    CONFIGURATION_TEETH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FACE_WIDTH,
    MODULE_MM,
    bore_dia_mm,
    bore_surface_finish,
)
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view


SPEC = DRAWINGS_BY_NAME["cone_gear"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_NAMES = tuple(f"T{teeth:03d}" for teeth in CONFIGURATION_TEETH)
# Discrete standard ratios keep the face view legible while the 6.5 mm face
# width still fits in the side view on the smallest gears.
_SCALE_BY_TEETH = {
    6: (8.0, 1.0),
    12: (6.0, 1.0),
    18: (5.0, 1.0),
    24: (4.0, 1.0),
    30: (3.0, 1.0),
    36: (3.0, 1.0),
    42: (3.0, 1.0),
    48: (5.0, 2.0),
    54: (5.0, 2.0),
    60: (2.0, 1.0),
    66: (2.0, 1.0),
    72: (2.0, 1.0),
    78: (2.0, 1.0),
    84: (2.0, 1.0),
    90: (3.0, 2.0),
    96: (3.0, 2.0),
    102: (3.0, 2.0),
    108: (3.0, 2.0),
    114: (3.0, 2.0),
    120: (3.0, 2.0),
}
SHEET_SCALES = {
    f"T{teeth:03d}": _SCALE_BY_TEETH[teeth] for teeth in CONFIGURATION_TEETH
}
SHEET_SCALE = SHEET_SCALES[SHEET_NAMES[0]]

FRONT_CENTER = (0.090, 0.145)
RIGHT_CENTER = (0.235, 0.145)
ISO_CENTER = (0.350, 0.145)
GEAR_DATA_POS = (0.215, 0.247)
MANUFACTURING_NOTES_POS = (0.015, 0.263)
SHEET_COUNT_POS = (0.350, 0.263)

DIMENSION_CALLOUTS = {
    "BoreCutDia": "REAM THRU",
    "ToothThickness": (
        "CIRCULAR TOOTH THICKNESS AT PITCH DIA; "
        f"BACKLASH WITH {CYLINDER_MATE_NUMBER} ACCEPT AT ASSEMBLY"
    ),
}


def outside_dia_mm(teeth: int) -> float:
    return (teeth + 2) * MODULE_MM


def rendered_half_od(teeth: int) -> float:
    numerator, denominator = _SCALE_BY_TEETH[teeth]
    return outside_dia_mm(teeth) * numerator / (denominator * 2000.0)


def rendered_half_face_width(teeth: int) -> float:
    numerator, denominator = _SCALE_BY_TEETH[teeth]
    return FACE_WIDTH * numerator / (denominator * 2000.0)


def front_keep(teeth: int) -> dict[str, tuple[float, float]]:
    half_od = rendered_half_od(teeth)
    return {
        "BlankDia": (FRONT_CENTER[0], FRONT_CENTER[1] + half_od + 0.012),
        "BoreCutDia": (
            FRONT_CENTER[0] - half_od - 0.025,
            FRONT_CENTER[1] - half_od - 0.010,
        ),
        "ToothThickness": (
            FRONT_CENTER[0] + half_od + 0.035,
            FRONT_CENTER[1] - half_od - 0.010,
        ),
    }


def right_keep(teeth: int) -> dict[str, tuple[float, float]]:
    return {
        "FaceWidth": (
            RIGHT_CENTER[0],
            RIGHT_CENTER[1] + rendered_half_od(teeth) + 0.012,
        )
    }


def _tooth_pattern_feature(source_model: Any) -> Any:
    """Return the one circular feature pattern in the saved cone-gear part."""
    matches: list[Any] = []
    raw = source_model.FirstFeature()
    while raw is not None:
        feature = _early_bound(raw, "IFeature")
        if "cirpattern" in str(feature.GetTypeName2()).casefold():
            matches.append(feature)
        raw = feature.GetNextFeature()
    if len(matches) != 1:
        names = [str(feature.Name) for feature in matches]
        raise RuntimeError(
            f"saved cone gear must have one circular pattern; found {names!r}"
        )
    return matches[0]


def _assert_saved_configuration_topology(
    adapter: Any, source_model: Any
) -> None:
    """Prove every persisted configuration contains its solved tooth pattern."""
    pattern = _tooth_pattern_feature(source_model)
    pattern_name = str(pattern.Name)
    failures: list[str] = []
    observations: list[str] = []
    # Positive control first, then the smallest configuration that the drawing
    # exposed as a smooth blank, then the remainder of the family.
    ordered = (CONFIGURATION_TEETH[-1], *CONFIGURATION_TEETH[:-1])
    for teeth in ordered:
        configuration = f"T{teeth:03d}"
        if not bool(source_model.ShowConfiguration2(configuration)):
            failures.append(f"{configuration}: ShowConfiguration2 failed")
            continue
        manager = _early_bound(
            source_model.ConfigurationManager, "IConfigurationManager"
        )
        active = _early_bound(manager.ActiveConfiguration, "IConfiguration")
        observed = str(active.Name)
        needs_rebuild = bool(active.NeedsRebuild)
        part = _early_bound(source_model, "IPartDoc")
        bodies = tuple(part.GetBodies2(0, False) or ())
        face_count = (
            int(_early_bound(bodies[0], "IBody2").GetFaceCount())
            if len(bodies) == 1
            else 0
        )
        states = pattern.IsSuppressed2(3, [configuration])
        if not isinstance(states, (list, tuple)):
            states = (states,)
        suppressed = len(states) != 1 or bool(states[0])
        definition = _early_bound(
            pattern.GetDefinition(), "ICircularPatternFeatureData"
        )
        instances = int(definition.TotalInstances)
        error_result = pattern.GetErrorCode2()
        if not isinstance(error_result, (list, tuple)) or len(error_result) < 2:
            raise RuntimeError(
                f"{configuration}: unreadable {pattern_name} error state "
                f"{error_result!r}"
            )
        error_code = int(error_result[0] or 0)
        is_warning = bool(error_result[1])
        observation = (
            f"{configuration}: active={observed}, needs_rebuild={needs_rebuild}, "
            f"{pattern_name} instances={instances}, suppressed={suppressed}, "
            f"error={error_code}, warning={is_warning}, bodies={len(bodies)}, "
            f"faces={face_count}"
        )
        observations.append(observation)
        if (
            observed != configuration
            or needs_rebuild
            or instances != teeth
            or suppressed
            or error_code
            or len(bodies) != 1
            or face_count < 2 * teeth + 4
        ):
            failures.append(observation)
    for observation in observations:
        _telemetry.info(f"saved cone-gear topology: {observation}")
    if failures:
        raise RuntimeError(
            "saved cone-gear configuration topology is invalid: "
            + "; ".join(failures)
        )


def _configure_views(
    adapter: Any, configuration: str, views: tuple[Any, ...]
) -> None:
    """Select one source configuration and verify every view's exact readback."""
    bound_views = tuple(_early_bound(view, "IView") for view in views)
    for view in bound_views:
        view.ReferencedConfiguration = configuration
    # The common drawing chokepoint deliberately does not treat EditRebuild3's
    # BOOL as the sole health signal.  Exact configuration readback is followed
    # by model-dimension import and configuration-qualified native bore-edge
    # validation below.  IView.GetOutline cannot validate nominal geometry: the
    # adapter contract records that SolidWorks pads that box with whitespace.
    rebuild_drawing(adapter, label=f"{configuration} view configuration")
    for view in bound_views:
        observed = str(view.ReferencedConfiguration)
        if observed != configuration:
            raise RuntimeError(
                f"view configuration readback {observed!r} != {configuration!r}"
            )


def _curate_repeated_dimensions(
    adapter: Any,
    view: Any,
    *,
    keep: dict[str, tuple[float, float]],
    view_label: str,
) -> list[Any]:
    """Import a complete sheet's model dimensions, allowing cross-sheet copies.

    ``InsertModelAnnotations3``'s ``DuplicateDims`` flag means *eliminate*
    duplicates when true.  The standard curator uses true because ordinary
    drawings place each model dimension once.  This configured-family package
    must print the same driving dimensions on all twenty standalone sheets, so
    it deliberately passes false and then curates only the returned objects.
    """
    declared = set().union(*DRAWING_DIMENSIONS.values())
    unknown = sorted(set(keep) - declared)
    if unknown:
        raise RuntimeError(f"{view_label} keeps undeclared dimensions: {unknown}")

    drawing = _early_bound(adapter.currentModel, "IModelDoc2")
    ddoc = _early_bound(drawing, "IDrawingDoc")
    name = view_name(adapter, view)
    if not bool(ddoc.ActivateView(name)):
        raise RuntimeError(f"failed to activate drawing view {name!r}")
    drawing.ClearSelection2(True)
    extension = _early_bound(drawing.Extension, "IModelDocExtension")
    if not bool(
        extension.SelectByID2(
            name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
        )
    ):
        raise RuntimeError(f"failed to select drawing view {name!r}")
    result = adapter._attempt(
        lambda: ddoc.InsertModelAnnotations3(
            0,  # swImportModelItemsFromEntireModel
            _INSERT_DIMS_MARKED,
            False,  # selected view only
            False,  # allow the same model dimensions on every package sheet
            True,  # include dimensions on construction/hidden features
            False,
        ),
        default=None,
    )
    drawing.ClearSelection2(True)
    if not result or isinstance(result, str):
        raise RuntimeError(f"{view_label} imported no marked model dimensions")
    annotations = delete_unnamed_imports(adapter, list(result))
    names = {dimension_name(adapter, annotation) for annotation in annotations}
    delete = tuple(sorted(name for name in names if name and name not in keep))
    curated = curate_dimensions(
        adapter, annotations, delete=delete, reposition=dict(keep)
    )
    present = {dimension_name(adapter, annotation) for annotation in curated}
    missing = sorted(set(keep) - present)
    if missing:
        raise RuntimeError(
            f"{view_label} is missing model dimensions {missing}; "
            f"available={sorted(present)}"
        )
    return curate_dimensions(adapter, curated, reposition=dict(keep))


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-gear source", await adapter.open_model(str(SOURCE)))
    source_model = _early_bound(adapter.currentModel, "IModelDoc2")
    _assert_saved_configuration_topology(adapter, source_model)
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="cone-gear batch")
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Gear Batch Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone gear; configured T006 through T120 by six",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    ddoc = _early_bound(drawing_model, "IDrawingDoc")

    for sheet_index, teeth in enumerate(CONFIGURATION_TEETH, start=1):
        configuration = f"T{teeth:03d}"
        view_scale = SHEET_SCALES[configuration]
        if not ddoc.ActivateSheet(configuration):
            raise RuntimeError(f"failed to activate cone-gear sheet {configuration}")

        front = place_view(
            adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=view_scale
        )
        right = place_view(
            adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=view_scale
        )
        iso = place_view(
            adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=view_scale
        )
        views = (front, right, iso)
        _configure_views(adapter, configuration, views)
        for view in views:
            set_hidden_lines_removed(adapter, view)

        front_annotations = _curate_repeated_dimensions(
            adapter,
            front,
            keep=front_keep(teeth),
            view_label=f"{configuration} front",
        )
        right_annotations = _curate_repeated_dimensions(
            adapter,
            right,
            keep=right_keep(teeth),
            view_label=f"{configuration} right",
        )
        annotations = [*front_annotations, *right_annotations]
        set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
        assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
        if not auto_center_marks(adapter, front, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center mark on {configuration}")

        numerator, denominator = view_scale
        bore_radius = bore_dia_mm(teeth) * numerator / (denominator * 2000.0)
        half_od = rendered_half_od(teeth)
        add_surface_finish(
            adapter,
            front,
            edge_xy=(FRONT_CENTER[0] + bore_radius, FRONT_CENTER[1]),
            symbol_xy=(
                FRONT_CENTER[0] + half_od + 0.015,
                FRONT_CENTER[1] - 0.025,
            ),
            control=bore_surface_finish(teeth),
            label=f"{configuration} cone-gear bore finish",
        )

        add_property_linked_note(
            adapter, "Gear Data", *GEAR_DATA_POS, char_height=0.0025
        )
        add_property_linked_note(
            adapter, "Manufacturing Notes", *MANUFACTURING_NOTES_POS,
            char_height=0.0025,
        )
        if (
            add_note(
                adapter,
                f"SHEET {sheet_index} OF {len(SHEET_NAMES)}",
                *SHEET_COUNT_POS,
            )
            is None
        ):
            raise RuntimeError(f"failed to stamp sheet count on {configuration}")
        rebuild_drawing(adapter, label=f"{configuration} layout audit")
        check_drawing_layout(
            adapter, layout=SPEC.layout, stem=f"cone-gear {configuration}"
        )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Gear Batch Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts={name: SPEC.layout for name in SHEET_NAMES},
        sheet_scales=SHEET_SCALES,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
