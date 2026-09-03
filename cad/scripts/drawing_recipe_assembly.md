# Recipe: assembly drawing packages

Each registered assembly produces a three-sheet ASME B package:

1. `ASSEMBLED VIEWS` shows enlarged Front and Right working-position views.
2. `EXPLODED AND BOM` shows a native exploded isometric, an associative BOM,
   balloons, and two small reference projections used for balloon coverage.
3. `ASSEMBLY PROCEDURE` shows the assembled isometric beside ordered steps,
   hardware and consumables, and measurable orientation and acceptance checks.

The source assembly must contain a persisted exploded view. Assembly saves
create one with SolidWorks `AutoExplode` when the active configuration has
none, then collapse it before the final solve and save. The drawing fails if
the exploded state cannot be displayed. It never substitutes a collapsed view
under an exploded-view label.

`_assembly_drawing.py` owns sheet creation, view display, active-configuration
pinning, BOM insertion and validation, balloon coverage, note placement, sheet
markers, and export. An entry point supplies its registry identity, layout
scales and centers, and assembly-specific procedure text:

```python
SPEC = DRAWINGS_BY_NAME["<stem>_assembly"]
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)

SHEET_SCALE = (1.0, 4.0)
REFERENCE_SCALE = (1.0, 8.0)
FRONT_CENTER = (0.080, 0.145)
RIGHT_CENTER = (0.280, 0.145)
ISO_CENTER = (0.280, 0.145)

ASSEMBLY_STEPS = ("...", "...", "...", "...")
CRITICAL_CHECKS = ("...", "...")
HARDWARE_NOTES = ("...",)


async def build(adapter):
    return await build_assembly_package(
        adapter,
        source=SOURCE,
        outputs=OUTPUTS,
        sheet_scale=SHEET_SCALE,
        reference_scale=REFERENCE_SCALE,
        front_center=FRONT_CENTER,
        right_center=RIGHT_CENTER,
        iso_center=ISO_CENTER,
        pdf_title="<Title> Assembly Drawing",
        assembly_steps=ASSEMBLY_STEPS,
        critical_checks=CRITICAL_CHECKS,
        hardware_notes=HARDWARE_NOTES,
    )
```

The BOM reads unsuppressed top-level components from the active assembly
configuration. Native quantities stay authoritative. Component `Number` and
`Title` properties supply the released part number and description; filenames
are only the fallback description.

Registry rows, task names, CLI arguments, and output stems remain unchanged.
Build one package with:

```powershell
uv run python -m doit drawing:<stem>_assembly
```

`test_assembly_drawing_batch_contract.py` owns the shared package invariants.
The per-assembly tests pin the procedure content and layout forwarded by each
entry point.
