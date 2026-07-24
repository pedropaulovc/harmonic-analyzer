from __future__ import annotations

import re
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parent
HELPER = SCRIPTS / "_drawing_common.py"


def test_datum_position_gate_is_one_millimetre_and_observable() -> None:
    source = HELPER.read_text(encoding="utf-8")

    assert "position_tolerance_m: float = 0.001" in source
    assert '_telemetry.event("drawing.datum_selection_request"' in source
    assert '_telemetry.event("drawing.datum_position_readback"' in source
    assert "_telemetry.info(position_message, **position_fields)" in source
    assert "_telemetry.warn(position_message, **position_fields)" in source
    for field in (
        "requested_x_m",
        "requested_y_m",
        "expected_x_m",
        "expected_y_m",
        "actual_x_m",
        "actual_y_m",
        "position_error_mm",
        "position_tolerance_mm",
        "normalized_expectation",
        "selection_mode",
        "entity_type",
        "edge_x_m",
        "edge_y_m",
        "datum_position_signal",
    ):
        assert f'"{field}"' in source


def test_datum_call_sites_do_not_restore_submillimetre_gates() -> None:
    violations: list[str] = []
    pattern = re.compile(
        r"position_tolerance_m=(\d+(?:\.\d+)?(?:e[+-]?\d+)?),", re.IGNORECASE
    )
    for path in sorted(SCRIPTS.glob("draw_*.py")):
        source = path.read_text(encoding="utf-8")
        for match in pattern.finditer(source):
            if float(match.group(1)) < 0.001:
                violations.append(f"{path.name}:{match.group(1)}")

    assert not violations, f"submillimetre datum position gates: {violations}"
