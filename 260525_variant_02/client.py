from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
import re
import sys
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ollama import ChatOllama

from config import client_settings, setup_logging
from ifc_model import IfcModel
from session_log import SessionLogger


SERVER_PATH = Path(__file__).resolve().parent / "server.py"
logger = setup_logging("variant_02_client")


SYSTEM_PROMPT = """
Je bent een IFC-onderzoeksassistent. Gebruik uitsluitend de beschikbare MCP-tools
voor feiten over het model.

REGELS — VERPLICHT:
- Roep altijd eerst een tool aan. Reageer NOOIT met tekst voordat je de benodigde tools hebt uitgevoerd.
- Schrijf NOOIT "Ik zal...", "Laten we...", "Ik ga nu..." — doe het gewoon.
- Na een tool-resultaat: als je nog meer data nodig hebt, roep dan DIRECT de volgende tool aan.
- Pas als alle tools klaar zijn, geef je een beknopt antwoord aan de gebruiker.
- Geef NOOIT een antwoord op basis van aannames — gebruik altijd tool-data.
- Als een tool-resultaat een "filter_warnings" veld bevat: STOP, voer de tool opnieuw uit
  met het ontbrekende filter toegevoegd. Geef NOOIT een antwoord op basis van een query
  waarbij een inhoudelijk filter ontbrak.
- Leid NOOIT zelf af hoeveel elementen een eigenschap hebben vanuit een ongefilterde lijst.
  Ongeldige redenering: "Er zijn 268 wanden; hiervan zijn er 41 dragend."
  Geldige aanpak: filters={"LoadBearing": true} toevoegen en opnieuw aggregeren.

Werkwijze — volg altijd deze volgorde:
1. Begin met get_model_summary voor een algemeen overzicht.
2. Gebruik describe_entity_type om te ontdekken welke eigenschappen beschikbaar zijn.
3. Gebruik get_available_values om exacte waarden op te halen voordat je filters toepast.
4. Gebruik EERST aggregate_elements als de vraag gaat over "hoeveel", "welke types",
   "per verdieping", "per type", of als er veel elementen verwacht worden.
   Gebruik group_by=["name","type_name"] voor uitsplitsingen per naam én type tegelijk.
5. Gebruik query_elements ALLEEN als je een lijst van individuele elementen met GUIDs nodig hebt.
   Gebruik query_elements NIET voor tellingen — gebruik dan aggregate_elements.
6. Gebruik get_element_details of get_property_sets voor details van één specifiek element.
7. Gebruik get_related_elements voor relaties tussen elementen.
8. Gebruik search_elements voor vrije tekstzoekopdrachten.

Antwoordformaat bij aantallen/uitsplitsingen:
- Bereken het totaal als de som van ALLE groepswaarden uit de tool-output.
- Toon ALLE groepen uit de tool-output — laat er nooit een weg, ook niet kleine aantallen.
- Laat groepen alleen weg als de gebruiker expliciet vraagt om top-N of een samenvatting.
- Structuur (geldt voor elk entiteitstype — wanden, ramen, deuren, slabs, etc.):
  "Er zijn [totaal] [entiteiten] [context]:
  - [type/naam uit tool-output]: [aantal]
  - ...
  [optioneel: Voorbeelden met GUID]"

Domeincontrole — voeg een waarschuwing toe bij bouwkundig onwaarschijnlijke combinaties:
- Controleer of type-naam en eigenschappen logisch bij elkaar passen, ongeacht het entiteitstype.
- Voorbeelden van verdachte combinaties (niet uitputtend — gebruik ook eigen domeinkennis):
  * Isolatie- of afwerkingsmateriaal + LoadBearing=true
  * Niet-constructief element (raam, deur, ruimte) + LoadBearing=true
  * Transparant/glas element + IsExternal=false op een buitengevel
- Toon eerst altijd de volledige feitelijke data, daarna pas de waarschuwing.
- Formuleer de waarschuwing als: "Waarschuwing: het type '[naam]' is als [eigenschap] gemarkeerd.
  Dit lijkt bouwkundig ongebruikelijk omdat [reden]. Controle van de modeldata wordt aanbevolen."

Interpreteer BVO/bruto vloeroppervlakte als IfcSpace GrossFloorArea en
NVO/netto vloeroppervlakte als IfcSpace NetFloorArea, tenzij de gebruiker iets
anders specificeert. Als de gebruiker "vloeroppervlak" zonder verdere specificatie
vraagt, gebruik dan IfcSpace GrossFloorArea.
""".strip()


def build_mcp_client(ifc_path: str) -> MultiServerMCPClient:
    return MultiServerMCPClient(
        {
            "ifc_variant_02": {
                "transport": "stdio",
                "command": sys.executable,
                "args": [str(SERVER_PATH), "--ifc", ifc_path],
            }
        }
    )


def build_agent(tools: list[Any], model_name: str, ollama_url: str) -> Any:
    model = ChatOllama(
        model=model_name,
        base_url=ollama_url,
        temperature=0,
    )
    for tool in tools:
        tool.handle_tool_error = True
    return create_agent(model=model, tools=tools, system_prompt=SYSTEM_PROMPT)


def last_message_text(result: dict[str, Any]) -> str:
    messages = result.get("messages", [])
    if not messages:
        return ""
    content = messages[-1].content
    if isinstance(content, list):
        return "\n".join(str(part.get("text", part)) for part in content)
    return str(content)


def extract_tool_calls(messages: list) -> list[dict]:
    """Haal tool-aanroepen en -uitvoer op uit LangChain-berichten."""
    tool_calls: list[dict] = []
    pending: dict[str, tuple[str, str]] = {}

    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tc_id = tc.get("id", "")
                name = tc.get("name", "unknown")
                args = tc.get("args", {})
                inp = json.dumps(args, ensure_ascii=False) if args else "{}"
                pending[tc_id] = (name, inp)
        elif isinstance(msg, ToolMessage):
            tc_id = getattr(msg, "tool_call_id", "")
            if tc_id in pending:
                name, inp = pending.pop(tc_id)
                tool_calls.append({"name": name, "input": inp, "output": str(msg.content)})

    return tool_calls


def normalized_words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.casefold()))


def storey_display_name(storey: str) -> str:
    return re.sub(r"^\s*[-\d.]+\s*", "", storey).strip() or storey


def matching_storey(question: str, storeys: list[str]) -> str | None:
    question_text = question.casefold()
    question_words = normalized_words(question)
    best: tuple[int, str] | None = None
    for storey in storeys:
        label = storey_display_name(storey).casefold()
        if label and label in question_text:
            score = len(normalized_words(label))
        else:
            words = normalized_words(label)
            score = len(words & question_words)
            if score == 0:
                continue
        if best is None or score > best[0]:
            best = (score, storey)
    return best[1] if best else None


def format_m2(value: float) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def try_answer_area_question(question: str, ifc_path: str) -> str | None:
    lowered = question.casefold()
    if not any(token in lowered for token in ("vloeroppervlak", "vloeroppervlakte", "bvo", "nvo", "bruto vloer", "netto vloer")):
        return None

    property_name = "NetFloorArea" if any(token in lowered for token in ("nvo", "netto")) else "GrossFloorArea"
    area_label = "netto vloeroppervlakte" if property_name == "NetFloorArea" else "bruto vloeroppervlakte"

    model = IfcModel(ifc_path)
    storeys = model.available_values("Storey", "name")
    storey = matching_storey(question, storeys)
    result = model.sum_numeric_property("Space", property_name, storey=storey)
    total = float(result["total"])

    if storey:
        label = storey_display_name(storey)
        return f"De {area_label} van de {label} ({storey}) is {format_m2(total)} m²."
    return f"De totale {area_label} van het gebouw is {format_m2(total)} m²."


async def ask_once(args: argparse.Namespace, session: SessionLogger) -> None:
    t0 = time.perf_counter()
    direct_answer = try_answer_area_question(args.question, args.ifc)
    if direct_answer:
        duration_ms = (time.perf_counter() - t0) * 1000
        print(direct_answer)
        session.log(args.question, [], direct_answer, duration_ms)
        return

    client = build_mcp_client(args.ifc)
    tools = await client.get_tools()
    agent = build_agent(tools, args.model, args.ollama_url)

    t0 = time.perf_counter()
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": args.question}]}
    )
    duration_ms = (time.perf_counter() - t0) * 1000

    messages = result.get("messages", [])
    tool_calls = extract_tool_calls(messages)
    answer = last_message_text(result)

    if tool_calls:
        print(f"[Tools: {', '.join(c['name'] for c in tool_calls)}]")
    print(answer)

    session.log(args.question, tool_calls, answer, duration_ms)
    logger.info("Sessie-log: %s", session.path)


async def chat(args: argparse.Namespace, session: SessionLogger) -> None:
    client = build_mcp_client(args.ifc)
    tools = await client.get_tools()
    agent = build_agent(tools, args.model, args.ollama_url)
    messages: list = []
    print(f"IFC Variant 02 — typ 'exit' om te stoppen.")
    print(f"Sessie-log: {session.path.name}\n")
    while True:
        question = input("> ").strip()
        if question.casefold() in {"exit", "quit", "stop"}:
            return
        if not question:
            continue

        t0 = time.perf_counter()
        direct_answer = try_answer_area_question(question, args.ifc)
        if direct_answer:
            duration_ms = (time.perf_counter() - t0) * 1000
            print(direct_answer)
            print()
            messages.append({"role": "assistant", "content": direct_answer})
            session.log(question, [], direct_answer, duration_ms)
            continue

        prev_len = len(messages)
        messages.append({"role": "user", "content": question})

        t0 = time.perf_counter()
        result = await agent.ainvoke({"messages": messages})
        duration_ms = (time.perf_counter() - t0) * 1000

        messages = result["messages"]
        new_messages = messages[prev_len:]
        tool_calls = extract_tool_calls(new_messages)
        answer = last_message_text(result)

        if tool_calls:
            print(f"[Tools: {', '.join(c['name'] for c in tool_calls)}]")
        print(answer)
        print()

        session.log(question, tool_calls, answer, duration_ms)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ifc", help="Pad naar het IFC-model")
    parser.add_argument("--model", help="Ollama modelnaam")
    parser.add_argument("--ollama-url")
    parser.add_argument("--question", help="Eenmalige vraag. Zonder deze optie start chatmodus.")
    args = parser.parse_args()
    settings = client_settings(args.ifc, args.model, args.ollama_url)
    args.ifc = str(settings.ifc_path)
    args.model = settings.model
    args.ollama_url = settings.ollama_url
    return args


def main() -> None:
    args = parse_args()
    session = SessionLogger("variant_02")
    logger.info("Starting LangChain client model=%s ollama_url=%s", args.model, args.ollama_url)
    if args.question:
        asyncio.run(ask_once(args, session))
    else:
        asyncio.run(chat(args, session))


if __name__ == "__main__":
    main()
