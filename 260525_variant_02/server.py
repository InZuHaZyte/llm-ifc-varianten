from __future__ import annotations

import argparse

try:
    from fastmcp import FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP  # type: ignore

from config import server_settings, setup_logging
from ifc_model import IfcModel
from tools import register_tools


mcp = FastMCP("ifc-parameter-tools-variant-02")
logger = setup_logging("variant_02_server")
ifc: IfcModel | None = None


def get_model() -> IfcModel:
    if ifc is None:
        raise RuntimeError("IFC-model is nog niet geladen.")
    return ifc


register_tools(mcp, get_model, logger)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ifc", help="Pad naar het IFC-model")
    parser.add_argument("--transport", default="stdio", choices=["stdio", "sse", "streamable-http"])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8002)
    return parser.parse_args()


def main() -> None:
    global ifc
    args = parse_args()
    settings = server_settings(args.ifc, args.transport, args.host, args.port)
    ifc = IfcModel(str(settings.ifc_path))
    logger.info("Starting MCP server for IFC file: %s", settings.ifc_path)
    if settings.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport=settings.transport, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
