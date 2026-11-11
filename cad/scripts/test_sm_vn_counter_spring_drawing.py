"""Offline contracts for the purchased 1330K524 reference sheet."""

from __future__ import annotations

import _purchased_fastener_drawing as purchased
import sm_vn_counter_spring_notes as notes
import sm_vn_counter_spring_spec as spec
from spring_mount_geom import counter_force_n


def test_installed_spring_stays_within_catalogue_load_envelope() -> None:
    assert spec.FREE_LENGTH_MM <= spec.INSTALLED_LENGTH_MM <= spec.MAX_LENGTH_MM
    assert counter_force_n(spec.INSTALLED_LENGTH_MM) < spec.MAXIMUM_LOAD_N


def test_supplier_maximum_is_native_not_rounded_print_geometry() -> None:
    import math

    assert math.isclose(spec.FREE_LENGTH_MM, 10.00 * 25.4)
    assert math.isclose(spec.MAX_LENGTH_MM, 421.6146)
    assert not math.isclose(spec.MAX_LENGTH_MM, 16.60 * 25.4)
    assert math.isclose(spec.SUPPLIER_COIL_OD_MM, 0.500 * 25.4)
    assert math.isclose(spec.SUPPLIER_WIRE_DIA_MM, 0.063 * 25.4)
    assert spec.SUPPLIER_PRECISION == {
        "SupplierFreeLength": 2, "SupplierMaximumLength": 2,
        "SupplierCoilOD": 3, "SupplierWireDiameter": 3,
    }


def test_footer_prints_every_catalogue_fact_once_in_four_lines() -> None:
    # Owner ruling on #2129: at most four printed footer lines, counting the
    # generic heading and general line; drop no fact, add no number. Coil OD
    # and wire ride in the catalogue designation on the ITEM row.
    item = purchased.check_item(notes.ITEM, label="counter spring")
    assert item == "DOUBLE-LOOP EXTENSION SPRING, COIL OD (Ø.500), WIRE (Ø.063)"
    lines = purchased.note_lines(notes.DRAWING_NOTES, label="counter spring")
    data = purchased._supplier_data_lines(notes.SUPPLIER_DATA, label="counter spring")
    printed = (*lines, *data, purchased._GENERAL_TEXT[False])
    assert printed == (
        "SHOWN AT INSTALLED LENGTH (13.63); FREE (10.00), MAX (16.60), ALL INSIDE LOOPS.",
        "SUPPLIER OPERATING DATA (REFERENCE):",
        "RATE (1.78 LBF/IN) AND INITIAL TENSION (3.84 LBF) UNTOLERANCED",
        "PURCHASED PART, USED AS SUPPLIED. VIEWS ARE REFERENCE ONLY.",
    )
    assert len(printed) == 4
    # The note line shares the footer's text run with the longest general
    # line the generic footer prints (72 characters); it stays under the
    # ~83-character worst-case width of _NOTE_X.._FOOTER_RIGHT.
    assert all(len(line) <= 83 for line in printed)
    import draw_sm_vn_counter_spring as drawing

    assert drawing.ITEM is notes.ITEM
    assert drawing.SUPPLIER_DATA is notes.SUPPLIER_DATA
