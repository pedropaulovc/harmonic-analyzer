"""Every part drawing's source part stamps the properties its title block needs.

A drawing reads its title block from the source part's custom properties and
fails at build time when a required one is missing (``read_required_properties``).
The warm build of integ 9a0f50b1c lost ``drawing:dt_cylinder_end_disc`` that way:
the #743 rebuild of MHA-DT-26 never called ``apply_drawing_properties``, so
Material Specification / Finish / Quantity were never stamped.  This contract
catches the same gap offline, across every registered part drawing.

"Stamped" is static and deliberately generous: the keys ``part_properties``
returns for the part, every string literal in the part's build script and in
the direct repo-local modules it imports (``_drawing_marks`` aside, whose literals only
count through a call to ``apply_drawing_properties``), plus that helper's keys
when the build calls it.  Configured document properties are stricter: only
keys in the mapping actually passed to ``apply_drawing_properties`` count,
not unused metadata or readback requirements. Their finite metadata tuples,
tables and prefix comprehensions are inspected without importing producers or
executing Python. Unknown shapes fail closed. SolidWorks-free.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from _drawing_registry import DRAWINGS

SCRIPTS = Path(__file__).resolve().parent


PART_DRAWINGS = sorted(
    (drawing for drawing in DRAWINGS if drawing.source_kind == "part"),
    key=lambda drawing: drawing.name,
)


def test_every_part_drawing_is_under_test() -> None:
    assert len(PART_DRAWINGS) >= 90


@pytest.mark.parametrize("drawing", PART_DRAWINGS, ids=lambda drawing: drawing.name)
def test_source_part_stamps_every_required_property(drawing) -> None:
    build = SCRIPTS / f"build_{drawing.part}.py"
    assert build.is_file(), f"{drawing.name}: no build script {build.name}"
