"""MHA-FR-VN-52 gooseneck set screw (McMaster 91410A540): its inch sheet, offline."""

from __future__ import annotations



import draw_fr_vn_gooseneck_set_screw as draw
from _part_properties import part_drawing_unit


def test_sheet_prints_decimal_inches() -> None:
    assert part_drawing_unit("fr-vn-gooseneck-set-screw") == "in"


def test_only_the_thread_text_shelves_right_of_its_witnesses() -> None:
    assert draw.SHELVES == {"SupplierThreadDiameter": (True, "right")}
