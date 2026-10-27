"""
Geometrie-gebaseerde fallback voor oppervlakte, volume en hoogte.

Veel IFC2X3-exports (waaronder academische datasets zoals Schependomlaan)
bevatten geen of onvolledige IfcElementQuantity Base Quantities. Om toch
altijd een waarde te kunnen tonen (m², m³) wordt de 3D-geometrie van elk
element één keer doorlopen en worden volume, footprint-oppervlakte,
zijoppervlakte en hoogte rechtstreeks uit de mesh berekend. Extractors
gebruiken dit alleen als laatste fallback, na Qto- en Pset-waarden.
"""
import logging

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape as shape_util

logger = logging.getLogger(__name__)

GEOM_TYPES = (
    "IfcSpace", "IfcWall", "IfcSlab", "IfcRoof", "IfcDoor", "IfcWindow",
    "IfcColumn", "IfcBeam", "IfcCovering", "IfcStair",
    "IfcRailing", "IfcMember",
)


def compute_geometric_quantities(model: ifcopenshell.file) -> dict[str, dict[str, float]]:
    """Berekent per GlobalId {volume, footprint_area, side_area, height} uit de geometrie."""
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)

    quantities: dict[str, dict[str, float]] = {}
    try:
        iterator = ifcopenshell.geom.iterator(
            settings, model, num_threads=8, include=list(GEOM_TYPES)
        )
    except Exception:
        logger.warning("Geometrie-iterator kon niet worden gestart", exc_info=True)
        return quantities

    if not iterator.initialize():
        return quantities

    processed = 0
    while True:
        shape = iterator.get()
        geom = shape.geometry
        entry: dict[str, float] = {}
        try:
            vertices = shape_util.get_vertices(geom)
            if len(vertices):
                zmin, zmax = float(vertices[:, 2].min()), float(vertices[:, 2].max())
                if zmax > zmin:
                    entry["height"] = round(zmax - zmin, 3)
        except Exception:
            pass
        try:
            entry["volume"] = round(shape_util.get_volume(geom), 3)
        except Exception:
            pass
        try:
            entry["footprint_area"] = round(shape_util.get_footprint_area(geom), 3)
        except Exception:
            pass
        try:
            entry["side_area"] = round(shape_util.get_max_side_area(geom), 3)
        except Exception:
            pass
        if entry:
            quantities[shape.guid] = entry
        processed += 1
        if not iterator.next():
            break

    logger.info(
        "Geometrische fallback-quantities berekend voor %d/%d elementen",
        len(quantities), processed,
    )
    return quantities
