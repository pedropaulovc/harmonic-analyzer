r"""Reproduction script: pinion lever retention pin (book ch. 25; MHA-135).

U8 ruled a match-drilled cross-pin between the engage lever's hub and the lift
rod ("retention pin shown at 3 o'clock", ch25 p.68 ``page002_img08``: a small
flush dot on the domed hub); U36 sized it -- a plain 1/16 in drill-rod pin cut
overlength (PIN_LEN), driven through the hole match-drilled at assembly at
mid-engagement, then trimmed and peened flush at both ends.  Webs at the worst case: rod
2.38 each side, hub wall 3.32.

Layout: pin axis along local X, centred on the origin (x +-PIN_LEN/2), so the
assembly seats it on the lift rod's "lever pin" axis with its Right Plane on
the rod's Right Plane.  The pin is a Front-plane half-profile revolved about
that axis (the crank-pinion-pin idiom), so its diameter and length both
import into the *Front side view (rule 7, turned parts).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pinion_lever_pin.py
"""

from __future__ import annotations

import math
import sys

import _config
import _telemetry
from _common import (
    POLISHED_STEEL,
    _early_bound,
    SketchDims,
    active_configuration_name,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _grouped_bom_properties import apply_grouped_bom_properties
from _saved_part_guard import require_saved_drawing_properties
from pinion_lever_pin_geometry import INSTALLED_CONFIG, INSTALLED_LEN
from pinion_lever_pin_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    PIN_DIA,
    PIN_DIA_BAND,
    PIN_LEN,
)

PART_NAME = "pinion-lever-pin"
MATERIAL = "Plain Carbon Steel"  # annealed drill rod: soft enough to peen
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
)

PIN_R = PIN_DIA / 2.0
V_PIN = math.pi * PIN_R**2 * PIN_LEN
V_INSTALLED = math.pi * PIN_R**2 * INSTALLED_LEN


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreateConfigurationParameters,
        RevolveParameters,
        SetGlobalVariableParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing (INCH
    # document; the equation manager reads bare numbers in document units).
    await set_global(adapter, "PinDia", f"{PIN_DIA}mm")
    await set_global(adapter, "PinLen", f"{PIN_LEN}mm")

    # Half-profile on the Front Plane (sketch x -> model X, y -> model Y): the
    # axis centerline along X through the origin and the rectangle above it,
    # centred on the origin -- the lift rod's axis in the assembly.  Its two
    # dimensions are the print's two: the length along the outline and the
    # diameter as a doubled centerline-to-outline dim.
    half = PIN_LEN / 2.0
    pin = SketchDims()
    check("create_sketch pin", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check("axis centerline", await adapter.add_centerline(-half, 0.0, half, 0.0))
    profile_pts = [(-half, 0.0), (-half, PIN_R), (half, PIN_R), (half, 0.0)]
    profile_lines = await add_line_chain(adapter, profile_pts)
    set_sketch_direct_db(adapter, False)
    n = len(profile_lines)
    for i, line in enumerate(profile_lines):
        (_, y1), (_, y2) = profile_pts[i], profile_pts[(i + 1) % n]
        direction = "horizontal" if y1 == y2 else "vertical"
        check(
            f"pin {direction} {line}",
            await adapter.add_sketch_constraint(line, None, direction),
        )
    outline = profile_lines[1]
    await dimension_between(
        adapter,
        f"{outline}.start",
        f"{outline}.end",
        "horizontal_distance",
        PIN_LEN,
        "pin PinLen",
    )
    pin.record("PinLen", '"PinLen"')
    await add_diametric_linear_dimension(
        adapter, axis, outline, (-half / 2.0, PIN_R + 4.0), "PinDia"
    )
    pin.record("PinDia", '"PinDia"')
    start = f"{profile_lines[0]}.start"
    check(
        "pin end on the axis",
        await adapter.add_sketch_constraint(start, "origin", "horizontal_points"),
    )
    await dimension_between(
        adapter, start, "origin", "horizontal_distance", half, "pin centred on origin"
    )
    pin.record("PinHalfLen", '"PinLen" / 2')
    await ensure_fully_defined(adapter, "pin sketch")
    check("exit_sketch pin", await adapter.exit_sketch())
    name_last_feature(adapter, "PinProfile")
    drive_jobs = pin.apply(adapter, "PinProfile")
    check("revolve pin", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Pin")
    volume = await volume_check(adapter, "pin", V_PIN, 0.005 * V_PIN)
    res = await adapter.get_mass_properties()
    com = res.data.center_of_mass
    if com is None or any(abs(c) > 1e-6 for c in com):
        raise RuntimeError(f"lever pin is not centred on its origin (COM {com})")

    # Named pin axis (Axis1, along X): coaxial with the lift rod's "lever pin"
    # cross-hole axis in the assembly.
    await name_bore_axis(adapter, "Top Plane", 0.0, "Front Plane", 0.0, "pin axis")

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven pin (equations neutral)", volume, 0.005 * V_PIN)

    # Every edit to the model -- the drawing support (the stock band, the
    # marked set, the model-owned decimal places), the material and the
    # appearance -- precedes the INSTALLED split.  Each one made after it
    # touched only the active configuration and left INSTALLED stale
    # (IConfiguration.NeedsRebuild) in the saved part, so drive-train opened
    # NeedsRebuild2=1: set_dimension_bilateral_tolerance (pc-lever-pin-diag)
    # and, once that moved, apply_material, which sets the ACTIVE
    # configuration's material (pc-lever-pin-diag2).  Made before the split,
    # INSTALLED is copied from a finished Default and both configurations'
    # rebuilds below are the last model edits.  #928's save guard still
    # rebuilds any stale configuration; this keeps its happy path clean.
    set_dimension_bilateral_tolerance(
        adapter, "PinProfile", "PinDia", *deviations(PIN_DIA_BAND)
    )
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)

    # Installed configuration (Codex #858 P2): the drive train places the pin
    # trimmed and peened flush with the MHA-059 hub.  The default stays the
    # overlength cut the drawing prints, and both carry one MHA-135 BOM
    # identity.  PinLen is set per configuration in each, so neither inherits
    # the other's length.
    default_config = active_configuration_name(adapter)
    check(
        f"create_configuration {INSTALLED_CONFIG}",
        await adapter.create_configuration(
            CreateConfigurationParameters(
                name=INSTALLED_CONFIG, comment="trimmed and peened flush with the hub"
            )
        ),
    )
    for name, length in ((default_config, PIN_LEN), (INSTALLED_CONFIG, INSTALLED_LEN)):
        check(
            f"PinLen = {length} in {name}",
            await adapter.set_global_variable(
                SetGlobalVariableParameters(
                    name="PinLen", expression=f"{length}mm", configuration=name
                )
            ),
        )
    check(
        f"activate {INSTALLED_CONFIG}",
        await adapter.set_active_configuration(INSTALLED_CONFIG),
    )
    await force_rebuild(adapter)
    await volume_check(adapter, "installed pin", V_INSTALLED, 0.005 * V_INSTALLED)
    check(
        f"re-activate {default_config}",
        await adapter.set_active_configuration(default_config),
    )
    await force_rebuild(adapter)
    await volume_check(adapter, "manufactured pin (default)", volume, 0.005 * V_PIN)
    grouped_spec = _config.parts(PART_NAME)
    apply_grouped_bom_properties(
        adapter,
        [default_config, INSTALLED_CONFIG],
        part_number=str(grouped_spec["number"]),
        description=str(grouped_spec["title"]),
    )
    await report_mass_properties(adapter)
    require_material_in_every_configuration(adapter, (default_config, INSTALLED_CONFIG))
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


def require_material_in_every_configuration(
    adapter, configurations: tuple[str, ...]
) -> None:
    """Read each configuration's material back; raise unless all are MATERIAL.

    ``apply_material`` sets the ACTIVE configuration's material only
    (``IPartDoc::SetMaterialPropertyName2``), so a configuration split before
    it could carry no material, and drive-train would take MHA-135's mass
    from the wrong density.  Every configuration is logged before any
    raise, so a failing leaf still shows what each one reads.
    """
    part = _early_bound(adapter.currentModel, "IPartDoc")
    readings: dict[str, str] = {}
    for name in configurations:
        # Early-bound: the retval, then the [out] database.
        material, database = part.GetMaterialPropertyName2(name)
        readings[name] = str(material or "")
        _telemetry.info(f"material in {name}: {material!r} (database {database!r})")
    wrong = {name: got for name, got in readings.items() if got != MATERIAL}
    if wrong:
        raise RuntimeError(
            f"{PART_NAME}: configurations {wrong} do not carry {MATERIAL!r}"
        )
    _telemetry.success(f"{MATERIAL} in every configuration {list(readings)}")


if __name__ == "__main__":
    sys.exit(run_build(build))
