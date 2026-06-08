from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ENTITY_CLASSES = {
    "Wall": ("IfcWall", "IfcWallStandardCase"),
    "Window": ("IfcWindow",),
    "Door": ("IfcDoor",),
    "Space": ("IfcSpace",),
    "Storey": ("IfcBuildingStorey",),
}


def _load_ifcopenshell():
    try:
        import ifcopenshell  # type: ignore
        from ifcopenshell.util import element as element_util  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "IfcOpenShell is niet geinstalleerd. Installeer dependencies met: "
            "pip install -r requirements.txt"
        ) from exc
    return ifcopenshell, element_util


def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class IfcModel:
    def __init__(self, path: str) -> None:
        self.path = Path(path).expanduser().resolve()
        if not self.path.exists():
            raise FileNotFoundError(f"IFC-bestand niet gevonden: {self.path}")
        ifcopenshell, element_util = _load_ifcopenshell()
        self._element_util = element_util
        self.model = ifcopenshell.open(str(self.path))

    def elements(self, entity_type: str) -> list[Any]:
        classes = ENTITY_CLASSES[entity_type]
        seen: dict[int, Any] = {}
        for class_name in classes:
            for element in self.model.by_type(class_name):
                seen[element.id()] = element
        return list(seen.values())

    def count(self, entity_type: str) -> int:
        return len(self.elements(entity_type))

    def name(self, element: Any) -> str:
        return _string(getattr(element, "Name", None)) or _string(getattr(element, "GlobalId", None)) or str(element.id())

    def guid(self, element: Any) -> str | None:
        return _string(getattr(element, "GlobalId", None))

    def type_name(self, element: Any) -> str | None:
        try:
            element_type = self._element_util.get_type(element)
            if element_type:
                return _string(getattr(element_type, "Name", None))
        except Exception:
            pass
        return _string(getattr(element, "ObjectType", None))

    def storey(self, element: Any) -> str | None:
        try:
            container = self._element_util.get_container(element)
            while container is not None:
                if container.is_a("IfcBuildingStorey"):
                    return self.name(container)
                container = self._element_util.get_container(container)
        except Exception:
            pass
        return None

    def item(self, element: Any) -> dict[str, Any]:
        return {
            "id": element.id(),
            "guid": self.guid(element),
            "name": self.name(element),
            "ifc_class": element.is_a(),
            "type_name": self.type_name(element),
            "storey": self.storey(element),
        }

    def list_by_type(self, entity_type: str) -> list[dict[str, Any]]:
        return [self.item(element) for element in self.elements(entity_type)]

    def distinct_type_names(self, entity_type: str) -> list[str]:
        values = {self.type_name(element) for element in self.elements(entity_type)}
        return sorted(value for value in values if value)

    def count_by_storey(self, entity_type: str) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for element in self.elements(entity_type):
            counter[self.storey(element) or "Onbekende bouwlaag"] += 1
        return dict(sorted(counter.items()))

    def elements_on_storey(self, entity_type: str, storey_name: str) -> list[dict[str, Any]]:
        needle = storey_name.casefold()
        return [
            self.item(element)
            for element in self.elements(entity_type)
            if (self.storey(element) or "").casefold() == needle
        ]

    def elements_on_storey_alias(self, entity_type: str, aliases: tuple[str, ...]) -> list[dict[str, Any]]:
        alias_text = tuple(alias.casefold() for alias in aliases)
        result = []
        for element in self.elements(entity_type):
            storey = (self.storey(element) or "").casefold()
            if any(alias in storey for alias in alias_text):
                result.append(self.item(element))
        return result

    def project_summary(self) -> dict[str, Any]:
        projects = self.model.by_type("IfcProject")
        sites = self.model.by_type("IfcSite")
        buildings = self.model.by_type("IfcBuilding")
        return {
            "file": str(self.path),
            "schema": getattr(self.model, "schema", None),
            "project": self.name(projects[0]) if projects else None,
            "site": self.name(sites[0]) if sites else None,
            "building": self.name(buildings[0]) if buildings else None,
            "counts": {key: self.count(key) for key in ENTITY_CLASSES},
        }

    def model_statistics(self) -> dict[str, Any]:
        all_classes = Counter(element.is_a() for element in self.model)
        return {
            "total_entities": sum(all_classes.values()),
            "top_ifc_classes": dict(all_classes.most_common(25)),
            "storeys": [self.item(element) for element in self.elements("Storey")],
        }

    def available_categories(self) -> list[str]:
        return list(ENTITY_CLASSES.keys())

    def spaces_bounded_by_walls(self) -> list[dict[str, Any]]:
        rows = []
        for rel in self.model.by_type("IfcRelSpaceBoundary"):
            space = getattr(rel, "RelatingSpace", None)
            element = getattr(rel, "RelatedBuildingElement", None)
            if space and element and element.is_a() in ENTITY_CLASSES["Wall"]:
                rows.append({"space": self.item(space), "wall": self.item(element)})
        return rows

    def walls_bounding_spaces(self) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in self.spaces_bounded_by_walls():
            grouped[row["wall"]["guid"] or row["wall"]["name"]].append(row["space"])
        return dict(grouped)

    def filling_elements(self, entity_type: str) -> list[dict[str, Any]]:
        rows = []
        wanted = ENTITY_CLASSES[entity_type]
        for rel in self.model.by_type("IfcRelFillsElement"):
            element = getattr(rel, "RelatedBuildingElement", None)
            opening = getattr(rel, "RelatingOpeningElement", None)
            if not element or not opening or element.is_a() not in wanted:
                continue
            wall = None
            for inverse in self.model.get_inverse(opening):
                if inverse.is_a("IfcRelVoidsElement"):
                    wall = getattr(inverse, "RelatingBuildingElement", None)
                    break
            rows.append({"element": self.item(element), "wall": self.item(wall) if wall else None})
        return rows
