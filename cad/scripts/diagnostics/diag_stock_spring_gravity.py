"""Opt-in native stock-spring gravity capacity diagnostic.

From the repository root, after generating current parts with doit, run::

    uv run python cad/scripts/diagnostics/diag_stock_spring_gravity.py

Reads the twenty existing cad/out/sldprt parts; never builds missing artifacts.
The caller must make those artifacts current through doit. This uses the standard
run_build session (including its initial document cleanup); save user work first.
COM is serialized by dodo._com_seat, and each measured document is closed without
saving. Results are written to cad/out/reports/stock-spring-gravity.json.

Scope: level lever, configured catalog curves, clamp at/inside the built 165 mm
radius. All pen weight is reflected using max(CAD ratio, physical pitch ratio),
with no helpful guide friction. Flexible spring/wire weight and wheel imbalance
are bounded symmetrically. The fixed gooseneck is measured but contributes no
moving-lever torque. This is not a full native-build gate, writing-friction or
dynamic-load proof. Counter initial-tension tolerance is unspecified: measured
force-curve acceptance remains necessary; no tolerance bounds are invented.
The original current-part experiment yielded 23.4944..48.87466 N against catalog
17.08117..69.30329 N, with pen mass 0.179161 kg; these are reference observations,
not substituted inputs or assertions that future geometry must retain them.
"""

from pathlib import Path
import json
import math
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import dodo
from _common import _early_bound, check, run_build
import _telemetry
import build_magnifier_assembly as m
import counter_spring_spec
import error_budget as eb
import pen_wire_geom
import spring_mount_geom as s

ROOT = Path(__file__).resolve().parents[3]

STEMS = (
    "channel-spring-installed",
    "counter-spring",
    "spring-hook",
    "boss-hook",
    "summing-lever",
    "gooseneck",
    "magnifying-lever",
    "magnifying-bracket",
    "magnifying-clamp",
    "magnifying-vertical-rod",
    "output-fixture",
    "thumb-screw",
    "lever-wire",
    "magnifying-wheel",
    "pen-rod",
    "pen-v-block",
    "pen-marker",
    "pen-frame",
    "pen-set-screw",
    "pen-wire",
)
PEN_STEMS = (
    "pen-rod",
    "pen-v-block",
    "pen-marker",
    "pen-frame",
    "pen-set-screw",
    "pen-wire",
)
REPORT = ROOT / "cad/out/reports/stock-spring-gravity.json"


async def build(adapter):
    parts = {}
    for stem in STEMS:
        path = ROOT / "cad/out/sldprt" / f"{stem}.SLDPRT"
        with _telemetry.span("gravity.native_mass", part=stem):
            check(f"open built part {stem}", await adapter.open_model(str(path)))
            model = _early_bound(adapter.currentModel, "IModelDoc2")
            try:
                if model is None:
                    raise RuntimeError(f"opened part has no native document: {stem}")
                model.ClearSelection2(True)
                ext = _early_bound(model.Extension, "IModelDocExtension")
                mp = _early_bound(ext.CreateMassProperty2(), "IMassProperty2")
                if mp is None:
                    raise RuntimeError(f"CreateMassProperty2 failed: {stem}")
                mp.UseSystemUnits = True
                mp.IncludeHiddenBodiesOrComponents = True
                if not mp.Recalculate():
                    raise RuntimeError(f"native mass recalculation failed: {stem}")
                options = _early_bound(
                    mp.GetOverrideOptions(), "IMassPropertyOverrideOptions"
                )
                if options is None:
                    raise RuntimeError(
                        f"native mass override options unavailable: {stem}"
                    )
                row = {
                    "path": str(path),
                    "mass_kg": float(mp.Mass),
                    "density_kg_m3": float(mp.Density),
                    "volume_mm3": float(mp.Volume) * 1e9,
                    "area_mm2": float(mp.SurfaceArea) * 1e6,
                    "com_mm": [float(v) * 1000 for v in mp.CenterOfMass],
                    "mass_override": bool(options.OverrideMass),
                    "com_override": bool(options.OverrideCenterOfMass),
                }
                if row["mass_override"] or row["com_override"]:
                    raise RuntimeError(f"native mass/COM override rejected: {stem}")
                if (
                    not math.isfinite(row["mass_kg"])
                    or row["mass_kg"] <= 0
                    or not math.isfinite(row["density_kg_m3"])
                    or row["density_kg_m3"] <= 0
                    or len(row["com_mm"]) != 3
                    or not all(math.isfinite(v) for v in row["com_mm"])
                ):
                    raise RuntimeError(
                        f"invalid native mass/density/COM: {stem}: {row}"
                    )
                parts[stem] = row
                _telemetry.info(
                    "read native gravity mass", part=stem, mass_kg=row["mass_kg"]
                )
            finally:
                if model is not None:
                    adapter.swApp.CloseDoc(str(model.GetTitle()))
                adapter.currentModel = None

    with _telemetry.span("gravity.counter_force_interval"):
        rows = []

        def weight(stem, origin, rotation, count=1):
            p = parts[stem]
            com = [
                origin[j] + sum(p["com_mm"][i] * rotation[i][j] for i in range(3))
                for j in range(3)
            ]
            torque = -count * p["mass_kg"] * 9.80665 * (com[0] - s.KNIFE[0])
            rows.append(
                {
                    "part": stem,
                    "count": count,
                    "mass_kg": count * p["mass_kg"],
                    "origin_mm": origin,
                    "rotation_rows": rotation,
                    "world_com_mm": com,
                    "gravity_torque_n_mm": torque,
                }
            )

        weight("summing-lever", (s.KNIFE[0], s.KNIFE[1], 0), m.IDENTITY)
        weight("spring-hook", (*s.CHANNEL_ANCHOR_XY, 0), m.IDENTITY, 20)
        weight("boss-hook", (*s.COUNTER_ANCHOR_XY, 0), m.IDENTITY)
        weight(
            "magnifying-lever", (m.LEVER_X0, m.LEVER_ROD_Y, m.LEVER_ROD_Z), m.ROT_Y_180
        )
        weight(
            "magnifying-bracket",
            (m.BRACKET_X, m.LEVER_ROD_Y, m.LEVER_ROD_Z),
            m.IDENTITY,
        )
        weight("magnifying-clamp", m.CLAMP_POS, m.ROT_Y_POS90)
        rotation = m.compose_rows(m.rot_z_rows(-90), m.ROT_Y_180)
        weight(
            "thumb-screw",
            (m.CLAMP_X, m.THUMB_SCREW_OUTER_FACE_Y, m.LEVER_ROD_Z),
            rotation,
        )
        weight("magnifying-vertical-rod", (m.CLAMP_X, m.VROD_TOP_Y, m.VROD_Z), rotation)
        weight("output-fixture", (m.CLAMP_X, m.FIXTURE_Y0, m.VROD_Z), m.IDENTITY)
        positive = sum(max(0, row["gravity_torque_n_mm"]) for row in rows)
        negative = sum(min(0, row["gravity_torque_n_mm"]) for row in rows)
        hook = m.HUB_WIRE_START
        hook_radius = math.hypot(hook[0] - s.KNIFE[0], hook[1] - s.KNIFE_CONTACT_Y)
        physical_ratio = (pen_wire_geom.RIM_DIA + pen_wire_geom.WIRE_DIA) / (
            m.HUB_DIA + m.HUB_WIRE_DIA
        )
        cad_ratio = eb.nominal().wheel_ratio
        ratio = max(physical_ratio, cad_ratio)
        pen_mass = sum(parts[stem]["mass_kg"] for stem in PEN_STEMS)
        pen_torque_bound = pen_mass * 9.80665 * ratio * hook_radius
        wheel = parts["magnifying-wheel"]
        wheel_ecc = math.hypot(wheel["com_mm"][0], wheel["com_mm"][2])
        wheel_bound = (
            wheel["mass_kg"]
            * 9.80665
            * wheel_ecc
            * hook_radius
            / ((m.HUB_DIA + m.HUB_WIRE_DIA) / 2)
        )
        channel_radius = math.hypot(
            s.CHANNEL_ANCHOR_XY[0] - s.KNIFE[0],
            s.CHANNEL_ANCHOR_XY[1] - s.KNIFE_CONTACT_Y,
        )
        counter_radius = math.hypot(
            s.COUNTER_ANCHOR_XY[0] - s.KNIFE[0],
            s.COUNTER_ANCHOR_XY[1] - s.KNIFE_CONTACT_Y,
        )
        flexible_bound = 9.80665 * (
            20 * parts["channel-spring-installed"]["mass_kg"] * channel_radius
            + parts["counter-spring"]["mass_kg"] * counter_radius
            + parts["lever-wire"]["mass_kg"] * hook_radius
        )
        arm = -s.COUNTER_REFERENCE_POSE.moment_arm_mm
        reference = s.counter_force_n(s.COUNTER_REFERENCE_POSE.length_mm)
        low = (
            reference
            + (negative - pen_torque_bound - wheel_bound - flexible_bound) / arm
        )
        high = reference + (positive + wheel_bound + flexible_bound) / arm
        catalog = [
            counter_spring_spec.INITIAL_TENSION_N,
            counter_spring_spec.MAXIMUM_LOAD_N,
        ]
        within_catalog = catalog[0] <= low <= high <= catalog[1]
        report = {
            "scope": "Level lever; configured catalog curves; clamp at/inside built 165 mm radius. Full pen-weight reflection; no helpful guide friction. Flexible weight and wheel imbalance bounded symmetrically. Not a writing-friction/dynamic-load proof or substitute for full native build.",
            "limitation": "Counter initial-tension tolerance unspecified; measured force-curve acceptance still needed. No tolerance bounds assumed.",
            "native_parts": parts,
            "rigid_parts": rows,
            "fixed_parts_excluded_from_moving_torque": ["gooseneck"],
            "pen_parts_one_each": PEN_STEMS,
            "flexible_part_counts": {
                "channel-spring-installed": 20,
                "counter-spring": 1,
                "lever-wire": 1,
            },
            "pen_mass_kg": pen_mass,
            "pen_gravity_torque_bound_n_mm": pen_torque_bound,
            "wheel_imbalance_bound_n_mm": wheel_bound,
            "flexible_weight_bound_n_mm": flexible_bound,
            "cad_wheel_ratio": cad_ratio,
            "physical_pitch_ratio": physical_ratio,
            "wheel_ratio_bound": ratio,
            "hook_radius_mm": hook_radius,
            "channel_radius_mm": channel_radius,
            "counter_radius_mm": counter_radius,
            "counter_moment_arm_mm": arm,
            "counter_reference_force_n": reference,
            "counter_force_interval_n": [low, high],
            "catalog_interval_n": catalog,
            "within_catalog_interval": within_catalog,
        }
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        _telemetry.info(
            "native gravity capacity report",
            report=str(REPORT),
            low_n=low,
            high_n=high,
            pen_mass_kg=pen_mass,
        )
        _telemetry.info(report["limitation"])
        if not within_catalog:
            raise RuntimeError(
                f"native gravity bound [{low}, {high}] N exceeds catalog adjustment "
                f"range {catalog} N; see {REPORT}"
            )
    return {"report": str(REPORT)}


def main():
    with dodo._com_seat("stock-spring-gravity"):
        missing = [
            str(ROOT / "cad/out/sldprt" / f"{stem}.SLDPRT")
            for stem in STEMS
            if not (ROOT / "cad/out/sldprt" / f"{stem}.SLDPRT").is_file()
        ]
        if missing:
            _telemetry.error(
                "missing built parts; generate current artifacts with doit first",
                missing_parts=missing,
            )
            return 1
        return run_build(build)


if __name__ == "__main__":
    raise SystemExit(main())
