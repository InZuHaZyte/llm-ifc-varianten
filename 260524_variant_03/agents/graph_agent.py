"""
GraphAgent: orkestreert de volledige twee-staps pipeline

  Stap 1 — Discovery:  Vraag → LLM beslist discovery-Cypher → Neo4j → exacte waarden
  Stap 2 — Generatie:  Vraag + exacte waarden → LLM → hoofd-Cypher → Neo4j → antwoord

Logt bij elke stap: discovery, cypher, resultaat, antwoord, latency.
"""
import logging
import time
from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage

from graph.cypher_generator import CypherGenerator, GenerationResult
from graph.discovery import DiscoveryResult
from graph.retrieval import GraphRetriever
from graph.neo4j_client import Neo4jClient
from llm.model import get_llm
from llm.prompts import ANSWER_GENERATION_TEMPLATE
from config import AppConfig

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    question: str
    # Discovery (stap 1)
    discovery_cypher: str | None
    discovery_results: list[dict] | None
    # Hoofd-query (stap 2)
    cypher: str
    raw_results: list[dict]
    answer: str
    # Latency
    latency_total_ms: float
    latency_discovery_ms: float
    latency_cypher_ms: float
    latency_query_ms: float
    latency_answer_ms: float


class GraphAgent:
    def __init__(self, config: AppConfig, neo4j_client: Neo4jClient):
        self._cfg = config
        self._llm = get_llm(config.ollama)
        self._client = neo4j_client
        self._generator = CypherGenerator(self._llm, neo4j_client)
        self._retriever = GraphRetriever(neo4j_client)

    def run(self, question: str) -> AgentResult:
        t_start = time.perf_counter()
        logger.info("=" * 60)
        logger.info("VRAAG: %s", question)

        # ------------------------------------------------------------------
        # Stap 1 + 2: Discovery → Cypher generatie
        # ------------------------------------------------------------------
        t0 = time.perf_counter()
        gen: GenerationResult = self._generator.generate(question)
        t_gen = (time.perf_counter() - t0) * 1000

        # Splitst discovery-tijd en cypher-tijd niet afzonderlijk (beide in generator)
        # maar we loggen ze beide duidelijk.
        discovery: DiscoveryResult | None = gen.discovery
        t_discovery_ms = 0.0
        t_cypher_ms = t_gen  # totaal van beide LLM-calls

        if discovery:
            logger.info(
                "DISCOVERY CYPHER:\n%s",
                discovery.cypher,
            )
            logger.info(
                "DISCOVERY WAARDEN (%d):\n%s",
                len(discovery.results),
                discovery.format_for_prompt(),
            )
        else:
            logger.info("DISCOVERY: niet nodig voor deze vraag")

        logger.info("HOOFD-CYPHER (%dms totaal):\n%s", t_gen, gen.cypher)

        # ------------------------------------------------------------------
        # Stap 3: Cypher → Neo4j
        # ------------------------------------------------------------------
        t0 = time.perf_counter()
        try:
            raw_results = self._retriever.retrieve(gen.cypher)
        except Exception as exc:
            raw_results = []
            logger.error("Query mislukt: %s", exc)
        t_query = (time.perf_counter() - t0) * 1000
        formatted = self._retriever.format_results(raw_results)
        logger.info("RESULTAAT (%dms): %d records", t_query, len(raw_results))
        logger.debug("RESULTAAT DETAIL:\n%s", formatted)

        # ------------------------------------------------------------------
        # Stap 4: Resultaten → leesbaar antwoord
        # ------------------------------------------------------------------
        t0 = time.perf_counter()
        answer = self._generate_answer(question, gen.cypher, formatted)
        t_answer = (time.perf_counter() - t0) * 1000

        t_total = (time.perf_counter() - t_start) * 1000
        logger.info("ANTWOORD (%dms):\n%s", t_answer, answer)
        logger.info(
            "LATENCY | totaal=%.0fms | discovery+cypher=%.0fms | query=%.0fms | antwoord=%.0fms",
            t_total, t_gen, t_query, t_answer,
        )
        logger.info("=" * 60)

        return AgentResult(
            question=question,
            discovery_cypher=discovery.cypher if discovery else None,
            discovery_results=discovery.results if discovery else None,
            cypher=gen.cypher,
            raw_results=raw_results,
            answer=answer,
            latency_total_ms=t_total,
            latency_discovery_ms=t_discovery_ms,
            latency_cypher_ms=t_cypher_ms,
            latency_query_ms=t_query,
            latency_answer_ms=t_answer,
        )

    def _generate_answer(self, question: str, cypher: str, results: str) -> str:
        prompt = ANSWER_GENERATION_TEMPLATE.format(
            question=question,
            cypher=cypher,
            results=results,
        )
        try:
            response = self._llm.invoke([HumanMessage(content=prompt)])
            return response.content if hasattr(response, "content") else str(response)
        except Exception as exc:
            logger.error("Antwoord-generatie mislukt: %s", exc)
            return f"Fout bij antwoordgeneratie: {exc}"
