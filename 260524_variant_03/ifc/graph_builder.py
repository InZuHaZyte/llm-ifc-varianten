"""
Orkestreert alle extractors en geeft een GraphData-object terug
dat direct aan Neo4jClient gevoerd kan worden.
"""
import logging
from dataclasses import dataclass, field

import ifcopenshell

from ifc import extractors as ex

logger = logging.getLogger(__name__)


@dataclass
class GraphData:
    projects: list[dict] = field(default_factory=list)
    buildings: list[dict] = field(default_factory=list)
    storeys: list[dict] = field(default_factory=list)
    spaces: list[dict] = field(default_factory=list)
    walls: list[dict] = field(default_factory=list)
    doors: list[dict] = field(default_factory=list)
    windows: list[dict] = field(default_factory=list)
    relationships: list[dict] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"Projects={len(self.projects)} | Buildings={len(self.buildings)} | "
            f"Storeys={len(self.storeys)} | Spaces={len(self.spaces)} | "
            f"Walls={len(self.walls)} | Doors={len(self.doors)} | "
            f"Windows={len(self.windows)} | Relaties={len(self.relationships)}"
        )


class GraphBuilder:
    """Zet een IfcOpenShell-model om naar een GraphData-object."""

    def build(self, model: ifcopenshell.file) -> GraphData:
        logger.info("Graph bouwen vanuit IFC-model...")

        data = GraphData(
            projects=ex.extract_projects(model),
            buildings=ex.extract_buildings(model),
            storeys=ex.extract_storeys(model),
            spaces=ex.extract_spaces(model),
            walls=ex.extract_walls(model),
            doors=ex.extract_doors(model),
            windows=ex.extract_windows(model),
        )

        data.relationships = (
            ex.extract_containment_rels(model)
            + ex.extract_space_boundary_rels(model)
            + ex.extract_fills_opening_rels(model)
        )

        logger.info("Graph gebouwd: %s", data.summary())
        return data
