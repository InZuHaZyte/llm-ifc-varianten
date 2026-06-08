"""
GraphRAG voor IFC-modellen
Gebruik:
  python app.py load   --ifc "C:\IFC_modellen\Schependomlaan\IFC Schependomlaan.ifc" --clear
  python app.py query  "Welke ruimtes zijn er op verdieping 2?"
  python app.py shell  (interactieve modus — ook standaard zonder subcommando)
  python app.py schema (toon Neo4j-schema)

Neo4j Browser:  http://localhost:7474
Ollama API:     zie .env (OLLAMA_BASE_URL)
"""
import argparse
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from config import get_config
from logging_config import setup_logging
from ifc.parser import IFCParser
from ifc.graph_builder import GraphBuilder
from graph.neo4j_client import Neo4jClient
from agents.graph_agent import GraphAgent
from session_log import SessionLogger

console = Console()


# ---------------------------------------------------------------------------
# Subcommand: load
# ---------------------------------------------------------------------------

def cmd_load(args, cfg, client: Neo4jClient):
    if args.clear:
        console.print("[yellow]Graph wordt geleegd...[/yellow]")
        client.clear_graph()

    client.setup_schema()

    parser = IFCParser(args.ifc)
    model = parser.parse()

    builder = GraphBuilder()
    data = builder.build(model)

    client.load_graph_data(data)

    # Overzichtstabel
    table = Table(title="IFC → Neo4j", box=box.ROUNDED)
    table.add_column("Type", style="cyan")
    table.add_column("Aantal", style="green", justify="right")
    for label, nodes in [
        ("Project", data.projects), ("Building", data.buildings),
        ("Storey", data.storeys), ("Space", data.spaces),
        ("Wall", data.walls), ("Door", data.doors), ("Window", data.windows),
    ]:
        table.add_row(label, str(len(nodes)))
    table.add_row("Relaties", str(len(data.relationships)), end_section=True)
    console.print(table)
    console.print(
        Panel(
            "[bold]Neo4j Browser:[/bold] http://localhost:7474\n"
            "Voer in de browser uit:\n"
            "  MATCH p=(:Project)-[:CONTAINS*]->() RETURN p LIMIT 100",
            title="Visualisatie",
            style="blue",
        )
    )


# ---------------------------------------------------------------------------
# Subcommand: query
# ---------------------------------------------------------------------------

def cmd_query(args, cfg, client: Neo4jClient, session: SessionLogger):
    agent = GraphAgent(cfg, client)
    result = agent.run(args.question)
    _print_result(result)
    session.log(result)


# ---------------------------------------------------------------------------
# Subcommand: shell (interactieve modus)
# ---------------------------------------------------------------------------

def cmd_shell(cfg, client: Neo4jClient, session: SessionLogger):
    agent = GraphAgent(cfg, client)
    console.print(Panel(
        f"GraphRAG IFC — interactieve modus\n"
        f"Typ [bold]exit[/bold] of [bold]quit[/bold] om te stoppen.\n"
        f"[dim]Sessie-log: {session.path.name}[/dim]",
        style="green",
    ))
    while True:
        try:
            question = console.input("[bold cyan]Vraag:[/bold cyan] ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if not question:
            continue
        if question.lower() in ("exit", "quit", "stop"):
            break
        result = agent.run(question)
        _print_result(result)
        session.log(result)


# ---------------------------------------------------------------------------
# Subcommand: schema
# ---------------------------------------------------------------------------

def cmd_schema(client: Neo4jClient):
    summary = client.get_schema_summary()
    console.print(Panel(summary, title="Neo4j Schema", style="magenta"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_result(result):
    if result.discovery_cypher:
        console.print(Panel(
            result.discovery_cypher,
            title="[1/2] Discovery Cypher",
            style="dim cyan",
        ))
        if result.discovery_results:
            from rich.table import Table
            tbl = Table(box=box.SIMPLE, show_header=True, header_style="cyan")
            if result.discovery_results:
                for col in result.discovery_results[0].keys():
                    tbl.add_column(col)
                for row in result.discovery_results[:20]:  # max 20 tonen
                    tbl.add_row(*[str(v) for v in row.values()])
            console.print(tbl)

    console.print(Panel(result.cypher, title="[2/2] Hoofd-Cypher", style="yellow"))
    console.print(Panel(result.answer, title="Antwoord", style="green"))
    console.print(
        f"[dim]Latency: totaal={result.latency_total_ms:.0f}ms | "
        f"discovery+cypher={result.latency_cypher_ms:.0f}ms | "
        f"query={result.latency_query_ms:.0f}ms | "
        f"antwoord={result.latency_answer_ms:.0f}ms[/dim]"
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main():
    cfg = get_config()
    logger = setup_logging(cfg.log)

    parser = argparse.ArgumentParser(
        description="GraphRAG voor IFC-modellen",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # load
    p_load = sub.add_parser("load", help="IFC-bestand inladen in Neo4j")
    p_load.add_argument("--ifc", required=True, help="Pad naar .ifc-bestand")
    p_load.add_argument("--clear", action="store_true", help="Wis bestaande graph eerst")

    # query
    p_query = sub.add_parser("query", help="Stel een vraag over het model")
    p_query.add_argument("question", help="Vraag in natuurlijke taal")

    # shell
    sub.add_parser("shell", help="Interactieve modus")

    # schema
    sub.add_parser("schema", help="Toon het Neo4j-schema")

    args = parser.parse_args()

    # Standaard shell-modus wanneer geen subcommando opgegeven
    if not args.command:
        args.command = "shell"

    session = SessionLogger()

    try:
        with Neo4jClient(cfg.neo4j.uri, cfg.neo4j.user, cfg.neo4j.password) as client:
            if args.command == "load":
                cmd_load(args, cfg, client)
            elif args.command == "query":
                cmd_query(args, cfg, client, session)
            elif args.command == "shell":
                cmd_shell(cfg, client, session)
            elif args.command == "schema":
                cmd_schema(client)
    except Exception as exc:
        logger.exception("Onverwachte fout")
        console.print(f"[bold red]Fout:[/bold red] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
