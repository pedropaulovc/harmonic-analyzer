r"""Reproduction script: pen square rod (book ch. 24, pp. 64-65).

The square brass rod that carries the v-block; the wire from the
magnifying wheel ties into the cross hole near its top, so the rod (and
pen) mirror the summed motion vertically.

Dimensions: cad/DIMENSIONS.md "Chapter 24" — ~5 mm square photo-scaled
(low); length ~120 from the p.64 inset (low).

Layout: length along +Y from the origin (assembly orientation), section
centred on the origin in X, extruded +Z; wire hole along Z near the top.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pen_rod.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import _telemetry

from _common import (
    _early_bound,
    SketchDims,
    add_line_chain,
    apply_material,
    check,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _part_pmi import author_part_pmi
from _saved_part_guard import require_saved_drawing_properties
from _hole_spec import blind_cut_dia_mm
from _holes import wizard_holes
from pen_rod_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    GEOMETRIC_CONTROLS,
    PART_DATUMS,
    ROD_LENGTH,
    ROD_SECTION,
    SECTION_BAND,
    SURFACE_FINISHES,
    TOP_VIEW_NOTE,
    WIRE_HOLE_SPEC,
    WIRE_HOLE_Y,
)

PART_NAME = "pen-rod"
MATERIAL = "Brass"  # see _common.apply_material docstring

# NONSHIPPING preference diagnostic.  Keep this block bounded so the probe can
# be removed without touching the pen-rod recipe below.
_PREFERENCE_WRITES = (
    ("swWarnStartingSketchInContextAssembly", False),
    ("swExtRefNoPromptOrSave", True),
    ("swAutoSaveEnable", False),
)
_POSITIVE_CONTROL = "swSaveReminderEnable"


def _resolved_toggle_ids() -> dict[str, int]:
    """Resolve exact names from this install's registered swconst.tlb."""
    import pythoncom
    from solidworks_mcp.adapters import sw_install

    executable = sw_install.resolve_com_server_path()
    if type(executable) is not str or not executable:
        raise RuntimeError(
            "cannot locate live swconst.tlb: SldWorks.Application has no "
            "registered executable"
        )
    source = Path(executable).parent / "swconst.tlb"
    if not source.is_file():
        raise RuntimeError(f"live SOLIDWORKS type library is missing: {source}")

    typelib = pythoncom.LoadTypeLib(str(source))
    members: dict[str, int] | None = None
    for index in range(typelib.GetTypeInfoCount()):
        if typelib.GetTypeInfoType(index) != pythoncom.TKIND_ENUM:
            continue
        if typelib.GetDocumentation(index)[0] != "swUserPreferenceToggle_e":
            continue
        info = typelib.GetTypeInfo(index)
        members = {}
        for position in range(info.GetTypeAttr()[7]):
            descriptor = info.GetVarDesc(position)
            if descriptor[4] != pythoncom.VAR_CONST:
                continue
            members[info.GetNames(descriptor[0])[0]] = int(descriptor[1])
        break

    if members is None:
        raise RuntimeError(f"{source} declares no swUserPreferenceToggle_e")
    ids: dict[str, int] = {}
    for name in (*[item[0] for item in _PREFERENCE_WRITES], _POSITIVE_CONTROL):
        try:
            ids[name] = members[name]
        except KeyError:
            raise RuntimeError(
                f"swUserPreferenceToggle_e.{name} is absent from {source}"
            ) from None
    return ids


def _read_toggle(sw, name: str, preference_id: int) -> bool:
    value = sw.GetUserPreferenceToggle(preference_id)
    if type(value) is not bool:
        raise RuntimeError(
            f"{name} (id {preference_id}) returned non-Boolean {value!r}"
        )
    return value


def _telemetry_readback(
    event: str,
    *,
    context: str,
    name: str,
    preference_id: int,
    before: bool,
    requested: bool,
    after: bool,
    setter_return_type: str,
) -> None:
    fields = {
        "context": context,
        "preference_name": name,
        "id": preference_id,
        "before": before,
        "requested": requested,
        "after": after,
        "setter_return_type": setter_return_type,
    }
    _telemetry.event(event, **fields)
    _telemetry.info(f"{event} {json.dumps(fields, sort_keys=True)}", **fields)


def _probe_toggle(
    sw,
    *,
    context: str,
    name: str,
    preference_id: int,
    requested: bool | None,
) -> None:
    before = _read_toggle(sw, name, preference_id)
    requested_value = not before if requested is None else requested
    after = before
    try:
        with _telemetry.span(
            "seat.preference_probe.write",
            context=context,
            preference_name=name,
            id=preference_id,
            before=before,
            requested=requested_value,
        ) as span:
            setter_result = sw.SetUserPreferenceToggle(
                preference_id, requested_value
            )
            after = _read_toggle(sw, name, preference_id)
            setter_return_type = type(setter_result).__name__
            span.set_attribute("after", after)
            span.set_attribute("setter_return_type", setter_return_type)
            _telemetry_readback(
                "seat.preference_probe.readback",
                context=context,
                name=name,
                preference_id=preference_id,
                before=before,
                requested=requested_value,
                after=after,
                setter_return_type=setter_return_type,
            )
    finally:
        # SetUserPreferenceToggle is VT_VOID: None is the successful native
        # return.  Only readback says whether the application moved.  Restore
        # every value that did move, including the opposite-value control.
        current = _read_toggle(sw, name, preference_id)
        if current != before:
            with _telemetry.span(
                "seat.preference_probe.restore",
                context=context,
                preference_name=name,
                id=preference_id,
                before=current,
                requested=before,
            ) as span:
                setter_result = sw.SetUserPreferenceToggle(preference_id, before)
                restored = _read_toggle(sw, name, preference_id)
                setter_return_type = type(setter_result).__name__
                span.set_attribute("after", restored)
                span.set_attribute("setter_return_type", setter_return_type)
                _telemetry_readback(
                    "seat.preference_probe.restored",
                    context=context,
                    name=name,
                    preference_id=preference_id,
                    before=current,
                    requested=before,
                    after=restored,
                    setter_return_type=setter_return_type,
                )
                if restored != before:
                    raise RuntimeError(
                        f"{context}: failed to restore {name} (id {preference_id}) "
                        f"to {before!r}; read back {restored!r}"
                    )


def _probe_context(adapter, context: str, ids: dict[str, int]) -> None:
    sw = _early_bound(adapter.swApp, "ISldWorks")
    with _telemetry.span("seat.preference_probe.context", context=context):
        for name, requested in _PREFERENCE_WRITES:
            _probe_toggle(
                sw,
                context=context,
                name=name,
                preference_id=ids[name],
                requested=requested,
            )
        _probe_toggle(
            sw,
            context=context,
            name=_POSITIVE_CONTROL,
            preference_id=ids[_POSITIVE_CONTROL],
            requested=None,
        )


def _assert_empty_probe_session(sw, context: str) -> None:
    count = sw.GetDocumentCount()
    active = sw.ActiveDoc
    if type(count) is not int or isinstance(count, bool):
        raise RuntimeError(f"{context}: invalid document count {count!r}")
    if count != 0 or active is not None:
        raise RuntimeError(
            f"{context}: preference probe requires an empty session "
            f"(document_count={count}, active_document={active is not None})"
        )


async def _probe_blank_document(
    adapter, context: str, creator, ids: dict[str, int]
) -> None:
    sw = _early_bound(adapter.swApp, "ISldWorks")
    previous_context = (
        adapter.currentModel,
        adapter.currentSketch,
        adapter.currentSketchManager,
    )
    title: str | None = None
    try:
        create_result = await creator()
        if adapter.currentModel is not previous_context[0]:
            model = _early_bound(adapter.currentModel, "IModelDoc2")
            title = str(model.GetTitle() or "")
        check(f"preference probe create {context}", create_result)
        if not title:
            raise RuntimeError(f"{context}: created document has no closable title")
        count = sw.GetDocumentCount()
        active = sw.ActiveDoc
        active_title = (
            ""
            if active is None
            else str(_early_bound(active, "IModelDoc2").GetTitle() or "")
        )
        if count != 1 or active_title != title:
            raise RuntimeError(
                f"{context}: created document is not the sole active document "
                f"(document_count={count!r}, created={title!r}, active={active_title!r})"
            )
        _probe_context(adapter, context, ids)
    finally:
        try:
            if title:
                sw.CloseDoc(title)
                _assert_empty_probe_session(sw, f"{context} cleanup")
        finally:
            (
                adapter.currentModel,
                adapter.currentSketch,
                adapter.currentSketchManager,
            ) = previous_context


async def _run_preference_probe(adapter) -> None:
    sw = _early_bound(adapter.swApp, "ISldWorks")
    ids = _resolved_toggle_ids()
    with _telemetry.span("seat.preference_probe"):
        _assert_empty_probe_session(sw, "empty_before")
        _probe_context(adapter, "empty_before", ids)
        await _probe_blank_document(
            adapter, "blank_part", adapter.create_part, ids
        )
        await _probe_blank_document(
            adapter, "blank_assembly", adapter.create_assembly, ids
        )
        _assert_empty_probe_session(sw, "empty_after")
        _probe_context(adapter, "empty_after", ids)


# END NONSHIPPING preference diagnostic.


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    await _run_preference_probe(adapter)


    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the square section, the rod length and
    # the wire-hole geometry. The mm suffix is load-bearing -- this is an INCH
    # document and the equation manager reads BARE numbers in document units (an
    # unsuffixed 120 = 120 in, blowing the part up 25.4x).
    await set_global(adapter, "RodSection", f"{ROD_SECTION}mm")
    await set_global(adapter, "RodLength", f"{ROD_LENGTH}mm")
    await set_global(adapter, "WireHoleY", f"{WIRE_HOLE_Y}mm")
    # (The old WireHoleDia knob is gone: the wire hole is now a native Hole
    # Wizard feature whose standard diameter is part-owned.)

    drive_jobs: list[tuple[str, str]] = []

    # Square section, anchored at the origin corner and spanning 0..ROD_LENGTH in
    # Y (not origin-centred, so keep the rectilinear chain). Emission order: the
    # kept per-segment distance dims (one horizontal width, one vertical length;
    # the closing horizontal/vertical are redundant), THEN the anchor dims at the
    # bottom-left corner (-RodSection/2, 0): only X is non-zero, so one anchor dim.
    section = SketchDims()
    check("create_sketch section", await adapter.create_sketch("Front"))
    section_rect = [
        (-ROD_SECTION / 2.0, 0.0),
        (ROD_SECTION / 2.0, 0.0),
        (ROD_SECTION / 2.0, ROD_LENGTH),
        (-ROD_SECTION / 2.0, ROD_LENGTH),
    ]
    lines = await add_line_chain(adapter, section_rect)
    await define_rectilinear_chain(
        adapter,
        lines,
        section_rect,
        label="rod",
        dims=section,
        names=["Section", "Length", "CornerX"],
        drives=['"RodSection"', '"RodLength"', '"RodSection" / 2'],
    )
    await ensure_fully_defined(adapter, "rod outline")
    check("exit_sketch section", await adapter.exit_sketch())
    name_last_feature(adapter, "RodProfile")
    drive_jobs += section.apply(adapter, "RodProfile")
    check(
        "extrude rod",
        await adapter.create_extrusion(ExtrusionParameters(depth=ROD_SECTION)),
    )
    name_last_feature(adapter, "Rod")
    depth_dim = name_dimensions(adapter, "Rod", ["Depth"])
    drive_jobs += [(depth_dim[0], '"RodSection"')]
    v_rod = ROD_SECTION * ROD_SECTION * ROD_LENGTH
    await volume_check(adapter, "rod", v_rod, 0.005 * v_rod)

    # Wire tie-off hole near the top, drilled +Z through the 5 mm square section
    # (Z 0..ROD_SECTION) at (0, WIRE_HOLE_Y). Through-all is geometrically
    # identical to the old mid-plane both-directions cut.
    wire_cut = wizard_holes(
        adapter,
        WIRE_HOLE_SPEC,
        [[0.0, WIRE_HOLE_Y, ROD_SECTION]],
        (0.0, 0.0, 1.0),
        "wire tie-off hole",
        name="WireHole",
        placement_dims=[((None, None), ("WireZ", '"WireHoleY"'))],
        expect_dia_mm=blind_cut_dia_mm(WIRE_HOLE_SPEC),
    )
    drive_jobs += wire_cut.placement_drive_jobs
    v_wire = math.pi * (wire_cut.hole_dia_mm / 2.0) ** 2 * ROD_SECTION
    v_final = v_rod - v_wire
    await volume_check(adapter, "wire hole", v_final, 0.005 * v_rod)

    # Apply the deferred drive equations after the whole model + a rebuild exists,
    # then re-check: every equation evaluates to the value just built, so the
    # geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven pen rod (equations neutral)", v_final, 0.005 * v_rod
    )

    # Named slide axis (local Y through the origin = Front Plane ∩ Right Plane,
    # the square rod's long axis) so the pen rod runs as a prismatic joint along
    # the v-block guide in the M6 mated-DOF assembly (vertical pen travel).
    slide_axis = await name_bore_axis(
        adapter,
        "Front Plane",
        0.0,
        "Right Plane",
        0.0,
        "slide axis",
    )
    _blank_ref_axis(adapter, slide_axis)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    set_dimension_bilateral_tolerance(
        adapter, "RodProfile", "Section", *deviations(SECTION_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "Rod", "Depth", *deviations(SECTION_BAND)
    )
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # GD&T lives on the MODEL as plain annotations; the drawing imports it.
    author_part_pmi(
        adapter,
        datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS,
        surface_finishes=SURFACE_FINISHES,
    )
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Top View Note": TOP_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        (
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Top View Note",
        ),
    )
    return artefacts


def _blank_ref_axis(adapter, name: str) -> None:
    """Keep the assembly-mating axis out of saved part renders."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        name,
        "AXIS",
        0,
        0,
        0,
        False,
        0,
        null_callout(),
        0,
    ):
        raise RuntimeError(f"cannot select {name!r} to hide reference geometry")
    model.BlankRefGeom()
    model.ClearSelection2(True)


if __name__ == "__main__":
    sys.exit(run_build(build))
