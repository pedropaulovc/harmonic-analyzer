"""Existing VIEW-origin call sites, not new production attachment selectors."""

from dataclasses import dataclass
from enum import StrEnum


class ViewResolver(StrEnum):
    BORE = "bore"
    TOOTH_TIP = "tooth_tip"
    PIVOT_FACE = "pivot_face"
    TIP_FACE = "tip_face"
    OUTER_END = "outer_end"
    PLANAR_FACE = "planar_face"
    JOURNAL = "journal"
    CRANK_END = "crank_end"
    FAR_END = "far_end"
    CROSS_HOLE = "cross_hole"
    SHANK = "shank"


@dataclass(frozen=True)
class ViewRole:
    orientation: str
    annotation_kind: int
    entity_type: str
    resolver: ViewResolver

    @property
    def entity_kind(self):
        return {"EDGE": 1, "FACE": 2, "SILHOUETTE": 46}[self.entity_type]

    def resolve(self, module, adapter, view):
        # Deliberately replay the existing recipe resolver. These are not
        # feature-owned model selectors or a new nearest-geometry fallback.
        match self.resolver:
            case ViewResolver.BORE:
                return module.visible_circle_edge(adapter, view, module.BORE_DIA)
            case ViewResolver.TOOTH_TIP:
                return module.visible_tooth_tip_silhouette(
                    adapter, view, module.OUTSIDE_DIA
                )
            case ViewResolver.PIVOT_FACE:
                return module._cylindrical_face(adapter, view, module.JOURNAL_DIA)
            case ViewResolver.TIP_FACE:
                return module._cylindrical_face(adapter, view, module.SECTION_DIAS[-1])
            case ViewResolver.OUTER_END:
                return module._outer_end_edge(adapter, view)
            case ViewResolver.PLANAR_FACE:
                return module._largest_visible_planar_face(adapter, view)
            case ViewResolver.JOURNAL:
                return module._visible_journal_silhouette(adapter, view)
            case ViewResolver.CRANK_END | ViewResolver.FAR_END:
                candidates = module._visible_shaft_end_edges(adapter, view)
                if len(candidates) < 2 or candidates[0][0] == candidates[-1][0]:
                    raise RuntimeError("shaft end roles missing or ambiguous")
                index = 0 if self.resolver == ViewResolver.CRANK_END else -1
                return candidates[index][1]
            case ViewResolver.CROSS_HOLE:
                return module._visible_cross_hole_edge(adapter, view)
            case ViewResolver.SHANK:
                # This existing resolver activates its view (no geometry write).
                # Observation reports it explicitly; it is not getter-only.
                return module._shank_silhouette(adapter, view)
        raise RuntimeError(f"unsupported VIEW resolver {self.resolver!r}")


def _bore(label):
    return {label: ViewRole("*Front", 7, "EDGE", ViewResolver.BORE)}


VIEW_ROLES = {
    "alignment_pinion": _bore("drum bore finish"),
    "rack_pinion": _bore("rack pinion bore finish"),
    "transgear_feed_pinion": _bore("feed pinion bore finish"),
    "transgear_pinion": _bore("transgear pinion bore finish"),
    "crank_drive_gear": {
        **_bore("crank-drive gear bore finish"),
        "crank-drive gear bore axis": ViewRole("*Front", 2, "EDGE", ViewResolver.BORE),
        "gear tooth-tip circular runout": ViewRole(
            "*Right", 5, "SILHOUETTE", ViewResolver.TOOTH_TIP
        ),
    },
    "crank_pinion": {
        **_bore("crank pinion bore finish"),
        "crank pinion bore axis": ViewRole("*Front", 2, "EDGE", ViewResolver.BORE),
        "pinion tooth-tip circular runout": ViewRole(
            "*Right", 5, "SILHOUETTE", ViewResolver.TOOTH_TIP
        ),
    },
    "cylinder_gear": {
        **_bore("cylinder gear bore finish"),
        "gear face squareness to bore": ViewRole(
            "*Front", 5, "FACE", ViewResolver.PLANAR_FACE
        ),
    },
    "cone_gear_shaft": {
        "cone gear shaft PMI datum:A": ViewRole(
            "*Right", 2, "FACE", ViewResolver.PIVOT_FACE
        ),
        "cone gear shaft PMI journal_cylindricity": ViewRole(
            "*Front", 5, "EDGE", ViewResolver.OUTER_END
        ),
        "pivot journal finish": ViewRole("*Right", 7, "FACE", ViewResolver.PIVOT_FACE),
        "tip journal finish": ViewRole("*Right", 7, "FACE", ViewResolver.TIP_FACE),
    },
    "crankshaft": {
        "crank-end datum face": ViewRole("*Right", 2, "EDGE", ViewResolver.CRANK_END),
        "end-face perpendicularity": ViewRole(
            "*Right", 5, "EDGE", ViewResolver.FAR_END
        ),
        "cross-hole true position": ViewRole(
            "*Right", 5, "EDGE", ViewResolver.CROSS_HOLE
        ),
        "crankshaft bearing-journal finish": ViewRole(
            "*Right", 7, "SILHOUETTE", ViewResolver.JOURNAL
        ),
    },
    "spring_hook": {
        "shank seating finish": ViewRole("*Front", 7, "SILHOUETTE", ViewResolver.SHANK),
    },
}
