r"""Build the minimal crank-versus-chain inspection assembly.

This fixture reuses the already-built paper-drive subassembly for its T12
sprocket and roller chain, then inserts only the photographed crank hardware.
It avoids rebuilding the several-hundred-component drive-train while retaining
the exact top-level transforms and the decisive cross-subassembly interference
check.

Run with SolidWorks open::

    uv run python cad\scripts\diagnostics\build_crank_chain_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _assembly import (  # noqa: E402
    assert_component_placed,
    assert_components_fully_defined,
    check_no_interference,
    place_component,
    save_assembly_and_images,
)
from _common import OUT_SLDASM, check, run_build  # noqa: E402
from _transforms import IDENTITY, ROT_Y_180, compose_rows  # noqa: E402
from build_crank_arm import ARM_C2C  # noqa: E402
from build_drive_train_assembly import (  # noqa: E402
    CRANK_ARM_ORIGIN_Z,
    CRANK_ARM_Z0,
    CRANK_PIN_X0,
    CRANK_PIN_Z,
    CRANKSHAFT_Z0,
    ROT_X_POS90,
    ROT_Y_POS90,
    X_CRANK,
    Y_CRANK,
    rot_z_rows,
)
from crank_pin_spec import RING_HOLE_X  # noqa: E402
from export_models import OUT_GLTF, _save_as  # noqa: E402

ASM_NAME = "crank-chain-check"


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        ComponentRefParameters,
        InsertComponentParameters,
    )

    check("create_assembly", await adapter.create_assembly())

    paper_drive_path = (OUT_SLDASM / "paper-drive.SLDASM").resolve()
    if not paper_drive_path.exists():
        raise RuntimeError(f"missing {paper_drive_path}; build paper-drive first")
    data = check(
        "insert cached paper-drive.SLDASM",
        await adapter.insert_component(
            InsertComponentParameters(
                file_path=str(paper_drive_path),
                position=[0.0, 0.0, 0.0],
                rotation=[0.0, 0.0, 0.0],
            )
        ),
    )
    paper_drive = data["name"]
    if not data.get("fixed"):
        check(
            "fix paper-drive",
            await adapter.fix_component(ComponentRefParameters(name=paper_drive)),
        )
    assert_component_placed(adapter, paper_drive, [0.0, 0.0, 0.0], IDENTITY)

    await place_component(
        adapter,
        "crankshaft",
        [X_CRANK, Y_CRANK, CRANKSHAFT_Z0],
        [90.0, 0.0, 0.0],
        ROT_X_POS90,
        label="crankshaft",
    )
    await place_component(
        adapter,
        "crank-arm",
        [X_CRANK, Y_CRANK, CRANK_ARM_ORIGIN_Z],
        [180.0, 0.0, -90.0],
        compose_rows(rot_z_rows(-90.0), ROT_Y_180),
        label="crank arm with bridge hub",
    )
    await place_component(
        adapter,
        "crank-handle",
        [X_CRANK, Y_CRANK - ARM_C2C, CRANK_ARM_Z0],
        [0.0, 90.0, 0.0],
        ROT_Y_POS90,
        label="crank handle",
    )
    await place_component(
        adapter,
        "crank-pin",
        [CRANK_PIN_X0, Y_CRANK, CRANK_PIN_Z],
        [0.0, 0.0, 0.0],
        IDENTITY,
        label="tapered crank pin",
    )
    await place_component(
        adapter,
        "crank-pin-ring",
        [CRANK_PIN_X0 + RING_HOLE_X, Y_CRANK, CRANK_PIN_Z],
        [0.0, 0.0, 0.0],
        IDENTITY,
        label="brass pull ring",
    )

    assert_components_fully_defined(adapter)
    check_no_interference(adapter)
    artefacts = await save_assembly_and_images(adapter, ASM_NAME)

    check("reopen crank-chain check for GLB", await adapter.open_model(artefacts["assembly"]))
    OUT_GLTF.mkdir(parents=True, exist_ok=True)
    glb = OUT_GLTF / f"{ASM_NAME}.glb"
    _save_as(adapter.currentModel, glb)
    artefacts["glb"] = str(glb)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
