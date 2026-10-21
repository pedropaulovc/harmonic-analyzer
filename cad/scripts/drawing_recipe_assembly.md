# Recipe: assembly drawings

## Legacy three-view sheets

The shared `_assembly_drawing.py` recipe produces one ASME B sheet with
`*Front`, `*Right`, and `*Isometric` views. These overview sheets are not complete
manufacturing assembly packages. New or recreated packages must follow
[`drawing-guidelines.md`](../docs/drawing-guidelines.md), including
the assembly information needed to build and inspect the mechanism.

`_drawing_common.finalize_drawing` enforces the project-wide isometric contract:
Shaded With Edges, precision geometry (draft/faceted quality off), and
high-quality cosmetic threads.

An entry point using the legacy recipe supplies its registry identity, output
paths, sheet scale, and view centers:

```python
SPEC = DRAWINGS_BY_NAME["<stem>_assembly"]
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)

SHEET_SCALE = (1.0, 4.0)
FRONT_CENTER = (0.070, 0.150)
RIGHT_CENTER = (0.150, 0.150)
ISO_CENTER = (0.225, 0.140)


async def build(adapter):
    return await build_simple_three_view_drawing(
        adapter,
        source=SOURCE,
        layout=SPEC.layout,
        outputs=OUTPUTS,
        sheet_scale=SHEET_SCALE,
        front_center=FRONT_CENTER,
        right_center=RIGHT_CENTER,
        iso_center=ISO_CENTER,
        pdf_title="<Title> Assembly Drawing",
    )
```

The builder explicitly pins every view to `SHEET_SCALE`. SolidWorks can
otherwise auto-scale a newly inserted view according to the seat preference,
which makes the saved placement nondeterministic. Explicit scale is placement
determinism, not a visual-style override.

Registry rows, task names, CLI arguments, and output stems remain unchanged.
The normal build command is:

```powershell
uv run python -m doit drawing:<stem>_assembly
```

Offline coverage lives in `test_assembly_drawing_batch_contract.py` plus one
small per-assembly contract file. The batch contract owns the shared invariants;
the per-assembly files pin each registry row, output mapping, scale, and centers.

## Frame package

`draw_fr_frame_assembly.py` uses three ASME B sheets: landscape working views,
portrait exploded view with native BOM and balloons, and landscape assembly
instructions. The registry includes both orientation templates as dependencies.
Finalization checks each native sheet and each exported PDF page against its
declared layout.

The frame builder owns the persisted `FRAME_EXPLODED` presentation, authors the
same steps in `Default Simplified` as `FRAME_EXPLODED Simplified`, and saves the
assembly collapsed. A drawing view shows the explode of the configuration it
references, and the 1:7 exploded view references `Default Simplified` (every
assembly view at 1:2 or smaller that inks edges does; sheet 3's isometric is
the full-detail view). The drawing therefore sets a view's configuration first
and its exploded state second, and consumes the presentation without authoring
source features. Explode validation checks component movement in world
coordinates; a view's exploded flag alone does not establish correct separation.
The drawing lifecycle also checks that the source assembly remains unchanged.

Use `uv run python -m doit drawing:fr_frame_assembly` to regenerate the package.
Inspect every page and complete the blind machinist review before release.

## Magnifier package

`draw_mg_magnifier_assembly.py` keeps its four sheets and all 19 BOM families.
The BOM's final five columns are item, full canonical Number, description,
vendor SKU and quantity. Their widths are 12/48/82/32/12 mm respectively;
the Number column has its own room for `MHA-MG-VN-50` through `MHA-MG-VN-56`.
The native table font, complete cell contents, 6 mm requested data-row height
and three-line heading budget are unchanged.

The wheel and lever exploded views use native `AutoBalloon5` EDGE/Square
placement against their existing linked BOM: eleven wheel families and seven
lever families. The finished wire keeps its proven ring anchor, completing
nineteen families without custom item text or quantity overrides. Exact native
item coverage and full shown-component edge ownership are mandatory; native
positions are not re-spread. Final rebuild checks reread the attachments and
rendered circles, including the lever caption's actual note extent.

The native EDGE call borrows the document's Normal visible-edge weight slot,
checks its readback, and restores and rereads the original slot in `finally`
before rebuilding or exporting. It never changes physical line widths or the
template. This reuses the MG-specific positive control from #1776/#1783, not a
general fix for every #1667 omission. The shared balloon helper is a drawing
recipe input, so this change rekeys drawing consumers without changing model
geometry; other assemblies retain their manual path and the default face mode.

The naming migration lengthened those seven purchased Numbers from ten to
twelve characters but left the Number column at 32 mm. The native failure at
`5c5d3e3b3672` measured a 153.3 mm table, from Y109.4 to Y262.7, against a
132 mm plan. That aggregate measurement does not identify the wrapped rows.
The wider Number column addresses the newly longer input without taking room
from descriptions or SKUs. It makes the table 186 mm wide at X229.1..415.1,
still 17.1 mm right of the unchanged wheel-view field. The BOM-reference field
follows the table's left edge and widens by 16 mm; its scale-fitting ladder is
unchanged, but may select a larger reference-view scale. Native readback and
sheet inspection must establish the resulting scale and fit.

Native acceptance still requires the BOM bottom at or above Y123.2 mm:
the reference field's unchanged top is Y120.7 and requires 2.5 mm of air.
The planned bottom remains Y130.7. A clearance failure attempts to log persisted
native column widths and row heights, plus complete cells and font heights for
grown rows; a diagnostic failure never replaces the measured-overrun error.
Inspect the regenerated four-page package for all 19
rows, full unbroken Numbers, readable descriptions/SKUs/quantities, unchanged
reference-view handling and unobstructed balloons; the offline field-budget
checks alone do not prove native text fit.
