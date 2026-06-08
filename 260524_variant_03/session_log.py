from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parent / "logs"
_MAX_CHARS = 2000


class SessionLogger:
    """Schrijft gestructureerd 4-stappen sessie-logboek voor onderzoeksbijlage."""

    def __init__(self) -> None:
        _LOG_DIR.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._path = _LOG_DIR / f"sessie_variant03_{ts}.log"

    def log(self, result) -> None:  # result: AgentResult
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines: list[str] = [
            "=" * 80,
            f"VARIANT 03  |  {ts}",
            "=" * 80,
            "",
            "STAP 1 — PROMPT",
            f"  {result.question}",
            "",
            "STAP 2 — TOOL AANROEPEN (Cypher generatie)",
        ]

        query_index = 1
        if result.discovery_cypher:
            lines.append(f"  [{query_index}]  neo4j — discovery query:")
            for line in result.discovery_cypher.splitlines():
                lines.append(f"        {line}")
            lines.append("")
            query_index += 1

        lines.append(f"  [{query_index}]  neo4j — hoofd-query:")
        for line in result.cypher.splitlines():
            lines.append(f"        {line}")

        lines += ["", "STAP 3 — TOOL UITVOER (Neo4j resultaten)"]

        result_index = 1
        if result.discovery_results:
            lines.append(f"  [{result_index}]  discovery resultaten ({len(result.discovery_results)} records):")
            disc_str = json.dumps(result.discovery_results[:20], ensure_ascii=False, indent=2)
            if len(disc_str) > _MAX_CHARS:
                disc_str = disc_str[:_MAX_CHARS] + "\n        ... [ingekort]"
            for line in disc_str.splitlines():
                lines.append(f"        {line}")
            lines.append("")
            result_index += 1

        raw_count = len(result.raw_results)
        lines.append(f"  [{result_index}]  hoofd-query resultaten ({raw_count} records):")
        raw_str = json.dumps(result.raw_results[:20], ensure_ascii=False, indent=2)
        if len(raw_str) > _MAX_CHARS:
            raw_str = raw_str[:_MAX_CHARS] + "\n        ... [ingekort]"
        for line in raw_str.splitlines():
            lines.append(f"        {line}")

        lines += ["", "STAP 4 — LLM ANTWOORD"]
        for line in result.answer.splitlines():
            lines.append(f"  {line}")

        lines += [
            "",
            f"  Latency: totaal={result.latency_total_ms:.0f} ms | "
            f"cypher={result.latency_cypher_ms:.0f} ms | "
            f"query={result.latency_query_ms:.0f} ms | "
            f"antwoord={result.latency_answer_ms:.0f} ms",
            "",
            "=" * 80,
            "",
        ]

        with self._path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

    @property
    def path(self) -> Path:
        return self._path
