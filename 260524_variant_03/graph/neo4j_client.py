"""
Neo4j-client: verbinding, schema-setup en batch-inlaad van GraphData.
Neo4j Browser: http://localhost:7474
"""
import logging
from contextlib import contextmanager
from typing import Any

from neo4j import GraphDatabase, Driver

from ifc.graph_builder import GraphData

logger = logging.getLogger(__name__)

CONSTRAINTS = [
    "CREATE CONSTRAINT project_guid  IF NOT EXISTS FOR (n:Project)  REQUIRE n.guid IS UNIQUE",
    "CREATE CONSTRAINT site_guid     IF NOT EXISTS FOR (n:Site)     REQUIRE n.guid IS UNIQUE",
    "CREATE CONSTRAINT building_guid IF NOT EXISTS FOR (n:Building) REQUIRE n.guid IS UNIQUE",
    "CREATE CONSTRAINT storey_guid   IF NOT EXISTS FOR (n:Storey)   REQUIRE n.guid IS UNIQUE",
    "CREATE CONSTRAINT space_guid    IF NOT EXISTS FOR (n:Space)    REQUIRE n.guid IS UNIQUE",
    "CREATE CONSTRAINT wall_guid     IF NOT EXISTS FOR (n:Wall)     REQUIRE n.guid IS UNIQUE",
    "CREATE CONSTRAINT door_guid     IF NOT EXISTS FOR (n:Door)     REQUIRE n.guid IS UNIQUE",
    "CREATE CONSTRAINT window_guid   IF NOT EXISTS FOR (n:Window)   REQUIRE n.guid IS UNIQUE",
    "CREATE CONSTRAINT slab_guid     IF NOT EXISTS FOR (n:Slab)     REQUIRE n.guid IS UNIQUE",
    "CREATE CONSTRAINT roof_guid     IF NOT EXISTS FOR (n:Roof)     REQUIRE n.guid IS UNIQUE",
    "CREATE CONSTRAINT stair_guid    IF NOT EXISTS FOR (n:Stair)    REQUIRE n.guid IS UNIQUE",
    "CREATE CONSTRAINT covering_guid IF NOT EXISTS FOR (n:Covering) REQUIRE n.guid IS UNIQUE",
    "CREATE CONSTRAINT column_guid   IF NOT EXISTS FOR (n:Column)   REQUIRE n.guid IS UNIQUE",
    "CREATE CONSTRAINT beam_guid     IF NOT EXISTS FOR (n:Beam)     REQUIRE n.guid IS UNIQUE",
    "CREATE CONSTRAINT railing_guid  IF NOT EXISTS FOR (n:Railing)  REQUIRE n.guid IS UNIQUE",
    "CREATE CONSTRAINT member_guid   IF NOT EXISTS FOR (n:Member)   REQUIRE n.guid IS UNIQUE",
]

BROWSER_HINTS = """
-- Volledige hiërarchie
MATCH p=(:Project)-[:CONTAINS*]->() RETURN p LIMIT 100

-- Verdiepingen met alle bouwelementen
MATCH (s:Storey)-[:CONTAINS]->(e) RETURN s, e LIMIT 100

-- Wanden met materiaallagen
MATCH (w:Wall) WHERE w.material_layers <> '' RETURN w.name, w.material, w.material_layers LIMIT 25

-- Vloeren (slabs) per verdieping
MATCH (st:Storey)-[:CONTAINS]->(sl:Slab) RETURN st.name, sl.name, sl.area, sl.width, sl.length LIMIT 50

-- Kolommen en balken
MATCH (st:Storey)-[:CONTAINS]->(e) WHERE e:Column OR e:Beam RETURN st.name, labels(e), e.name, e.material LIMIT 50

-- Akoestisch geclassificeerde elementen
MATCH (e) WHERE e.acoustic_rating <> '' RETURN labels(e), e.name, e.acoustic_rating LIMIT 50

-- Deuren in wanden
MATCH (d:Door)-[:FILLS_OPENING]->(w:Wall) RETURN d, w LIMIT 50
"""


class Neo4jClient:
    def __init__(self, uri: str, user: str, password: str):
        self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info("Neo4j verbonden: %s", uri)

    def close(self):
        self._driver.close()
        logger.info("Neo4j verbinding gesloten")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    @contextmanager
    def _session(self):
        with self._driver.session() as session:
            yield session

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def setup_schema(self):
        with self._session() as s:
            for cypher in CONSTRAINTS:
                s.run(cypher)
        logger.info("Schema constraints aangemaakt")

    def clear_graph(self):
        with self._session() as s:
            s.run("MATCH (n) DETACH DELETE n")
        logger.info("Graph geleegd")

    # ------------------------------------------------------------------
    # Data inladen
    # ------------------------------------------------------------------

    def _batch_create_nodes(self, session, label: str, nodes: list[dict]):
        if not nodes:
            return
        cypher = (
            f"UNWIND $rows AS row "
            f"MERGE (n:{label} {{guid: row.guid}}) "
            f"SET n += row"
        )
        session.run(cypher, rows=nodes)
        logger.debug("%s: %d nodes aangemaakt", label, len(nodes))

    def _batch_create_relationships(self, session, relationships: list[dict]):
        if not relationships:
            return

        by_type: dict[str, list[dict]] = {}
        for rel in relationships:
            by_type.setdefault(rel["type"], []).append(rel)

        for rel_type, rels in by_type.items():
            cypher = (
                "UNWIND $rows AS row "
                "MATCH (a {guid: row.from_guid}) "
                "MATCH (b {guid: row.to_guid}) "
                f"MERGE (a)-[:{rel_type}]->(b)"
            )
            session.run(cypher, rows=rels)
            logger.debug("%s: %d relaties aangemaakt", rel_type, len(rels))

    def load_graph_data(self, data: GraphData):
        logger.info("GraphData naar Neo4j schrijven...")
        with self._session() as s:
            self._batch_create_nodes(s, "Project",  data.projects)
            self._batch_create_nodes(s, "Site",     data.sites)
            self._batch_create_nodes(s, "Building", data.buildings)
            self._batch_create_nodes(s, "Storey",   data.storeys)
            self._batch_create_nodes(s, "Space",    data.spaces)
            self._batch_create_nodes(s, "Wall",     data.walls)
            self._batch_create_nodes(s, "Door",     data.doors)
            self._batch_create_nodes(s, "Window",   data.windows)
            self._batch_create_nodes(s, "Slab",     data.slabs)
            self._batch_create_nodes(s, "Roof",     data.roofs)
            self._batch_create_nodes(s, "Stair",    data.stairs)
            self._batch_create_nodes(s, "Covering", data.coverings)
            self._batch_create_nodes(s, "Column",   data.columns)
            self._batch_create_nodes(s, "Beam",     data.beams)
            self._batch_create_nodes(s, "Railing",  data.railings)
            self._batch_create_nodes(s, "Member",   data.members)
            self._batch_create_relationships(s, data.relationships)
        logger.info("GraphData geladen in Neo4j")

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def execute_query(self, cypher: str, params: dict | None = None) -> list[dict]:
        params = params or {}
        with self._session() as s:
            result = s.run(cypher, **params)
            records = [dict(r) for r in result]
        logger.debug("Query teruggegeven %d records", len(records))
        return records

    def get_schema_summary(self) -> str:
        """Geeft een beknopt schema-overzicht voor de LLM-prompt."""
        with self._session() as s:
            labels = [r["label"] for r in s.run("CALL db.labels() YIELD label RETURN label")]
            rel_types = [r["relationshipType"] for r in s.run(
                "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"
            )]
        return f"Labels: {labels}\nRelaties: {rel_types}"
