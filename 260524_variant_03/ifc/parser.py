import logging
from pathlib import Path

import ifcopenshell

logger = logging.getLogger(__name__)


class IFCParser:
    """Opent een IFC-bestand en geeft het IfcOpenShell-model terug."""

    def __init__(self, filepath: str | Path):
        self.filepath = Path(filepath)

    def parse(self) -> ifcopenshell.file:
        if not self.filepath.exists():
            raise FileNotFoundError(f"IFC-bestand niet gevonden: {self.filepath}")

        logger.info("IFC-bestand laden: %s", self.filepath)
        model = ifcopenshell.open(str(self.filepath))
        schema = model.schema
        logger.info("Schema: %s | Entiteiten: %d", schema, len(list(model)))
        return model
