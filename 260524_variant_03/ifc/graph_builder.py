"""
Orkestreert alle extractors en geeft een GraphData-object terug
dat direct aan Neo4jClient gevoerd kan worden.
"""
import logging
from dataclasses import dataclass, field

import ifcopenshell

from ifc import extractors as ex
from ifc.geometry import compute_geometric_quantities

logger = logging.getLogger(__name__)


@dataclass
class GraphData:
    projects: list[dict] = field(default_factory=list)
    sites: list[dict] = field(default_factory=list)
    buildings: list[dict] = field(default_factory=list)
    storeys: list[dict] = field(default_factory=list)
    spaces: list[dict] = field(default_factory=list)
    walls: list[dict] = field(default_factory=list)
    doors: list[dict] = field(default_factory=list)
    windows: list[dict] = field(default_factory=list)
    slabs: list[dict] = field(default_factory=list)
    roofs: list[dict] = field(default_factory=list)
    stairs: list[dict] = field(default_factory=list)
    coverings: list[dict] = field(default_factory=list)
    columns: list[dict] = field(default_factory=list)
    beams: list[dict] = field(default_factory=list)
    railings: list[dict] = field(default_factory=list)
    members: list[dict] = field(default_factory=list)
    relationships: list[dict] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"Projects={len(self.projects)} | Sites={len(self.sites)} | "
            f"Buildings={len(self.buildings)} | "
            f"Storeys={len(self.storeys)} | Spaces={len(self.spaces)} | "
            f"Walls={len(self.walls)} | Doors={len(self.doors)} | "
            f"Windows={len(self.windows)} | Slabs={len(self.slabs)} | "
            f"Roofs={len(self.roofs)} | Stairs={len(self.stairs)} | "
            f"Coverings={len(self.coverings)} | Columns={len(self.columns)} | "
            f"Beams={len(self.beams)} | Railings={len(self.railings)} | "
            f"Members={len(self.members)} | Relaties={len(self.relationships)}"
        )


class GraphBuilder:
    """Zet een IfcOpenShell-model om naar een GraphData-object."""

    def build(self, model: ifcopenshell.file) -> GraphData:
        logger.info("Graph bouwen vanuit IFC-model...")

        logger.info("Geometrische fallback-quantities berekenen (voor ontbrekende m²/m³)...")
        geom = compute_geometric_quantities(model)

        data = GraphData(
            projects=ex.extract_projects(model),
            sites=ex.extract_sites(model),
            buildings=ex.extract_buildings(model),
            storeys=ex.extract_storeys(model),
            spaces=ex.extract_spaces(model, geom),
            walls=ex.extract_walls(model, geom),
            doors=ex.extract_doors(model, geom),
            windows=ex.extract_windows(model, geom),
            slabs=ex.extract_slabs(model, geom),
            roofs=ex.extract_roofs(model, geom),
            stairs=ex.extract_stairs(model, geom),
            coverings=ex.extract_coverings(model, geom),
            columns=ex.extract_columns(model, geom),
            beams=ex.extract_beams(model, geom),
            railings=ex.extract_railings(model, geom),
            members=ex.extract_members(model, geom),
        )

        data.relationships = (
            ex.extract_containment_rels(model)
            + ex.extract_space_boundary_rels(model)
            + ex.extract_fills_opening_rels(model)
            + ex.extract_door_window_storey_rels(model)
        )

        logger.info("Graph gebouwd: %s", data.summary())
        return data
