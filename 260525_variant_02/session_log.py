from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parent / "logs"
_MAX_CHARS = 2000


class SessionLogger:
    """Schrijft gestructureerd 4-stappen sessie-logboek voor onderzoeksbijlage."""

    def __init__(self, variant: str) -> None:
        _LOG_DIR.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._path = _LOG_DIR / f"sessie_{variant}_{ts}.log"
        self._variant = variant.upper()

    def log(
        self,
        prompt: str,
        tool_calls: list[dict],
        answer: str,
        duration_ms: float = 0.0,
    ) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines: list[str] = [
            "=" * 80,
            f"{self._variant}  |  {ts}",
            "=" * 80,
            "",
            "STAP 1 — PROMPT",
            f"  {prompt}",
            "",
            "STAP 2 — TOOL AANROEPEN",
        ]

        if tool_calls:
            for i, call in enumerate(tool_calls, 1):
                inp = call.get("input", "").strip()
                lines.append(f"  [{i}]  {call['name']}")
                if inp and inp not in ("{}", "null"):
                    for line in inp.splitlines():
                        lines.append(f"        {line}")
        else:
            lines.append("  (geen tools aangeroepen — direct berekend)")

        lines += ["", "STAP 3 — TOOL UITVOER"]

        if tool_calls:
            for i, call in enumerate(tool_calls, 1):
                output = call.get("output", "")
                if len(output) > _MAX_CHARS:
                    output = output[:_MAX_CHARS] + "\n        ... [ingekort]"
                lines.append(f"  [{i}]  {call['name']}")
                for line in output.splitlines():
                    lines.append(f"        {line}")
        else:
            lines.append("  (geen tool-uitvoer)")

        lines += ["", "STAP 4 — LLM ANTWOORD"]
        for line in answer.splitlines():
            lines.append(f"  {line}")
        if duration_ms:
            lines += ["", f"  Duur: {duration_ms:.0f} ms"]

        lines += ["", "=" * 80, ""]

        with self._path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

    @property
    def path(self) -> Path:
        return self._path
