"""The release's HARDWARE.md: the Master Hardware Schedule (#2886).

``cad/config/hardware.yaml`` gives every purchased part its COTS tier and
reason, and each tier-1 (standard) part its generic designation, standard and
the pure per-SKU sources of its seat envelope. Numbers, titles, SKUs and
quantities come from the part registry; envelope values from the
``_mcmaster_*`` / ``*_spec`` providers the part recipes already consume;
assembly membership from the build graph. cut_release stages the document
beside ASSEMBLY.md; run this module to print it. No SolidWorks.
"""

from __future__ import annotations

import importlib
import math
import re
from functools import cache
from pathlib import Path
from typing import Any

import yaml

import _buildgraph as bg
import _config

DOCUMENT_NAME = "HARDWARE.md"
TIERS: dict[str, dict[str, Any]] = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / "config" / "hardware.yaml").read_text(
        encoding="utf-8"
    )
)
SCHEDULE = {stem: row for stem, row in TIERS.items() if row["tier"] == 1}
_PATH = re.compile(r"(\w+)|\[(\d+)\]")


def envelope_mm(source: str) -> float:
    """One ``"<module> [factor*]<path>"`` envelope value, in millimetres."""
    module, expr = source.split(" ")
    provider = importlib.import_module(module)
    factor, _, path = expr.rpartition("*")
    if path.startswith("Supplier"):
        (value,) = (
            abs(v)
            for name, v, *_ in provider.SUPPLIER_REFERENCE_DIMENSIONS
            if name == path
        )
    else:
        value = provider
        for name, index in _PATH.findall(path):
            value = getattr(value, name) if name else value[int(index)]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{source} is not a positive length: {value!r}")
    return float(value) * float(factor or 1)


def _envelope_text(row: dict[str, Any]) -> str:
    if not row.get("envelope"):
        return f"per {row['standard']}"
    return " x ".join(
        f"{label} {math.ceil(envelope_mm(source) / 25.4 * 1000 - 1e-6) / 1000:.3f}"
        for label, source in row["envelope"].items()
    )


@cache
def used_in() -> dict[str, tuple[str, ...]]:
    """Dashed part stem -> dashed assemblies whose builder references it. A
    machine part lists machine assemblies only; tooling lists its fixture."""
    found: dict[str, list[str]] = {}
    for assembly in bg.ASSEMBLY_ORDER:
        for stem in bg.references_of(assembly):
            if bg.is_shop_fixture(assembly) and not bg.is_shop_fixture(stem):
                continue
            found.setdefault(stem.replace("_", "-"), []).append(
                assembly.replace("_", "-")
            )
    return {stem: tuple(assemblies) for stem, assemblies in found.items()}


def purchased_parts() -> frozenset[str]:
    """Registry stems a tier must cover: every ``-vn-`` part and every
    fabricated part naming a bought supplier SKU, outside the retiring oblique
    trammel jig. ``TIERS`` may name more (a reworked blank the registry
    describes only in prose, such as MHA-PD-09)."""
    return frozenset(
        stem
        for stem, row in _config.parts().items()
        if "-tl-vn-oblique-" not in stem
        and ("-vn-" in stem or row.get("supplier_skus"))
    )


def _cells(*cells: object) -> str:
    return "| " + " | ".join(str(cell).replace("|", "\\|") for cell in cells) + " |"


def markdown() -> str:
    lines = [
        "# Master Hardware Schedule",
        "",
        "Standard hardware the machine uses as supplied (ASME Y14.24 tier 1). "
        "Buy to the generic designation; the example SKU is the part the CAD "
        "models. Fits (thread, pin diameter) come from the designation and its "
        "standard. The seat envelope bounds the space the part may occupy "
        "(heads and nuts across corners): the catalogue maximum where its "
        "dimension provider records one, otherwise the modelled catalogue size "
        "the assembly clearance checks use, rounded up to 0.001 in; a substitute "
        "must not exceed it. Inches.",
        "",
        "| Number | Part | Designation | Standard | Seat envelope (in) | Qty | Used in | Example SKU |",
        "|---|---|---|---|---|---:|---|---|",
    ]
    for stem, row in sorted(
        SCHEDULE.items(), key=lambda kv: _config.parts(kv[0])["number"]
    ):
        part = _config.parts(stem)
        skus = ", ".join(str(sku) for sku in part.get("supplier_skus", ()))
        lines.append(
            _cells(
                part["number"],
                part.get("title") or part.get("stock_name"),
                row["designation"],
                row["standard"],
                _envelope_text(row),
                part["quantity"],
                ", ".join(used_in().get(stem, ())) or "—",
                f"{part.get('supplier', 'McMaster-Carr')} {skus}",
            )
        )
    lines += [
        "",
        "Qty is the registry total. Used in lists the machine assemblies that "
        "use the part; a shop-tooling (`TL`) part lists its fixture instead.",
        "",
        "Non-standard purchased items (tier 2) and shop-altered purchased items "
        "(tier 3) have their own drawing sheets in `slddrw/`:",
        "",
        "| Part | Tier | Why |",
        "|---|---:|---|",
    ]
    for stem, row in sorted(TIERS.items(), key=lambda kv: (kv[1]["tier"], kv[0])):
        if row["tier"] != 1:
            number = _config.parts(stem)["number"]
            lines.append(_cells(f"{number} `{stem}`", row["tier"], row["why"]))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(markdown(), end="")
