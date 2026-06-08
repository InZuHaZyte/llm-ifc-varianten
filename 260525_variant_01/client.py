from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
import sys
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ollama import ChatOllama

from config import client_settings, setup_logging
from session_log import SessionLogger


SERVER_PATH = Path(__file__).resolve().parent / "server.py"
logger = setup_logging("variant_01_client")


SYSTEM_PROMPT = """
Je bent een IFC-onderzoeksassistent. Gebruik uitsluitend de beschikbare MCP-tools
voor feiten over het model. Variant 01 heeft vaste tools: kies de meest passende
vaste tool en geef compact antwoord in het Nederlands.
""".strip()


def build_mcp_client(ifc_path: str) -> MultiServerMCPClient:
    return MultiServerMCPClient(
        {
            "ifc_variant_01": {
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


async def ask_once(args: argparse.Namespace, session: SessionLogger) -> None:
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
    print(f"IFC Variant 01 — typ 'exit' om te stoppen.")
    print(f"Sessie-log: {session.path.name}\n")
    while True:
        question = input("> ").strip()
        if question.casefold() in {"exit", "quit", "stop"}:
            return
        if not question:
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
    session = SessionLogger("variant_01")
    logger.info("Starting LangChain client model=%s ollama_url=%s", args.model, args.ollama_url)
    if args.question:
        asyncio.run(ask_once(args, session))
    else:
        asyncio.run(chat(args, session))


if __name__ == "__main__":
    main()
