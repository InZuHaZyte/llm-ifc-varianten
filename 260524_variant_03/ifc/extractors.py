"""
Extraheert nodes en relaties uit een IfcOpenShell-model.
Elk extract_*-methode geeft een lijst van dicts terug, klaar voor Neo4j.
"""
import json
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
                if hasattr(val, "wrappedValue"):
                    return val.wrappedValue
                return val
    return None


_AREA_PSET_KEYS = (
    "GrossSideArea", "NetSideArea", "GrossArea", "NetArea", "Area",
    "GrossFloorArea", "NetFloorArea", "TotalSurfaceArea", "ProjectedArea",
)
_VOLUME_PSET_KEYS = ("GrossVolume", "NetVolume", "Volume")


def _qty_area(entity, length_scale: float = 1.0) -> float | None:
    """Oppervlakte: eerst IfcQuantityArea, dan pset-property als fallback."""
    try:
        for rel in getattr(entity, "IsDefinedBy", []):
            if not rel.is_a("IfcRelDefinesByProperties"):
                continue
            pdef = rel.RelatingPropertyDefinition
            if not pdef.is_a("IfcElementQuantity"):
                continue
            for qty in (pdef.Quantities or []):
                if qty.is_a("IfcQuantityArea"):
                    val = getattr(qty, "AreaValue", None)
                    if val and float(val) > 0:
                        return round(float(val) * length_scale ** 2, 2)
    except Exception:
        pass
    raw = _pick(_get_psets(entity), *_AREA_PSET_KEYS)
    if raw is not None:
        try:
            v = float(raw)
            if v > 0:
                return round(v * length_scale ** 2, 2)
        except (TypeError, ValueError):
            pass
    return None


def _qty_volume(entity, length_scale: float = 1.0) -> float | None:
    """Volume: eerst IfcQuantityVolume, dan pset-property als fallback."""
    try:
        for rel in getattr(entity, "IsDefinedBy", []):
            if not rel.is_a("IfcRelDefinesByProperties"):
                continue
            pdef = rel.RelatingPropertyDefinition
            if not pdef.is_a("IfcElementQuantity"):
                continue
            for qty in (pdef.Quantities or []):
                if qty.is_a("IfcQuantityVolume"):
                    val = getattr(qty, "VolumeValue", None)
                    if val and float(val) > 0:
                        return round(float(val) * length_scale ** 3, 2)
    except Exception:
        pass
    raw = _pick(_get_psets(entity), *_VOLUME_PSET_KEYS)
    if raw is not None:
        try:
            v = float(raw)
            if v > 0:
                return round(v * length_scale ** 3, 2)
        except (TypeError, ValueError):
            pass
    return None


def _derive(a: float | None, b: float | None, c: float | None = None) -> float | None:
    """Berekent a×b (×c) alleen als alle waarden aanwezig en positief zijn."""
    vals = [a, b] if c is None else [a, b, c]
    if all(v is not None and v > 0 for v in vals):
        result = vals[0]
        for v in vals[1:]:
            result *= v
        return round(result, 2)
    return None


def _footprint_area(entity, length_scale: float = 1.0) -> float | None:
    """Oppervlakte via de 2D FootPrint-plattegrondcurve (shoelace-formule).

    Veel IfcSpace-elementen (o.a. deze Revit-export) hebben geen 3D-solid
    ('Body'), alleen een 'FootPrint' GeometricCurveSet + bounding box. De
    geometrie-iterator (ifc/geometry.py) kan daar dan geen mesh uit halen,
    dus wordt de plattegrond hier direct via de polylijn berekend.
    """
    rep = getattr(entity, "Representation", None)
    if not rep:
        return None
    try:
        for r in rep.Representations:
            if r.RepresentationIdentifier != "FootPrint":
                continue
            for item in r.Items:
                if not item.is_a("IfcGeometricCurveSet"):
                    continue
                for curve in item.Elements:
                    if not curve.is_a("IfcPolyline"):
                        continue
                    pts = [tuple(p.Coordinates[:2]) for p in curve.Points]
                    if len(pts) < 3:
                        continue
                    total = 0.0
                    n = len(pts)
                    for i in range(n):
                        x1, y1 = pts[i]
                        x2, y2 = pts[(i + 1) % n]
                        total += x1 * y2 - x2 * y1
                    area = abs(total) / 2.0
                    if area > 0:
                        return round(area * length_scale ** 2, 2)
    except Exception:
        pass
    return None


def _geom(geom_map: dict | None, entity, key: str) -> float | None:
    """Laatste-redmiddel fallback: waarde uit de 3D-geometrie (zie ifc/geometry.py).

    Wordt alleen gebruikt als Qto- en Pset-waarden ontbreken, wat vaak voorkomt
    bij IFC2X3-exports zonder Base Quantities.
    """
    if not geom_map:
        return None
    entry = geom_map.get(_safe_guid(entity))
    if not entry:
        return None
    val = entry.get(key)
    return val if val and val > 0 else None


def _get_length_scale(model: ifcopenshell.file) -> float:
    """Schaalfactor om modellengte-eenheid om te zetten naar meters (bijv. mm → 0.001)."""
    try:
        from ifcopenshell.util import unit as unit_util
        return unit_util.calculate_unit_scale(model)
    except Exception:
        return 1.0


def _get_quantities(entity, length_scale: float = 1.0) -> dict[str, float]:
    """Haal IfcElementQuantity-waarden op, omgezet naar SI (m / m² / m³).

    Gebruikt directe traversal van IfcElementQuantity zodat het kwantiteitstype
    (IfcQuantityLength, IfcQuantityArea, IfcQuantityVolume) bekend is en de juiste
    schaalfactor wordt toegepast.
    """
    result: dict[str, float] = {}
    try:
        for rel in getattr(entity, "IsDefinedBy", []):
            if not rel.is_a("IfcRelDefinesByProperties"):
                continue
            pdef = rel.RelatingPropertyDefinition
            if not pdef.is_a("IfcElementQuantity"):
                continue
            for qty in (pdef.Quantities or []):
                val = None
                scale = 1.0
                if qty.is_a("IfcQuantityLength"):
                    val = getattr(qty, "LengthValue", None)
                    scale = length_scale
                elif qty.is_a("IfcQuantityArea"):
                    val = getattr(qty, "AreaValue", None)
                    scale = length_scale ** 2
                elif qty.is_a("IfcQuantityVolume"):
                    val = getattr(qty, "VolumeValue", None)
                    scale = length_scale ** 3
                elif qty.is_a("IfcQuantityCount"):
                    val = getattr(qty, "CountValue", None)
                elif qty.is_a("IfcQuantityWeight"):
                    val = getattr(qty, "WeightValue", None)
                if val is not None:
                    result[qty.Name] = round(float(val) * scale, 2)
    except Exception:
        pass
    return result


def _get_material_info(entity) -> tuple[str, str]:
    """Retourneert (primaire_materialnaam, JSON-string met lagen of '')."""
    try:
        material = ifcopenshell.util.element.get_material(entity)
        if material is None:
            return "", ""

        if material.is_a("IfcMaterial"):
            return material.Name or "", ""

        if material.is_a("IfcMaterialList"):
            names = [m.Name or "" for m in (material.Materials or [])]
            return ", ".join(filter(None, names)), ""

        # Lagenset
        layer_set = None
        if material.is_a("IfcMaterialLayerSetUsage"):
            layer_set = material.ForLayerSet
        elif material.is_a("IfcMaterialLayerSet"):
            layer_set = material

        if layer_set:
            layers = []
            for layer in (layer_set.MaterialLayers or []):
                mat_name = layer.Material.Name if layer.Material else ""
                layers.append({
                    "name": mat_name or "",
                    "thickness_mm": round(layer.LayerThickness * 1000, 1) if layer.LayerThickness else None,
                })
            primary = layers[0]["name"] if layers else ""
            return primary, json.dumps(layers, ensure_ascii=False)

        return "", ""
    except Exception:
        return "", ""


# ---------------------------------------------------------------------------
# Node extractors — ruimtelijke structuur
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


def extract_sites(model: ifcopenshell.file) -> list[dict]:
    nodes = []
    for s in model.by_type("IfcSite"):
        elevation = getattr(s, "RefElevation", None)
        nodes.append({
            "guid": _safe_guid(s),
            "name": _safe_name(s),
            "description": getattr(s, "Description", "") or "",
            "elevation": round(float(elevation), 4) if elevation is not None else None,
        })
    logger.debug("Sites gevonden: %d", len(nodes))
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
    scale = _get_length_scale(model)
    nodes = []
    for s in model.by_type("IfcBuildingStorey"):
        elevation = getattr(s, "Elevation", None)
        nodes.append({
            "guid": _safe_guid(s),
            "name": _safe_name(s),
            "long_name": getattr(s, "LongName", "") or "",
            "elevation": round(float(elevation) * scale, 4) if elevation is not None else None,
        })
    logger.debug("Storeys gevonden: %d", len(nodes))
    return nodes


def extract_spaces(model: ifcopenshell.file, geom: dict | None = None) -> list[dict]:
    scale = _get_length_scale(model)
    nodes = []
    for sp in model.by_type("IfcSpace"):
        psets = _get_psets(sp)
        qtys = _get_quantities(sp, scale)
        area = (
            _qty_area(sp, scale)
            or _geom(geom, sp, "footprint_area")
            or _footprint_area(sp, scale)
        )
        height = qtys.get("Height") or _geom(geom, sp, "height")
        volume = (
            _qty_volume(sp, scale)
            or _geom(geom, sp, "volume")
            or _derive(area, height)
        )
        nodes.append({
            "guid": _safe_guid(sp),
            "name": _safe_name(sp),
            "long_name": getattr(sp, "LongName", "") or "",
            "occupancy": _pick(psets, "OccupancyType", "Occupancy") or "",
            "acoustic_rating": str(_pick(psets, "AcousticRating") or ""),
            "area": area,
            "height": height,
            "volume": volume,
        })
    logger.debug("Spaces gevonden: %d", len(nodes))
    return nodes


# ---------------------------------------------------------------------------
# Node extractors — bouwelementen (bestaand, uitgebreid)
# ---------------------------------------------------------------------------

def extract_walls(model: ifcopenshell.file, geom: dict | None = None) -> list[dict]:
    scale = _get_length_scale(model)
    nodes = []
    for w in model.by_type("IfcWall"):
        psets = _get_psets(w)
        qtys = _get_quantities(w, scale)
        element_type = ifcopenshell.util.element.get_type(w)
        mat_name, mat_layers = _get_material_info(w)
        height = qtys.get("Height") or _geom(geom, w, "height")
        nodes.append({
            "guid": _safe_guid(w),
            "name": _safe_name(w),
            "type_name": _safe_name(element_type) if element_type else "",
            "load_bearing": bool(_pick(psets, "LoadBearing")),
            "is_external": bool(_pick(psets, "IsExternal")),
            "fire_rating": str(_pick(psets, "FireRating") or ""),
            "acoustic_rating": str(_pick(psets, "AcousticRating") or ""),
            "reference": str(_pick(psets, "Reference") or ""),
            "area":   _qty_area(w, scale) or _derive(qtys.get("Length"), qtys.get("Height")) or _geom(geom, w, "side_area"),
            "length": qtys.get("Length"),
            "height": height,
            "width":  qtys.get("Width"),
            "volume": _qty_volume(w, scale) or _derive(qtys.get("Length"), qtys.get("Height"), qtys.get("Width")) or _geom(geom, w, "volume"),
            "material": mat_name,
            "material_layers": mat_layers,
        })
    logger.debug("Walls gevonden: %d", len(nodes))
    return nodes


def extract_doors(model: ifcopenshell.file, geom: dict | None = None) -> list[dict]:
    scale = _get_length_scale(model)
    nodes = []
    for d in model.by_type("IfcDoor"):
        psets = _get_psets(d)
        element_type = ifcopenshell.util.element.get_type(d)
        mat_name, _ = _get_material_info(d)
        raw_h = getattr(d, "OverallHeight", None)
        raw_w = getattr(d, "OverallWidth", None)
        height = round(float(raw_h) * scale, 2) if raw_h is not None else _geom(geom, d, "height")
        width = round(float(raw_w) * scale, 2) if raw_w is not None else None
        nodes.append({
            "guid": _safe_guid(d),
            "name": _safe_name(d),
            "type_name": _safe_name(element_type) if element_type else "",
            "overall_height": height,
            "overall_width": width,
            "fire_rating": str(_pick(psets, "FireRating") or ""),
            "acoustic_rating": str(_pick(psets, "AcousticRating") or ""),
            "area": _qty_area(d, scale) or _derive(height, width) or _geom(geom, d, "side_area"),
            "material": mat_name,
        })
    logger.debug("Doors gevonden: %d", len(nodes))
    return nodes


def extract_windows(model: ifcopenshell.file, geom: dict | None = None) -> list[dict]:
    scale = _get_length_scale(model)
    nodes = []
    for w in model.by_type("IfcWindow"):
        psets = _get_psets(w)
        element_type = ifcopenshell.util.element.get_type(w)
        mat_name, _ = _get_material_info(w)
        raw_h = getattr(w, "OverallHeight", None)
        raw_w = getattr(w, "OverallWidth", None)
        height = round(float(raw_h) * scale, 2) if raw_h is not None else _geom(geom, w, "height")
        width = round(float(raw_w) * scale, 2) if raw_w is not None else None
        nodes.append({
            "guid": _safe_guid(w),
            "name": _safe_name(w),
            "type_name": _safe_name(element_type) if element_type else "",
            "overall_height": height,
            "overall_width": width,
            "fire_rating": str(_pick(psets, "FireRating") or ""),
            "acoustic_rating": str(_pick(psets, "AcousticRating") or ""),
            "area": _qty_area(w, scale) or _derive(height, width) or _geom(geom, w, "side_area"),
            "material": mat_name,
        })
    logger.debug("Windows gevonden: %d", len(nodes))
    return nodes


# ---------------------------------------------------------------------------
# Node extractors — nieuwe bouwelementen
# ---------------------------------------------------------------------------

def extract_slabs(model: ifcopenshell.file, geom: dict | None = None) -> list[dict]:
    scale = _get_length_scale(model)
    nodes = []
    for slab in model.by_type("IfcSlab"):
        psets = _get_psets(slab)
        qtys = _get_quantities(slab, scale)
        element_type = ifcopenshell.util.element.get_type(slab)
        mat_name, mat_layers = _get_material_info(slab)
        width_val  = qtys.get("Width") or qtys.get("Thickness")
        area_val   = _qty_area(slab, scale)
        volume_val = _qty_volume(slab, scale)
        if area_val is None and volume_val and width_val:
            area_val = round(volume_val / width_val, 2)
        if volume_val is None and area_val and width_val:
            volume_val = _derive(area_val, width_val)
        area_val = area_val or _geom(geom, slab, "footprint_area")
        volume_val = volume_val or _geom(geom, slab, "volume")
        if width_val is None and volume_val and area_val:
            width_val = round(volume_val / area_val, 3)
        nodes.append({
            "guid": _safe_guid(slab),
            "name": _safe_name(slab),
            "type_name": _safe_name(element_type) if element_type else "",
            "load_bearing": bool(_pick(psets, "LoadBearing")),
            "is_external": bool(_pick(psets, "IsExternal")),
            "fire_rating": str(_pick(psets, "FireRating") or ""),
            "acoustic_rating": str(_pick(psets, "AcousticRating") or ""),
            "area":   area_val,
            "length": qtys.get("Length"),
            "width":  width_val,
            "volume": volume_val,
            "material": mat_name,
            "material_layers": mat_layers,
        })
    logger.debug("Slabs gevonden: %d", len(nodes))
    return nodes


def extract_roofs(model: ifcopenshell.file, geom: dict | None = None) -> list[dict]:
    scale = _get_length_scale(model)
    nodes = []
    for roof in model.by_type("IfcRoof"):
        psets = _get_psets(roof)
        element_type = ifcopenshell.util.element.get_type(roof)
        mat_name, mat_layers = _get_material_info(roof)
        nodes.append({
            "guid": _safe_guid(roof),
            "name": _safe_name(roof),
            "type_name": _safe_name(element_type) if element_type else "",
            "is_external": bool(_pick(psets, "IsExternal")),
            "fire_rating": str(_pick(psets, "FireRating") or ""),
            "area": _qty_area(roof, scale) or _geom(geom, roof, "footprint_area"),
            "volume": _qty_volume(roof, scale) or _geom(geom, roof, "volume"),
            "material": mat_name,
            "material_layers": mat_layers,
        })
    logger.debug("Roofs gevonden: %d", len(nodes))
    return nodes


def extract_stairs(model: ifcopenshell.file, geom: dict | None = None) -> list[dict]:
    scale = _get_length_scale(model)
    nodes = []
    for stair in model.by_type("IfcStair"):
        psets = _get_psets(stair)
        qtys = _get_quantities(stair, scale)
        element_type = ifcopenshell.util.element.get_type(stair)
        nodes.append({
            "guid": _safe_guid(stair),
            "name": _safe_name(stair),
            "type_name": _safe_name(element_type) if element_type else "",
            "fire_rating": str(_pick(psets, "FireRating") or ""),
            "acoustic_rating": str(_pick(psets, "AcousticRating") or ""),
            "length": qtys.get("Length"),
            "height": qtys.get("Height") or _geom(geom, stair, "height"),
            "width": qtys.get("Width"),
            "volume": _qty_volume(stair, scale) or _geom(geom, stair, "volume"),
        })
    logger.debug("Stairs gevonden: %d", len(nodes))
    return nodes


def extract_coverings(model: ifcopenshell.file, geom: dict | None = None) -> list[dict]:
    scale = _get_length_scale(model)
    nodes = []
    for cov in model.by_type("IfcCovering"):
        psets = _get_psets(cov)
        qtys = _get_quantities(cov, scale)
        element_type = ifcopenshell.util.element.get_type(cov)
        mat_name, mat_layers = _get_material_info(cov)
        width_val = qtys.get("Width") or qtys.get("Thickness") or qtys.get("Depth")
        area_val = _qty_area(cov, scale) or _geom(geom, cov, "footprint_area")
        volume_val = (
            _qty_volume(cov, scale)
            or _derive(_qty_area(cov, scale), width_val)
            or _geom(geom, cov, "volume")
        )
        if width_val is None and volume_val and area_val:
            width_val = round(volume_val / area_val, 3)
        nodes.append({
            "guid": _safe_guid(cov),
            "name": _safe_name(cov),
            "type_name": _safe_name(element_type) if element_type else "",
            "fire_rating": str(_pick(psets, "FireRating") or ""),
            "acoustic_rating": str(_pick(psets, "AcousticRating") or ""),
            "area":   area_val,
            "length": qtys.get("Length"),
            "width":  width_val,
            "volume": volume_val,
            "material": mat_name,
            "material_layers": mat_layers,
        })
    logger.debug("Coverings gevonden: %d", len(nodes))
    return nodes


def extract_columns(model: ifcopenshell.file, geom: dict | None = None) -> list[dict]:
    scale = _get_length_scale(model)
    nodes = []
    for col in model.by_type("IfcColumn"):
        psets = _get_psets(col)
        qtys = _get_quantities(col, scale)
        element_type = ifcopenshell.util.element.get_type(col)
        mat_name, mat_layers = _get_material_info(col)
        length_val = qtys.get("Length") or _geom(geom, col, "height")
        nodes.append({
            "guid": _safe_guid(col),
            "name": _safe_name(col),
            "type_name": _safe_name(element_type) if element_type else "",
            "load_bearing": bool(_pick(psets, "LoadBearing")),
            "is_external": bool(_pick(psets, "IsExternal")),
            "fire_rating": str(_pick(psets, "FireRating") or ""),
            "area":   _qty_area(col, scale) or _geom(geom, col, "side_area"),
            "length": length_val,
            "volume": _qty_volume(col, scale) or _derive(_qty_area(col, scale), qtys.get("Length")) or _geom(geom, col, "volume"),
            "material": mat_name,
            "material_layers": mat_layers,
        })
    logger.debug("Columns gevonden: %d", len(nodes))
    return nodes


def extract_beams(model: ifcopenshell.file, geom: dict | None = None) -> list[dict]:
    scale = _get_length_scale(model)
    nodes = []
    for beam in model.by_type("IfcBeam"):
        psets = _get_psets(beam)
        qtys = _get_quantities(beam, scale)
        element_type = ifcopenshell.util.element.get_type(beam)
        mat_name, mat_layers = _get_material_info(beam)
        nodes.append({
            "guid": _safe_guid(beam),
            "name": _safe_name(beam),
            "type_name": _safe_name(element_type) if element_type else "",
            "load_bearing": bool(_pick(psets, "LoadBearing")),
            "fire_rating": str(_pick(psets, "FireRating") or ""),
            "area":   _qty_area(beam, scale) or _geom(geom, beam, "side_area"),
            "length": qtys.get("Length"),
            "volume": _qty_volume(beam, scale) or _derive(_qty_area(beam, scale), qtys.get("Length")) or _geom(geom, beam, "volume"),
            "material": mat_name,
            "material_layers": mat_layers,
        })
    logger.debug("Beams gevonden: %d", len(nodes))
    return nodes


def extract_railings(model: ifcopenshell.file, geom: dict | None = None) -> list[dict]:
    scale = _get_length_scale(model)
    nodes = []
    for rail in model.by_type("IfcRailing"):
        psets = _get_psets(rail)
        qtys = _get_quantities(rail, scale)
        element_type = ifcopenshell.util.element.get_type(rail)
        mat_name, mat_layers = _get_material_info(rail)
        nodes.append({
            "guid": _safe_guid(rail),
            "name": _safe_name(rail),
            "type_name": _safe_name(element_type) if element_type else "",
            "fire_rating": str(_pick(psets, "FireRating") or ""),
            "area":   _qty_area(rail, scale) or _geom(geom, rail, "side_area"),
            "length": qtys.get("Length"),
            "height": qtys.get("Height") or _geom(geom, rail, "height"),
            "volume": _qty_volume(rail, scale) or _geom(geom, rail, "volume"),
            "material": mat_name,
            "material_layers": mat_layers,
        })
    logger.debug("Railings gevonden: %d", len(nodes))
    return nodes


def extract_members(model: ifcopenshell.file, geom: dict | None = None) -> list[dict]:
    scale = _get_length_scale(model)
    nodes = []
    for mem in model.by_type("IfcMember"):
        psets = _get_psets(mem)
        qtys = _get_quantities(mem, scale)
        element_type = ifcopenshell.util.element.get_type(mem)
        mat_name, mat_layers = _get_material_info(mem)
        nodes.append({
            "guid": _safe_guid(mem),
            "name": _safe_name(mem),
            "type_name": _safe_name(element_type) if element_type else "",
            "load_bearing": bool(_pick(psets, "LoadBearing")),
            "fire_rating": str(_pick(psets, "FireRating") or ""),
            "area":   _qty_area(mem, scale) or _geom(geom, mem, "side_area"),
            "length": qtys.get("Length"),
            "volume": _qty_volume(mem, scale) or _derive(_qty_area(mem, scale), qtys.get("Length")) or _geom(geom, mem, "volume"),
            "material": mat_name,
            "material_layers": mat_layers,
        })
    logger.debug("Members gevonden: %d", len(nodes))
    return nodes


# ---------------------------------------------------------------------------
# Relationship extractors
# ---------------------------------------------------------------------------

_CONTAINMENT_TYPES = frozenset({
    "IfcWall", "IfcDoor", "IfcWindow", "IfcSpace",
    "IfcSlab", "IfcRoof", "IfcStair", "IfcCovering",
    "IfcColumn", "IfcBeam", "IfcRailing", "IfcMember",
})


def extract_containment_rels(model: ifcopenshell.file) -> list[dict]:
    """
    IfcRelAggregates → Project CONTAINS Building CONTAINS Storey CONTAINS ...
    IfcRelContainedInSpatialStructure → Storey CONTAINS bouwelementen
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
            if any(element.is_a(t) for t in _CONTAINMENT_TYPES):
                rels.append({
                    "type": "ON_STOREY",
                    "from_guid": _safe_guid(element),
                    "to_guid": _safe_guid(storey),
                })

    logger.debug("Containment relaties: %d", len(rels))
    return rels


_BOUNDARY_TYPES = frozenset({
    "IfcWall", "IfcSlab", "IfcColumn", "IfcBeam", "IfcCovering",
})


def extract_space_boundary_rels(model: ifcopenshell.file) -> list[dict]:
    """IfcRelSpaceBoundary → element BOUNDS_SPACE Space"""
    rels = []
    for rel in model.by_type("IfcRelSpaceBoundary"):
        space = rel.RelatingSpace
        element = rel.RelatedBuildingElement
        if space is None or element is None:
            continue
        if any(element.is_a(t) for t in _BOUNDARY_TYPES):
            rels.append({
                "type": "BOUNDS_SPACE",
                "from_guid": _safe_guid(element),
                "to_guid": _safe_guid(space),
            })
    logger.debug("SpaceBoundary relaties: %d", len(rels))
    return rels


def extract_door_window_storey_rels(model: ifcopenshell.file) -> list[dict]:
    """Leidt CONTAINS/ON_STOREY af voor deuren en ramen via hun hostwand.

    Veel IFC-exporters plaatsen deuren/ramen niet in IfcRelContainedInSpatialStructure.
    Ze zijn alleen gekoppeld via IfcRelFillsElement. Deze functie overbrugt dat gat:
    deur/raam → opening → wand → verdieping.
    """
    wall_to_storey: dict[str, str] = {}
    for rel in model.by_type("IfcRelContainedInSpatialStructure"):
        if not rel.RelatingStructure.is_a("IfcBuildingStorey"):
            continue
        storey_guid = _safe_guid(rel.RelatingStructure)
        for el in rel.RelatedElements:
            if el.is_a("IfcWall") or el.is_a("IfcWallStandardCase"):
                wall_to_storey[_safe_guid(el)] = storey_guid

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
        if not opening or not filler:
            continue
        if not (filler.is_a("IfcDoor") or filler.is_a("IfcWindow")):
            continue
        wall_guid = opening_to_wall.get(_safe_guid(opening))
        storey_guid = wall_to_storey.get(wall_guid) if wall_guid else None
        if not storey_guid:
            continue
        filler_guid = _safe_guid(filler)
        rels.append({"type": "CONTAINS",  "from_guid": storey_guid, "to_guid": filler_guid})
        rels.append({"type": "ON_STOREY", "from_guid": filler_guid, "to_guid": storey_guid})

    logger.debug("Door/Window storey-relaties afgeleid: %d", len(rels))
    return rels


def extract_fills_opening_rels(model: ifcopenshell.file) -> list[dict]:
    """IfcRelFillsElement → Door/Window FILLS_OPENING Wall"""
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
