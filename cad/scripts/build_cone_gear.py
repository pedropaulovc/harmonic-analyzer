r"""Reproduction script: cone gear (book ch. 12, pp. 16-21) -- parametric prototype.

One part, configuration-driven tooth count (plan M4: prototype 3 configs
before committing to the full 6..120-step-6 set of 20). All config-varying
geometry is equation-driven so a configuration switch regenerates the gear
from ``ToothCount``/``DP``/``PA`` alone:

* Equation-manager globals carry the involute math (base/tip radii in
  INCHES, involute parameter span, tooth-gap angles). Two parser facts
  probed live on SW 2026: the equation manager evaluates trig in DEGREES
  (``atn`` returns degrees too), and ``CreateEquationSpline2`` expressions
  evaluate lengths in DOCUMENT units (the configured part template is IPS),
  NOT metres -- inch-valued globals keep the two parsers consistent, and a
  blank-volume self-check right after the first extrude fails fast if the
  template's units ever change.
* The blank (two half circles at tip radius ``Ra``) and the six-entity
  tooth-gap profile (two involute flanks, base chord, two radial extensions,
  outer clearance arc) are all ``CreateEquationSpline2`` curves referencing
  the globals; parameter ranges are kept numeric (t in [0,1]) so only the
  expression parser needs global support.
* One gap is cut through the blank, then circular-patterned about the gear
  axis; the pattern instance count is equation-linked to ``ToothCount``.

Tooth-gap profile derivation (standard involute, polar form): a point of the
involute of base radius ``Rb`` at parameter t sits at radius ``Rb*sqrt(1+t^2)``
and polar angle ``phi - atan(t)`` where ``phi`` is the rolling angle offset.
With ``Delta = pi/(2N) + inv(PA)`` (half tooth angular thickness at the base
circle, ``inv`` the involute function), the gap between tooth 0 (centred on
+X) and tooth 1 is bounded below by tooth 0's upper flank (the mirrored
involute starting at angle ``+Delta``) and above by tooth 1's lower flank
(the involute starting at ``Gamma - Delta``, ``Gamma = 2*pi/N``).

Prototype scope notes:

* **No bore/keyway yet**: at DP 30 the 6-tooth gear's OD is 6.77 mm --
  *smaller than the 9.5 mm cone shaft* (DIMENSIONS.md ch. 12). The small
  cone gears must be integral with a reduced shaft section; bore/keyway
  join in the full pass once the mounting is resolved (Appendix C).
* Root geometry is simplified: the gap floor is the chord at the base
  circle, not the true root circle + trochoid fillet (for N >= 96 the base
  circle is slightly inside root, for small N teeth come out stub-form --
  the 6T gear is severely undercut at standard proportions anyway).

Dimensions: cad/DIMENSIONS.md "Chapter 12" -- DP 30 / PA 14.5 deg (module
resolved M4 prep), face width 7 mm (annotated p.18), tooth counts 6k.

Layout: gear axis = Z through the origin, blank extruded +Z from the Front
plane (z = 0..7 mm).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_cone_gear.py
"""

from __future__ import annotations

import math
import sys
from typing import Any

from _common import (
    OUT_PNG,
    _read_member,
    add_line_chain,
    apply_material,
    check,
    ensure_fully_defined,
    feature_name_by_type,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "cone-gear"
MATERIAL = "Brass"  # ch. 13 text: polished brass gear stock; cone set matches

DP = 30.0  # teeth per inch of pitch diameter, DIMENSIONS.md ch12 (high)
PA_DEG = 14.5  # pressure angle, period-typical assumption (low)
FACE_WIDTH = 7.0  # mm, photo callout p.18 (high)

# Cut clearance radius (inches -- document units, see module docstring)
# beyond the largest tip radius (120T OD/2 = 2.033") so the gap profile
# always closes outside the blank.
R_CLEAR_IN = 60.0 / 25.4

PI_LIT = "3.14159265358979"  # literal pi for equation-manager expressions

# The full cone set: 20 gears, 6..120 teeth step 6 (DIMENSIONS.md ch. 12).
# The 3-config prototype pass (6/60/120) validated regeneration first, per
# plan risk #2; the same script now carries all 20 configurations.
CONFIGS = [(f"T{n:03d}", n) for n in range(6, 121, 6)]
DEFAULT_TEETH = 120  # globals' all-configuration value at authoring time


def gear_facts(teeth: int, dp: float = DP, pa_deg: float = PA_DEG) -> dict[str, float]:
    """Python mirror of the equation-manager globals (lengths in inches)."""
    pa = math.radians(pa_deg)
    rb = teeth / dp * math.cos(pa) / 2.0
    ra = (teeth + 2.0) / dp / 2.0
    tmax = math.sqrt((ra / rb) ** 2 - 1.0)
    delta = math.pi / (2.0 * teeth) + math.tan(pa) - pa
    gamma = 2.0 * math.pi / teeth
    return {
        "PArad": pa,
        "Rb": rb,
        "Ra": ra,
        "Tmax": tmax,
        "Delta": delta,
        "Gamma": gamma,
        "ThetaL": math.atan(tmax) - tmax + delta,
        "ThetaU": tmax - math.atan(tmax) - delta + gamma,
    }


def gap_area_in_disc(
    teeth: int, samples: int = 2000, dp: float = DP, pa_deg: float = PA_DEG
) -> float:
    """Exact in-blank area of one tooth gap (in^2), by Green's theorem.

    Boundary: lower flank A1->B1, blank-rim arc B1->B2 at ``Ra`` (the
    beyond-rim part of the cut profile removes nothing), upper flank B2->A2
    reversed, base chord A2->A1 -- the same parametrisations as the live
    equation curves, so the expected volume validates the involute shape,
    not just that "some" cut happened.
    """
    f = gear_facts(teeth, dp, pa_deg)
    rb, ra = f["Rb"], f["Ra"]
    tmax, delta, gamma = f["Tmax"], f["Delta"], f["Gamma"]
    pts: list[tuple[float, float]] = []
    for i in range(samples + 1):  # lower flank (mirrored involute)
        t = tmax * i / samples
        ph = t - delta
        pts.append((
            rb * (math.cos(ph) + t * math.sin(ph)),
            rb * (t * math.cos(ph) - math.sin(ph)),
        ))
    for i in range(1, samples + 1):  # rim arc ThetaL -> ThetaU
        th = f["ThetaL"] + (f["ThetaU"] - f["ThetaL"]) * i / samples
        pts.append((ra * math.cos(th), ra * math.sin(th)))
    for i in range(1, samples + 1):  # upper flank, reversed
        t = tmax * (samples - i) / samples
        ph = t - delta + gamma
        pts.append((
            rb * (math.cos(ph) + t * math.sin(ph)),
            rb * (math.sin(ph) - t * math.cos(ph)),
        ))
    for i in range(1, samples):  # base chord A2 -> A1
        s = i / samples
        pts.append((
            rb * ((1 - s) * math.cos(gamma - delta) + s * math.cos(delta)),
            rb * ((1 - s) * math.sin(gamma - delta) + s * math.sin(delta)),
        ))
    area = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1], strict=False):
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


async def set_global_read(adapter: Any, name: str, expression: str) -> float:
    """Upsert a global variable and return the value SolidWorks evaluated."""
    from solidworks_mcp.adapters.base import SetGlobalVariableParameters

    res = await adapter.set_global_variable(
        SetGlobalVariableParameters(name=name, expression=expression)
    )
    data = check(f"global {name} = {expression}", res)
    value = data.get("value")
    if value is None:
        raise RuntimeError(f"global {name}: no evaluated value returned")
    return float(value)


async def set_global(adapter: Any, name: str, expression: str, expected: float) -> None:
    """Upsert a global variable and assert SolidWorks evaluated it correctly.

    The value round-trip is the live test of the equation parser (trig in
    DEGREES -- probed live, see ``build`` -- ``sqr`` = square root, literal-pi
    arithmetic); a mismatch means the expression dialect is wrong and every
    downstream curve would be silently bogus.
    """
    value = await set_global_read(adapter, name, expression)
    tol = max(1e-9, abs(expected) * 1e-6)
    if abs(value - expected) > tol:
        raise RuntimeError(
            f"global {name}: SolidWorks evaluated {value!r}, expected "
            f"{expected:.9g} -- equation-parser dialect mismatch"
        )


async def equation_curve(
    adapter: Any, label: str, x_expr: str, y_expr: str
) -> str:
    """Add a parametric equation curve over t in [0, 1]; return its entity ID."""
    from solidworks_mcp.adapters.base import CreateEquationCurveParameters

    res = await adapter.create_equation_driven_curve(
        CreateEquationCurveParameters(
            x_expression=x_expr,
            y_expression=y_expr,
            range_start="0",
            range_end="1",
        )
    )
    return check(f"curve {label}", res)


def pattern_count_dimension(adapter: Any, feature_name: str, expected: float) -> str:
    """Find the pattern's instance-count dimension name (``D?@<feature>``).

    The circular-pattern dimension layout (which of D1/D2 is the count vs
    the angle) is not documented stably across releases, so probe by value:
    the count dimension is the one reading ``expected`` (the seed count must
    differ from the 360-degree angle for this to be unambiguous).
    """
    from solidworks_mcp.adapters import sw_type_info

    model = adapter.currentModel
    try:
        sw_type_info.flag_methods(model, "IModelDoc2")
    except Exception:
        pass
    for dim in ("D1", "D2", "D3", "D4"):
        full = f"{dim}@{feature_name}"
        param = adapter._attempt(lambda f=full: model.Parameter(f), default=None)
        if param is None:
            continue
        try:
            value = float(_read_member(param, "Value"))
        except (TypeError, ValueError):
            continue
        print(f"  ..  {full} reads {value:g}")
        if abs(value - expected) < 1e-9:
            return full
    raise RuntimeError(
        f"no dimension of {feature_name} reads {expected:g} -- cannot link "
        "the instance count to ToothCount"
    )


def read_dimension(adapter: Any, full_name: str) -> float:
    """Read a dimension's value in the active configuration."""
    param = adapter._attempt(
        lambda: adapter.currentModel.Parameter(full_name), default=None
    )
    if param is None:
        raise RuntimeError(f"cannot read dimension {full_name}")
    return float(_read_member(param, "Value"))


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CircularPatternParameters,
        CreateConfigurationParameters,
        CreateEquationParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    findings: list[str] = []

    check("create_part", await adapter.create_part())

    # ------------------------------------------------------------------
    # Equation-manager globals. Probes first: live-verified on SW 2026, the
    # equation manager evaluates direct trig in DEGREES (cos(60) = 0.5);
    # the atn return unit is probed because inverse trig need not match.
    # sqr = square root (VBA-style).
    # ------------------------------------------------------------------
    facts = gear_facts(DEFAULT_TEETH)
    await set_global(adapter, "TrigProbe", "cos(60)", 0.5)
    await set_global(adapter, "SqrProbe", "sqr(2)", math.sqrt(2.0))
    atn_probe = await set_global_read(adapter, "AtnProbe", "atn(1)")
    if abs(atn_probe - 45.0) < 1e-6:
        atn_rad = f"atn(%s) * {PI_LIT} / 180"  # atn returns degrees
    elif abs(atn_probe - math.pi / 4.0) < 1e-6:
        atn_rad = "atn(%s)"  # atn returns radians
    else:
        raise RuntimeError(f"atn(1) evaluated to {atn_probe!r} -- unknown dialect")
    print(f"  ..  atn dialect: atn(1) = {atn_probe:g}")
    atn_tmax = atn_rad % '"Tmax"'

    await set_global(adapter, "ToothCount", str(DEFAULT_TEETH), DEFAULT_TEETH)
    await set_global(adapter, "DP", f"{DP:g}", DP)
    await set_global(adapter, "PA", f"{PA_DEG:g}", PA_DEG)
    await set_global(adapter, "PArad", f'"PA" * {PI_LIT} / 180', facts["PArad"])
    await set_global(
        adapter, "Rb", '"ToothCount" / "DP" * cos("PA") / 2', facts["Rb"]
    )
    await set_global(
        adapter, "Ra", '("ToothCount" + 2) / "DP" / 2', facts["Ra"]
    )
    await set_global(
        adapter, "Tmax", 'sqr("Ra" * "Ra" / ("Rb" * "Rb") - 1)', facts["Tmax"]
    )
    await set_global(
        adapter,
        "Delta",
        f'{PI_LIT} / (2 * "ToothCount") + tan("PA") - "PArad"',
        facts["Delta"],
    )
    await set_global(adapter, "Gamma", f'2 * {PI_LIT} / "ToothCount"', facts["Gamma"])
    await set_global(
        adapter, "ThetaL", f'{atn_tmax} - "Tmax" + "Delta"', facts["ThetaL"]
    )
    await set_global(
        adapter,
        "ThetaU",
        f'"Tmax" - {atn_tmax} - "Delta" + "Gamma"',
        facts["ThetaU"],
    )

    # ------------------------------------------------------------------
    # Blank: disc at tip radius Ra, revolved from a fully-dimensioned
    # rectangle whose radial dimension is then equation-linked to "Ra" --
    # the canonical configuration pattern. (A circle cannot be config-driven
    # through the fix+driven-dim recipe, and a disc from two half-circle
    # equation curves goes OVER-defined as soon as one curve is fixed --
    # both dead ends probed live.)
    # ------------------------------------------------------------------
    ra_default_mm = facts["Ra"] * 25.4
    check("create_sketch blank", await adapter.create_sketch("Top"))
    blank_lines = await add_line_chain(
        adapter,
        [
            (0.0, 0.0),
            (ra_default_mm, 0.0),
            (ra_default_mm, -FACE_WIDTH),
            (0.0, -FACE_WIDTH),
        ],
    )
    radial_line, side_line, _inner_line, axis_edge = blank_lines
    for ent, relation in (
        (radial_line, "horizontal"),
        (side_line, "vertical"),
        (_inner_line, "horizontal"),
        (axis_edge, "vertical"),
    ):
        check(f"blank {relation}", await adapter.add_sketch_constraint(ent, None, relation))
    # Radial dimension FIRST so it is D1@<sketch> (deterministic naming for
    # the equation link; verified by read-back below).
    check(
        "blank radial dim (D1)",
        await adapter.add_sketch_dimension(radial_line, None, "linear", ra_default_mm),
    )
    check(
        "blank width dim (D2)",
        await adapter.add_sketch_dimension(side_line, None, "linear", FACE_WIDTH),
    )
    # Revolve axis: a centerline strictly inside the axis edge's span (no
    # shared endpoints -> no merged vertices) drawn with inference off (no
    # collinear auto-relation) -- fixing it then cannot over-define the
    # dimensioned rectangle.
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "add_centerline axis",
        await adapter.add_centerline(0.0, -1.0, 0.0, -(FACE_WIDTH - 1.0)),
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "blank sketch", fix_entities=[centerline])
    check("exit_sketch blank", await adapter.exit_sketch())
    blank_sketch = feature_name_by_type(adapter, "ProfileFeature")
    check(
        "revolve blank",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )

    # The Top-plane sketch maps sketch -y onto global +Z: the blank must sit
    # at z = 0..FACE_WIDTH where the Front-plane gap cut (+Z, below) lands.
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"blank mass properties failed: {mass.error}")
    com_z = float(mass.data.center_of_mass[2])
    if abs(com_z - FACE_WIDTH / 2.0) > 0.1:
        raise RuntimeError(
            f"blank centre of mass z = {com_z:.2f}, expected {FACE_WIDTH / 2.0:.2f}"
            " -- Top-plane sketch axis mapping flipped; mirror the rectangle"
        )
    blank_volume = float(mass.data.volume)
    expected_blank = math.pi * ra_default_mm**2 * FACE_WIDTH
    if abs(blank_volume - expected_blank) > 0.02 * expected_blank:
        raise RuntimeError(
            f"blank volume {blank_volume:.1f} mm^3, expected {expected_blank:.1f}"
        )
    print(f"  OK  blank volume {blank_volume:.1f} mm^3 (com z {com_z:.2f})")

    # Equation-link the radial dimension to "Ra". Dimension equations
    # evaluate in DOCUMENT units; probe which unit Parameter().Value reports
    # so the per-config read-back asserts compare in the right unit.
    radial_dim = f"D1@{blank_sketch}"
    before = read_dimension(adapter, radial_dim)
    if abs(before - facts["Ra"]) < 1e-6 * facts["Ra"]:
        dim_unit = 1.0  # Value reads in inches
    elif abs(before - ra_default_mm) < 1e-6 * ra_default_mm:
        dim_unit = 25.4  # Value reads in millimetres
    else:
        raise RuntimeError(
            f"{radial_dim} reads {before!r}, matches neither {facts['Ra']:.6g} in "
            f"nor {ra_default_mm:.6g} mm"
        )
    print(f"  ..  {radial_dim} reads {before:g} (unit factor {dim_unit:g})")
    check(
        f"link {radial_dim} to Ra",
        await adapter.create_equation(
            CreateEquationParameters(equation=f'"{radial_dim}" = "Ra"')
        ),
    )

    # ------------------------------------------------------------------
    # One tooth gap, all six profile entities equation-driven (t in [0,1]).
    # Loop: A1 ->(lower flank)-> B1 ->(radial)-> arc -> (radial)-> B2
    # ->(upper flank, reversed)-> A2 ->(base chord)-> A1.
    # ------------------------------------------------------------------
    check("create_sketch gap", await adapter.create_sketch("Front"))
    u = '("Tmax" * t)'
    ph_low = f'({u} - "Delta")'
    ph_up = f'({u} - "Delta" + "Gamma")'
    gap_curves = [
        await equation_curve(
            adapter,
            "lower flank (tooth 0 upper, mirrored involute)",
            f'"Rb" * (cos{ph_low} + {u} * sin{ph_low})',
            f'"Rb" * ({u} * cos{ph_low} - sin{ph_low})',
        ),
        await equation_curve(
            adapter,
            "upper flank (tooth 1 lower involute)",
            f'"Rb" * (cos{ph_up} + {u} * sin{ph_up})',
            f'"Rb" * (sin{ph_up} - {u} * cos{ph_up})',
        ),
        await equation_curve(
            adapter,
            "base chord A2->A1",
            '"Rb" * ((1 - t) * cos("Gamma" - "Delta") + t * cos("Delta"))',
            '"Rb" * ((1 - t) * sin("Gamma" - "Delta") + t * sin("Delta"))',
        ),
        await equation_curve(
            adapter,
            "lower radial extension B1->clearance",
            f'("Ra" + t * ({R_CLEAR_IN:g} - "Ra")) * cos("ThetaL")',
            f'("Ra" + t * ({R_CLEAR_IN:g} - "Ra")) * sin("ThetaL")',
        ),
        await equation_curve(
            adapter,
            "outer clearance arc",
            f'{R_CLEAR_IN:g} * cos("ThetaL" + t * ("ThetaU" - "ThetaL"))',
            f'{R_CLEAR_IN:g} * sin("ThetaL" + t * ("ThetaU" - "ThetaL"))',
        ),
        await equation_curve(
            adapter,
            "upper radial extension clearance->B2",
            f'({R_CLEAR_IN:g} + t * ("Ra" - {R_CLEAR_IN:g})) * cos("ThetaU")',
            f'({R_CLEAR_IN:g} + t * ("Ra" - {R_CLEAR_IN:g})) * sin("ThetaU")',
        ),
    ]
    try:
        await ensure_fully_defined(adapter, "gap sketch", fix_entities=gap_curves)
    except RuntimeError as exc:
        findings.append(str(exc))
        print(f"  FINDING  {exc}")
    check("exit_sketch gap", await adapter.exit_sketch())
    # Single direction: both_directions splits the depth symmetrically about
    # the sketch plane (caught live: a 10 mm both-ways cut covered only
    # z 0..5 of the 7 mm blank, leaving an uncut full disc at z 5..7).
    gap_cut = await adapter.create_cut_extrude(
        ExtrusionParameters(depth=FACE_WIDTH + 1.0)
    )
    check("cut tooth gap", gap_cut)

    # ------------------------------------------------------------------
    # Pattern the gap about the gear axis; link the instance count to
    # ToothCount. Axis selection is by point (view-projected, flaky for
    # edge-on cylindrical faces), so walk candidates: a reference axis on
    # Z first, then OD-face points at several angles away from the seed
    # gap (which sits at ~0..1.4 degrees).
    # ------------------------------------------------------------------
    from solidworks_mcp.adapters.base import CreateAxisParameters

    check(
        "create_axis Z (Top x Right)",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=["Top Plane", "Right Plane"])
        ),
    )
    adapter._zoom_to_fit(adapter.currentModel)
    ra_default_mm = facts["Ra"] * 25.4
    candidates = [[0.0, 0.0, FACE_WIDTH / 2.0]]  # on the reference axis
    for angle_deg in (-45.0, -90.0, -135.0, 135.0, 45.0):
        a = math.radians(angle_deg)
        candidates.append(
            [ra_default_mm * math.cos(a), ra_default_mm * math.sin(a), FACE_WIDTH / 2.0]
        )
    pattern = None
    for point in candidates:
        # geometry_pattern: per-instance re-solve of the global-driven
        # equation-curve profile produces corrupt sliver cuts (live SW 2026
        # finding on the removable transgear); verbatim copies are exact.
        res = await adapter.circular_pattern_feature(
            CircularPatternParameters(
                axis_point=point,
                features=[gap_cut.data.name],
                count=DEFAULT_TEETH,
                geometry_pattern=True,
            )
        )
        if res.is_success:
            pattern = res
            print(f"  OK  circular pattern axis via point {point}")
            break
        print(f"  ..  axis candidate {point} failed: {res.error}")
    if pattern is None:
        raise RuntimeError("circular pattern: no axis candidate selectable")
    count_dim = pattern_count_dimension(adapter, pattern.data.name, DEFAULT_TEETH)
    check(
        f"link {count_dim} to ToothCount",
        await adapter.create_equation(
            CreateEquationParameters(equation=f'"{count_dim}" = "ToothCount"')
        ),
    )

    await apply_material(adapter, MATERIAL)

    # ------------------------------------------------------------------
    # Configurations + the regeneration experiment (plan risk #2): switch
    # through all configs asserting per-config instance count, volume bounds
    # and monotonic growth, then return to the first config and require the
    # volume to reproduce (determinism).
    # ------------------------------------------------------------------
    for name, teeth in CONFIGS:
        check(
            f"create_configuration {name}",
            await adapter.create_configuration(
                CreateConfigurationParameters(
                    name=name, comment=f"{teeth}-tooth cone gear"
                )
            ),
        )
    from solidworks_mcp.adapters.base import SetGlobalVariableParameters

    for name, teeth in CONFIGS:
        check(
            f"ToothCount = {teeth} in {name}",
            await adapter.set_global_variable(
                SetGlobalVariableParameters(
                    name="ToothCount", expression=str(teeth), configuration=name
                )
            ),
        )

    png_dir = OUT_PNG / PART_NAME
    png_dir.mkdir(parents=True, exist_ok=True)
    artefacts: dict[str, str] = {}
    volumes: dict[str, float] = {}
    for name, teeth in CONFIGS:
        check(f"activate {name}", await adapter.set_active_configuration(name))

        count = read_dimension(adapter, count_dim)
        if abs(count - teeth) > 1e-9:
            raise RuntimeError(
                f"{name}: pattern instance count reads {count:g}, expected {teeth}"
            )
        print(f"  OK  {name}: pattern count = {count:g}")

        cfg = gear_facts(teeth)
        ra_mm = cfg["Ra"] * 25.4
        mass = await adapter.get_mass_properties()
        if not mass.is_success:
            raise RuntimeError(f"{name}: get_mass_properties failed: {mass.error}")
        volume = float(mass.data.volume)
        blank_mm3 = math.pi * ra_mm**2 * FACE_WIDTH
        expected = blank_mm3 - teeth * gap_area_in_disc(teeth) * 25.4**2 * FACE_WIDTH
        if abs(volume - expected) > 0.01 * expected:
            raise RuntimeError(
                f"{name}: volume {volume:.1f} mm^3, analytic expectation "
                f"{expected:.1f} (blank {blank_mm3:.1f}) -- regeneration "
                "produced wrong geometry"
            )
        volumes[name] = volume
        print(
            f"  OK  {name}: volume {volume:.1f} mm^3 "
            f"(analytic {expected:.1f}, blank {blank_mm3:.1f})"
        )

        # OD check via the equation-driven radial dimension (selection-free;
        # the measure tool's point selection proved unreliable on the
        # patterned gear -- it kept grabbing gap-wall faces).
        radial = read_dimension(adapter, radial_dim)
        if abs(radial - cfg["Ra"] * dim_unit) > 1e-4 * cfg["Ra"] * dim_unit:
            raise RuntimeError(
                f"{name}: {radial_dim} reads {radial:g}, expected "
                f"{cfg['Ra'] * dim_unit:g} -- dimension equation did not "
                "regenerate"
            )
        print(f"  OK  {name}: blank radius dim = {radial:g}")

        img = (png_dir / f"{PART_NAME}_{name}_isometric.png").resolve()
        check(
            f"export_image {name}",
            await adapter.export_image(
                {
                    "file_path": str(img),
                    "format_type": "png",
                    "width": 1600,
                    "height": 1000,
                    "view_orientation": "isometric",
                }
            ),
        )
        artefacts[f"iso_{name}"] = str(img)

    ordered = [volumes[name] for name, _ in CONFIGS]
    if not all(a < b for a, b in zip(ordered, ordered[1:], strict=False)):
        raise RuntimeError(f"volumes not monotonically increasing: {volumes}")
    print(f"  OK  volumes monotonic: {ordered}")

    # Determinism: revisit the first configuration after the full cycle.
    first_name, _ = CONFIGS[0]
    check(f"re-activate {first_name}", await adapter.set_active_configuration(first_name))
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"re-check {first_name}: {mass.error}")
    revisit = float(mass.data.volume)
    if abs(revisit - volumes[first_name]) > abs(volumes[first_name]) * 1e-6:
        raise RuntimeError(
            f"{first_name} volume drifted on revisit: {revisit} vs "
            f"{volumes[first_name]} -- regeneration is not deterministic"
        )
    print(f"  OK  {first_name} volume reproduced on revisit: {revisit:.1f} mm^3")

    check("activate T120 for saved views", await adapter.set_active_configuration("T120"))
    await report_mass_properties(adapter)
    artefacts.update(await save_part_and_images(adapter, PART_NAME))

    if findings:
        summary = "; ".join(findings)
        raise RuntimeError(f"prototype completed with findings: {summary}")
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
