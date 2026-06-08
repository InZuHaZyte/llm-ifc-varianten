"""
Twee-staps Cypher-generatie:
  Stap 1 — Discovery: exacte waarden ophalen uit Neo4j
  Stap 2 — Generatie: hoofd-Cypher met die exacte waarden als context
"""
import logging
import re
from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama

from graph.neo4j_client import Neo4jClient
from graph.discovery import DiscoveryStep, DiscoveryResult
from llm.prompts import (
    GRAPH_SCHEMA,
    EXAMPLE_QUERIES,
    CYPHER_GENERATION_TEMPLATE,
)

logger = logging.getLogger(__name__)

_CODE_BLOCK = re.compile(r"```(?:cypher)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _clean_cypher(raw: str) -> str:
    match = _CODE_BLOCK.search(raw)
    if match:
        return match.group(1).strip()
    return raw.strip()


@dataclass
class GenerationResult:
    cypher: str
    discovery: DiscoveryResult | None = field(default=None)


class CypherGenerator:
    """
    Vertaalt een natuurlijke vraag naar een Cypher-query via twee LLM-stappen:
      1. Discovery — welke exacte waarden bestaan er in de database?
      2. Generatie — Cypher met die exacte waarden ingevuld.
    """

    def __init__(self, llm: ChatOllama, client: Neo4jClient):
        self._llm = llm
        self._discovery_step = DiscoveryStep(llm, client)

    def generate(self, question: str) -> GenerationResult:
        # Stap 1: discovery (kan None zijn als niet nodig)
        discovery = self._discovery_step.run(question)

        # Stap 2: hoofd-Cypher
        cypher = self._generate_final_cypher(question, discovery)
        logger.debug("Finale Cypher:\n%s", cypher)

        return GenerationResult(cypher=cypher, discovery=discovery)

    def _generate_final_cypher(
        self, question: str, discovery: DiscoveryResult | None
    ) -> str:
        if discovery and discovery.results:
            discovery_context = (
                "BESCHIKBARE WAARDEN UIT DE DATABASE "
                "(gebruik EXACT deze waarden, niet gokken of aanpassen):\n"
                + discovery.format_for_prompt()
                + "\n"
            )
        else:
            discovery_context = ""

        prompt = CYPHER_GENERATION_TEMPLATE.format(
            schema=GRAPH_SCHEMA,
            examples=EXAMPLE_QUERIES,
            discovery_context=discovery_context,
            question=question,
        )
        logger.debug("Cypher-prompt: %d tekens", len(prompt))

        response = self._llm.invoke([HumanMessage(content=prompt)])
        raw = response.content if hasattr(response, "content") else str(response)
        return _clean_cypher(raw)
