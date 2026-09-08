# Drawing-context body identity

The first complete-recipe attempt at `509e70460507f33f860ea6727a6fea8c4410ad50`
stopped before datum insertion on both drawings. Its new body guard compared a
drawing-context edge body directly to the source part's solid body. Both drawing
tasks failed; neither source file changed. This is not a passing drawing build.

The [read-only control](probes/production-509e7046/body-correspondence.json) on
the retained rack drawing established the required correspondence:

| Native comparison | `IsSame` |
| --- | --- |
| Source body with itself | 1 |
| Drawing-context edge body with itself | 1 |
| Drawing-context edge body with source body | 0 |
| `source.Extension.GetCorrespondingEntity2(edge).GetBody()` with source body | 1 |
| Mapped source edge with original drawing edge | 0 |
| `view.GetCorrespondingEntity(mapped_source_edge)` with original drawing edge | 1 |
| Round-trip edge body with original drawing-context body | 1 |

The mapped source edge retained the intended 2.5 mm bore radius and origin-Z
axis. Its source hash stayed
`aa70ef6a9907311ccc78cf3bd5de4252e887a78aeef10a99652037be1161ef90`;
the inventory and dirty flags also stayed unchanged during the read-only probe.

The correction must require that documented drawing-to-model-to-drawing round
trip. Model-body and cylinder checks belong on the mapped source edge;
selection/attachment equality belongs on the original drawing-context edge.
Missing or unequal mappings remain failures. A radius match cannot substitute
for model-body identity.

After recording the control, VM2 discarded only its witnessed unsaved
`Draw122 - Sheet1` and the associated unsaved callout change. The native source
bytes remained unchanged and the seat returned empty. The failure and control
remain preserved here; the document is a call-shape diagnosis, not a waiver of
the body-identity requirement.
