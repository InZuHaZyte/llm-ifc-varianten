from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import logging
import os


BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
DEFAULT_MODEL = "mistral-small"
DEFAULT_OLLAMA_URL = "http://localhost:11434"


def load_dotenv(path: Path | None = None) -> None:
    env_path = path or BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


def is_placeholder_path(value: str) -> bool:
    normalized = value.replace("/", "\\").casefold()
    return normalized in {
        r"c:\pad\naar\model.ifc",
        r"c:\path\to\model.ifc",
    }


def first_ifc_file() -> Path | None:
    for root in (BASE_DIR / "models", BASE_DIR / "data", BASE_DIR, Path.cwd()):
        if root.exists():
            found = sorted(root.glob("*.ifc"))
            if found:
                return found[0]
    return None


def resolve_ifc_path(path: str | None = None) -> Path:
    load_dotenv()
    candidate = path or os.getenv("IFC_MODEL_PATH")
    if candidate:
        if is_placeholder_path(candidate):
            raise FileNotFoundError(
                "IFC_MODEL_PATH bevat nog de voorbeeldwaarde. Pas .env aan naar het echte IFC-pad."
            )
        resolved = Path(candidate).expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(
                f"IFC-bestand niet gevonden: {resolved}\n"
                "Controleer IFC_MODEL_PATH in .env. Let op: Windows gebruikt '\\' als mapscheiding."
            )
        return resolved
    discovered = first_ifc_file()
    if discovered:
        return discovered.resolve()
    raise FileNotFoundError(
        "Geen IFC-bestand gevonden. Geef --ifc mee of zet IFC_MODEL_PATH in .env."
    )


def setup_logging(name: str) -> logging.Logger:
    load_dotenv()
    LOG_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    logger.propagate = False
    if not logger.handlers:
        handler = logging.FileHandler(LOG_DIR / f"{name}.log", encoding="utf-8")
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


@dataclass(frozen=True)
class ServerSettings:
    ifc_path: Path
    transport: str
    host: str
    port: int


@dataclass(frozen=True)
class ClientSettings:
    ifc_path: Path
    model: str
    ollama_url: str


def server_settings(
    ifc: str | None,
    transport: str,
    host: str,
    port: int,
) -> ServerSettings:
    load_dotenv()
    return ServerSettings(
        ifc_path=resolve_ifc_path(ifc),
        transport=transport,
        host=os.getenv("MCP_HOST", host),
        port=int(os.getenv("MCP_PORT", str(port))),
    )


def client_settings(
    ifc: str | None,
    model: str | None,
    ollama_url: str | None,
) -> ClientSettings:
    load_dotenv()
    return ClientSettings(
        ifc_path=resolve_ifc_path(ifc),
        model=model or os.getenv("OLLAMA_MODEL", DEFAULT_MODEL),
        ollama_url=ollama_url or os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL),
    )
