"""
Parameter-discovery: vraagt de LLM welke exacte waarden nodig zijn,
haalt die op uit Neo4j, en geeft ze terug als context voor de hoofd-query.

Flow:
  Vraag → LLM beslist discovery-Cypher → Neo4j → exacte waarden
"""
import logging
import re
from dataclasses import dataclass

from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama

from graph.neo4j_client import Neo4jClient
from llm.prompts import DISCOVERY_PROMPT

logger = logging.getLogger(__name__)

_CODE_BLOCK = re.compile(r"```(?:cypher)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _clean_cypher(raw: str) -> str:
    match = _CODE_BLOCK.search(raw)
    if match:
        return match.group(1).strip()
    return raw.strip()


@dataclass
class DiscoveryResult:
    cypher: str
    results: list[dict]

    def format_for_prompt(self) -> str:
        """Compacte lijst van gevonden waarden, klaar voor de LLM-prompt."""
        if not self.results:
            return "Geen waarden gevonden."
        lines = []
        for record in self.results:
            parts = [f"{k}: {v}" for k, v in record.items() if v is not None and v != ""]
            if parts:
                lines.append("  - " + " | ".join(parts))
        return "\n".join(lines)


class DiscoveryStep:
    """
    Stap 1 van de twee-staps pipeline.
    Vraagt de LLM of discovery nodig is, en zo ja: welke Cypher.
    """

    def __init__(self, llm: ChatOllama, client: Neo4jClient):
        self._llm = llm
        self._client = client

    def run(self, question: str) -> DiscoveryResult | None:
        discovery_cypher = self._decide(question)
        if discovery_cypher is None:
            return None

        logger.info("DISCOVERY CYPHER:\n%s", discovery_cypher)
        try:
            results = self._client.execute_query(discovery_cypher)
        except Exception as exc:
            logger.warning("Discovery query mislukt: %s", exc)
            return None

        logger.info("DISCOVERY: %d waarden opgehaald", len(results))
        return DiscoveryResult(cypher=discovery_cypher, results=results)

    def _decide(self, question: str) -> str | None:
        """Vraagt de LLM: welke discovery-Cypher is nodig? Antwoord: NONE of een Cypher."""
        prompt = DISCOVERY_PROMPT.format(question=question)
        response = self._llm.invoke([HumanMessage(content=prompt)])
        raw = response.content.strip() if hasattr(response, "content") else str(response).strip()

        logger.debug("Discovery LLM-antwoord: %s", raw[:300])

        if not raw or raw.upper().startswith("NONE"):
            return None

        cleaned = _clean_cypher(raw)
        return cleaned if cleaned and cleaned.upper() != "NONE" else None
