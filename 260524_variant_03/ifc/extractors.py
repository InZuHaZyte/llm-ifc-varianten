"""
Extraheert nodes en relaties uit een IfcOpenShell-model.
Elk extract_*-methode geeft een lijst van dicts terug, klaar voor Neo4j.
"""
import logging
from typing import Any

import ifcopenshell
import ifcopenshell.util.element

logger = logging.getLogger(__name__)


def _safe_guid(entity) -> str:
    return getattr(entity, "GlobalId", "") or ""


def _safe_name(entity) -> str:
    return getattr(entity, "Name", "") or ""


def _get_psets(entity) -> dict[str, Any]:
    try:
        return ifcopenshell.util.element.get_psets(entity)
    except Exception:
        return {}


def _pick(psets: dict, *keys: str) -> Any:
    """Zoek een property-waarde door meerdere pset-namen heen."""
    for pset_vals in psets.values():
        for key in keys:
            if key in pset_vals:
                val = pset_vals[key]
                # Wikkel IFC-waarden uit
                if hasattr(val, "wrappedValue"):
                    return val.wrappedValue
                return val
    return None


# ---------------------------------------------------------------------------
# Node extractors
# ---------------------------------------------------------------------------

def extract_projects(model: ifcopenshell.file) -> list[dict]:
    nodes = []
    for p in model.by_type("IfcProject"):
        nodes.append({
            "guid": _safe_guid(p),
            "name": _safe_name(p),
            "description": getattr(p, "Description", "") or "",
        })
    logger.debug("Projects gevonden: %d", len(nodes))
    return nodes


def extract_buildings(model: ifcopenshell.file) -> list[dict]:
    nodes = []
    for b in model.by_type("IfcBuilding"):
        nodes.append({
            "guid": _safe_guid(b),
            "name": _safe_name(b),
            "description": getattr(b, "Description", "") or "",
        })
    logger.debug("Buildings gevonden: %d", len(nodes))
    return nodes


def extract_storeys(model: ifcopenshell.file) -> list[dict]:
    nodes = []
    for s in model.by_type("IfcBuildingStorey"):
        elevation = getattr(s, "Elevation", None)
        nodes.append({
            "guid": _safe_guid(s),
            "name": _safe_name(s),
            "long_name": getattr(s, "LongName", "") or "",
            "elevation": float(elevation) if elevation is not None else None,
        })
    logger.debug("Storeys gevonden: %d", len(nodes))
    return nodes


def extract_spaces(model: ifcopenshell.file) -> list[dict]:
    nodes = []
    for sp in model.by_type("IfcSpace"):
        psets = _get_psets(sp)
        nodes.append({
            "guid": _safe_guid(sp),
            "name": _safe_name(sp),
            "long_name": getattr(sp, "LongName", "") or "",
            "occupancy": _pick(psets, "OccupancyType", "Occupancy") or "",
        })
    logger.debug("Spaces gevonden: %d", len(nodes))
    return nodes


def extract_walls(model: ifcopenshell.file) -> list[dict]:
    nodes = []
    for w in model.by_type("IfcWall"):
        psets = _get_psets(w)
        nodes.append({
            "guid": _safe_guid(w),
            "name": _safe_name(w),
            "load_bearing": bool(_pick(psets, "LoadBearing")),
            "is_external": bool(_pick(psets, "IsExternal")),
            "fire_rating": str(_pick(psets, "FireRating") or ""),
            "reference": str(_pick(psets, "Reference") or ""),
        })
    logger.debug("Walls gevonden: %d", len(nodes))
    return nodes


def extract_doors(model: ifcopenshell.file) -> list[dict]:
    nodes = []
    for d in model.by_type("IfcDoor"):
        psets = _get_psets(d)
        element_type = ifcopenshell.util.element.get_type(d)
        nodes.append({
            "guid": _safe_guid(d),
            "name": _safe_name(d),
            "type_name": _safe_name(element_type) if element_type else "",
            "overall_height": getattr(d, "OverallHeight", None),
            "overall_width": getattr(d, "OverallWidth", None),
            "fire_rating": str(_pick(psets, "FireRating") or ""),
        })
    logger.debug("Doors gevonden: %d", len(nodes))
    return nodes


def extract_windows(model: ifcopenshell.file) -> list[dict]:
    nodes = []
    for w in model.by_type("IfcWindow"):
        psets = _get_psets(w)
        element_type = ifcopenshell.util.element.get_type(w)
        nodes.append({
            "guid": _safe_guid(w),
            "name": _safe_name(w),
            "type_name": _safe_name(element_type) if element_type else "",
            "overall_height": getattr(w, "OverallHeight", None),
            "overall_width": getattr(w, "OverallWidth", None),
            "fire_rating": str(_pick(psets, "FireRating") or ""),
        })
    logger.debug("Windows gevonden: %d", len(nodes))
    return nodes


# ---------------------------------------------------------------------------
# Relationship extractors
# ---------------------------------------------------------------------------

def extract_containment_rels(model: ifcopenshell.file) -> list[dict]:
    """
    IfcRelAggregates → Project CONTAINS Building CONTAINS Storey CONTAINS ...
    IfcRelContainedInSpatialStructure → Storey CONTAINS Wall/Door/Window

    Spaces zitten in IfcRelAggregates (niet in IfcRelContainedInSpatialStructure),
    daarom maken we ON_STOREY ook aan vanuit IfcRelAggregates als de parent een Storey is.
    """
    rels = []

    for rel in model.by_type("IfcRelAggregates"):
        parent = rel.RelatingObject
        for child in rel.RelatedObjects:
            rels.append({
                "type": "CONTAINS",
                "from_guid": _safe_guid(parent),
                "to_guid": _safe_guid(child),
            })
            # Als de parent een Storey is, voeg ON_STOREY toe voor directe traversal
            if parent.is_a("IfcBuildingStorey"):
                rels.append({
                    "type": "ON_STOREY",
                    "from_guid": _safe_guid(child),
                    "to_guid": _safe_guid(parent),
                })

    for rel in model.by_type("IfcRelContainedInSpatialStructure"):
        storey = rel.RelatingStructure
        for element in rel.RelatedElements:
            rels.append({
                "type": "CONTAINS",
                "from_guid": _safe_guid(storey),
                "to_guid": _safe_guid(element),
            })
            # Omgekeerde richting voor directe toegang
            ifc_class = element.is_a()
            if ifc_class in ("IfcWall", "IfcDoor", "IfcWindow", "IfcSpace"):
                rels.append({
                    "type": "ON_STOREY",
                    "from_guid": _safe_guid(element),
                    "to_guid": _safe_guid(storey),
                })

    logger.debug("Containment relaties: %d", len(rels))
    return rels


def extract_space_boundary_rels(model: ifcopenshell.file) -> list[dict]:
    """IfcRelSpaceBoundary → Wall BOUNDS_SPACE Space"""
    rels = []
    for rel in model.by_type("IfcRelSpaceBoundary"):
        space = rel.RelatingSpace
        element = rel.RelatedBuildingElement
        if space is None or element is None:
            continue
        if element.is_a("IfcWall"):
            rels.append({
                "type": "BOUNDS_SPACE",
                "from_guid": _safe_guid(element),
                "to_guid": _safe_guid(space),
            })
    logger.debug("SpaceBoundary relaties: %d", len(rels))
    return rels


def extract_fills_opening_rels(model: ifcopenshell.file) -> list[dict]:
    """IfcRelFillsElement → Door/Window FILLS_OPENING Wall"""
    # Bouw een map: opening_guid → wall_guid
    opening_to_wall: dict[str, str] = {}
    for rel in model.by_type("IfcRelVoidsElement"):
        wall = rel.RelatingBuildingElement
        opening = rel.RelatedOpeningElement
        if wall and opening:
            opening_to_wall[_safe_guid(opening)] = _safe_guid(wall)

    rels = []
    for rel in model.by_type("IfcRelFillsElement"):
        opening = rel.RelatingOpeningElement
        filler = rel.RelatedBuildingElement
        if opening is None or filler is None:
            continue
        if not filler.is_a("IfcDoor") and not filler.is_a("IfcWindow"):
            continue
        wall_guid = opening_to_wall.get(_safe_guid(opening))
        if wall_guid:
            rels.append({
                "type": "FILLS_OPENING",
                "from_guid": _safe_guid(filler),
                "to_guid": wall_guid,
            })
    logger.debug("FillsOpening relaties: %d", len(rels))
    return rels
