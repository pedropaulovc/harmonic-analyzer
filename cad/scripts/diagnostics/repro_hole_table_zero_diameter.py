"""Minimal native SolidWorks repro for a bogus hole-table diameter line.

Creates an isolated rectangular plate with one four-position ANSI-inch #4
normal-clearance Hole Wizard feature and one #30 drilled Hole Wizard feature,
then creates a drawing containing one front view and one native hole table. On
the affected SolidWorks 2026 seat, each #4 SIZE cell contains the correct
through-hole callout followed by the bogus ``DIAMETER 0.00 X 0 DEG, FAR SIDE``
line after a redundant ``HoleFit=normal`` ModifyDefinition, while the #30
comparison row is correct.

No table cell is edited and no custom column is added.  The script fails unless
the native SIZE text contains both the correct through-hole size and the phantom
zero-diameter line, making the saved files a positive reproduction.

Run with SolidWorks open::

    uv run python cad/scripts/diagnostics/repro_hole_table_zero_diameter.py

Outputs land under::

    cad/out/reports/repros/hole-table-zero-diameter/
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import _telemetry  # noqa: E402
from _common import check, run_build  # noqa: E402
from _drawing_common import insert_hole_table, set_hidden_lines_removed  # noqa: E402
from _holes import HoleSpec, _early, wizard_holes  # noqa: E402
from solidworks_mcp.adapters.pywin32_adapter import null_callout  # noqa: E402
from solidworks_mcp.adapters.solidworks.drawing import (  # noqa: E402
    new_drawing,
    place_view,
    save_drawing,
    set_units_mm,
)


REPRO_DIR = (
    Path(__file__).resolve().parents[2]
    / "out"
    / "reports"
    / "repros"
    / "hole-table-zero-diameter"
)
PART_PATH = REPRO_DIR / "hole-table-zero-diameter.SLDPRT"
DRAWING_PATH = REPRO_DIR / "hole-table-zero-diameter.SLDDRW"
PDF_PATH = REPRO_DIR / "hole-table-zero-diameter.pdf"

PLATE_WIDTH_MM = 80.0
PLATE_HEIGHT_MM = 40.0
PLATE_THICKNESS_MM = 10.0
CLEARANCE_HOLES_MM = (
    (-25.0, -10.0),
    (-25.0, 10.0),
    (25.0, -10.0),
    (25.0, 10.0),
)
NUMBER_DRILL_HOLE_MM = (0.0, 0.0)
ALL_HOLES_MM = (*CLEARANCE_HOLES_MM, NUMBER_DRILL_HOLE_MM)

# A-size landscape sheet coordinates.  The 1:1 front view is centered here;
# its geometry therefore spans x=0.060..0.140 and y=0.090..0.130 metres.
VIEW_X_M = 0.100
VIEW_Y_M = 0.110
DATUM_XY_M = (0.060, 0.090)
TABLE_XY_M = (0.125, 0.210)
# #4 normal clearance is 3.251 mm on this ANSI-inch Hole Wizard table. Select
# a point on the visible circular rim, not the hole centre.
HOLE_RIM_DY_M = 0.0016255


def _table_contents(adapter: Any, table: Any) -> tuple[tuple[str, ...], ...]:
    rows = int(adapter._get_attr_or_call(table, "RowCount") or 0)
    columns = int(adapter._get_attr_or_call(table, "ColumnCount") or 0)
    return tuple(
        tuple(
            str(
                adapter._attempt(
                    lambda row=row, column=column: table.DisplayedText(row, column)
                )
                or ""
            )
            for column in range(columns)
        )
        for row in range(rows)
    )


def _assert_positive_repro(contents: tuple[tuple[str, ...], ...]) -> None:
    if len(contents) != 6 or any(len(row) != 4 for row in contents):
        raise RuntimeError(f"unexpected native hole-table shape: {contents!r}")

    size_cells = tuple(row[3] for row in contents[1:])
    bad_clearance = tuple(
        text for text in size_cells if "3.25 THRU ALL" in text and "0.00" in text
    )
    good_number_drill = tuple(
        text for text in size_cells if "3.26 THRU ALL" in text and "0.00" not in text
    )
    if len(bad_clearance) != 4 or len(good_number_drill) != 1:
        raise RuntimeError(
            "native table did not show four bad #4-clearance rows and one "
            f"clean #30 comparison row: {size_cells!r}"
        )


def _apply_redundant_normal_fit(adapter: Any) -> None:
    """Reproduce the old plain-hole edit that corrupts type 25 into type 26."""
    model = adapter.currentModel
    feature = model.FeatureByName("ClearanceHoles")
    if feature is None:
        raise RuntimeError("ClearanceHoles feature is missing")
    definition = _early(feature.GetDefinition(), "IWizardHoleFeatureData2")
    if int(definition.Type) != 25:
        raise RuntimeError(f"expected initial swHoleThru type 25, got {definition.Type}")
    if not definition.AccessSelections(model, None):
        raise RuntimeError("AccessSelections failed for redundant HoleFit repro")
    definition.HoleFit = 1  # swWzdHoleScrewClearanceNormal
    if not feature.ModifyDefinition(
        definition._oleobj_, model, null_callout()
    ):
        raise RuntimeError("redundant normal HoleFit ModifyDefinition failed")
    model.EditRebuild3()
    corrupted = _early(feature.GetDefinition(), "IWizardHoleFeatureData2")
    if int(corrupted.Type) != 26 or bool(corrupted.FarSideCounterSink):
        raise RuntimeError(
            "redundant normal HoleFit did not reproduce type 26 / far-side false: "
            f"type={corrupted.Type}, far={corrupted.FarSideCounterSink}"
        )
    _telemetry.success("redundant normal HoleFit reproduced type 25 -> 26 corruption")


async def build(adapter: Any) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    REPRO_DIR.mkdir(parents=True, exist_ok=True)

    with _telemetry.span("repro.part"):
        check("create repro part", await adapter.create_part())
        check("create plate sketch", await adapter.create_sketch("Front"))
        check(
            "add plate rectangle",
            await adapter.add_rectangle(
                -PLATE_WIDTH_MM / 2.0,
                -PLATE_HEIGHT_MM / 2.0,
                PLATE_WIDTH_MM / 2.0,
                PLATE_HEIGHT_MM / 2.0,
            ),
        )
        check("exit plate sketch", await adapter.exit_sketch())
        check(
            "extrude plate",
            await adapter.create_extrusion(
                ExtrusionParameters(depth=PLATE_THICKNESS_MM)
            ),
        )
        wizard_holes(
            adapter,
            HoleSpec("clearance", "#4"),
            [[x, y, 0.0] for x, y in CLEARANCE_HOLES_MM],
            (0.0, 0.0, -1.0),
            "#4 normal-clearance through holes",
            name="ClearanceHoles",
        )
        _apply_redundant_normal_fit(adapter)
        wizard_holes(
            adapter,
            HoleSpec("drilled_number", "#30"),
            [[*NUMBER_DRILL_HOLE_MM, 0.0]],
            (0.0, 0.0, -1.0),
            "#30 drilled through hole",
            name="NumberDrillHole",
        )
        check(
            f"save repro part -> {PART_PATH}", await adapter.save_file(str(PART_PATH))
        )

    with _telemetry.span("repro.drawing"):
        new_drawing(adapter)
        set_units_mm(adapter, decimals=2)
        front = place_view(
            adapter,
            str(PART_PATH),
            "*Front",
            VIEW_X_M,
            VIEW_Y_M,
            scale=(1.0, 1.0),
        )
        set_hidden_lines_removed(adapter, front)
        table = insert_hole_table(
            adapter,
            front,
            datum_xy=DATUM_XY_M,
            hole_points=tuple(
                (
                    VIEW_X_M + x / 1000.0,
                    VIEW_Y_M + y / 1000.0 + HOLE_RIM_DY_M,
                )
                for x, y in ALL_HOLES_MM
            ),
            anchor_xy=TABLE_XY_M,
            label="minimal #4-clearance / #30 comparison repro",
        )
        contents = _table_contents(adapter, table)
        _telemetry.info(f"native hole-table contents: {contents!r}")
        _assert_positive_repro(contents)
        outputs = save_drawing(
            adapter,
            str(DRAWING_PATH),
            pdf_path=str(PDF_PATH),
        )
        if set(outputs) != {"drawing", "pdf"}:
            raise RuntimeError(f"repro drawing outputs are incomplete: {outputs!r}")

    _telemetry.success(f"positive native hole-table repro saved under {REPRO_DIR}")
    return {"part": str(PART_PATH), **outputs}


if __name__ == "__main__":
    _telemetry.set_service("diagnostic-hole-table-repro")
    sys.exit(run_build(build))
