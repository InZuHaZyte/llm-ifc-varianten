import json
import logging

from graph.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


class GraphRetriever:
    """Voert een Cypher-query uit en geeft de ruwe resultaten terug."""

    def __init__(self, client: Neo4jClient):
        self._client = client

    def retrieve(self, cypher: str) -> list[dict]:
        logger.debug("Cypher uitvoeren in Neo4j")
        try:
            records = self._client.execute_query(cypher)
            logger.debug("Resultaten: %d records", len(records))
            return records
        except Exception as exc:
            logger.error("Cypher-fout: %s", exc)
            raise

    def format_results(self, records: list[dict]) -> str:
        """Maakt een leesbare string van de Neo4j-resultaten voor de LLM."""
        if not records:
            return "Geen resultaten gevonden."
        return json.dumps(records, ensure_ascii=False, indent=2, default=str)
