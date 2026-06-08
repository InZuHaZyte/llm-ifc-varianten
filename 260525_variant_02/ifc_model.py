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
    "Slab": ("IfcSlab",),
    "Column": ("IfcColumn",),
    "Beam": ("IfcBeam",),
    "Roof": ("IfcRoof",),
    "Stair": ("IfcStair",),
    "Opening": ("IfcOpeningElement",),
}

PROPERTY_ALIASES = {
    "name": "name",
    "type_name": "type_name",
    "storey": "storey",
    "guid": "guid",
    "ifc_class": "ifc_class",
    "load_bearing": "load_bearing",
    "is_external": "is_external",
    "fire_rating": "fire_rating",
    "bvo": "GrossFloorArea",
    "gross_floor_area": "GrossFloorArea",
    "grossfloorarea": "GrossFloorArea",
    "bruto_vloeroppervlakte": "GrossFloorArea",
    "net_floor_area": "NetFloorArea",
    "netfloorarea": "NetFloorArea",
    "nvo": "NetFloorArea",
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


def _norm(value: Any) -> str:
    return str(value).strip().casefold()


def _property_key(value: Any) -> str:
    return "".join(ch for ch in str(value).casefold() if ch.isalnum())


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().casefold() in {"true", "yes", "ja", "1", ".t.", "t"}
    return bool(value)


class IfcModel:
    def __init__(self, path: str) -> None:
        self.path = Path(path).expanduser().resolve()
        if not self.path.exists():
            raise FileNotFoundError(f"IFC-bestand niet gevonden: {self.path}")
        ifcopenshell, element_util = _load_ifcopenshell()
        self._element_util = element_util
        self.model = ifcopenshell.open(str(self.path))

    def entity_classes(self, entity_type: str) -> tuple[str, ...]:
        if entity_type in ENTITY_CLASSES:
            return ENTITY_CLASSES[entity_type]
        if entity_type.startswith("Ifc"):
            return (entity_type,)
        raise ValueError(
            f"Onbekend entity_type '{entity_type}'. Gebruik een van: {sorted(ENTITY_CLASSES)} of een IfcClass."
        )

    def elements(self, entity_type: str) -> list[Any]:
        seen: dict[int, Any] = {}
        for class_name in self.entity_classes(entity_type):
            for element in self.model.by_type(class_name):
                seen[element.id()] = element
        return list(seen.values())

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
        try:
            for inverse in self.model.get_inverse(element):
                if inverse.is_a("IfcRelAggregates"):
                    parent = getattr(inverse, "RelatingObject", None)
                    if parent and parent.is_a("IfcBuildingStorey"):
                        return self.name(parent)
                elif inverse.is_a("IfcRelContainedInSpatialStructure"):
                    parent = getattr(inverse, "RelatingStructure", None)
                    while parent is not None:
                        if parent.is_a("IfcBuildingStorey"):
                            return self.name(parent)
                        parent = self._element_util.get_container(parent)
        except Exception:
            pass
        return None

    def property_sets(self, element: Any) -> dict[str, Any]:
        try:
            return self._element_util.get_psets(element) or {}
        except Exception:
            return {}

    def flat_properties(self, element: Any) -> dict[str, Any]:
        values = {
            "id": element.id(),
            "guid": self.guid(element),
            "name": self.name(element),
            "ifc_class": element.is_a(),
            "type_name": self.type_name(element),
            "storey": self.storey(element),
        }
        for pset_values in self.property_sets(element).values():
            if isinstance(pset_values, dict):
                for key, value in pset_values.items():
                    values.setdefault(key, value)
                    values.setdefault(key.casefold(), value)
                    values.setdefault(_property_key(key), value)
        return values

    def property_value(self, element: Any, property_name: str) -> Any:
        key = PROPERTY_ALIASES.get(property_name, property_name)
        props = self.flat_properties(element)
        return props.get(key, props.get(key.casefold(), props.get(_property_key(key))))

    def item(self, element: Any, include_properties: bool = False) -> dict[str, Any]:
        data = {
            "id": element.id(),
            "guid": self.guid(element),
            "name": self.name(element),
            "ifc_class": element.is_a(),
            "type_name": self.type_name(element),
            "storey": self.storey(element),
        }
        if include_properties:
            data["properties"] = self.flat_properties(element)
        return data

    def find_element(self, identifier: str) -> Any | None:
        text = _norm(identifier)
        for element in self.model:
            guid = getattr(element, "GlobalId", None)
            name = getattr(element, "Name", None)
            if _norm(element.id()) == text or (guid and _norm(guid) == text) or (name and _norm(name) == text):
                return element
        return None

    def find_elements(self, identifiers: list[Any]) -> list[Any]:
        elements = []
        for identifier in identifiers:
            if isinstance(identifier, dict):
                identifier = identifier.get("id") or identifier.get("guid") or identifier.get("name")
            element = self.find_element(str(identifier))
            if element is not None:
                elements.append(element)
        return elements

    def get_model_summary(self) -> dict[str, Any]:
        counts = {key: len(self.elements(key)) for key in ENTITY_CLASSES}
        return {
            "file": str(self.path),
            "schema": getattr(self.model, "schema", None),
            "counts": counts,
            "storeys": self.available_values("Storey", "name"),
            "supported_entity_types": sorted(ENTITY_CLASSES),
        }

    def available_values(self, entity_type: str, property_name: str) -> list[Any]:
        key = PROPERTY_ALIASES.get(property_name, property_name)
        values = set()
        for element in self.elements(entity_type):
            value = self.property_value(element, key)
            if value not in (None, "") and not isinstance(value, dict):
                values.add(value)
        return sorted(values, key=lambda item: str(item))

    def available_values_by_entity(self, property_name: str) -> dict[str, list[Any]]:
        values = {}
        for entity_type in sorted(ENTITY_CLASSES):
            entity_values = self.available_values(entity_type, property_name)
            if entity_values:
                values[entity_type] = entity_values
        return values

    def matches_filters(self, element: Any, filters: dict[str, Any] | None) -> bool:
        if not filters:
            return True
        for key, expected in filters.items():
            actual = self.property_value(element, key)
            if isinstance(expected, bool):
                if _boolish(actual) != expected:
                    return False
            elif actual is None or _norm(actual) != _norm(expected):
                return False
        return True

    def matches_storey(self, element: Any, storey: str | None) -> bool:
        if not storey:
            return True
        actual = self.storey(element)
        if actual is None:
            return False
        expected_text = _norm(storey)
        actual_text = _norm(actual)
        return expected_text == actual_text or expected_text in actual_text or actual_text in expected_text

    def query_elements(
        self,
        entity_type: str,
        storey: str | None = None,
        type_name: str | None = None,
        name_contains: str | None = None,
        property_filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        result = []
        for element in self.elements(entity_type):
            if not self.matches_storey(element, storey):
                continue
            if type_name and _norm(self.type_name(element)) != _norm(type_name):
                continue
            if name_contains and _norm(name_contains) not in _norm(self.name(element)):
                continue
            if not self.matches_filters(element, property_filters):
                continue
            result.append(self.item(element))
        return result

    def count_elements(
        self,
        entity_type: str,
        storey: str | None = None,
        type_name: str | None = None,
        property_filters: dict[str, Any] | None = None,
        group_by: str | None = None,
    ) -> int | dict[str, int]:
        matching = []
        for element in self.elements(entity_type):
            if not self.matches_storey(element, storey):
                continue
            if type_name and _norm(self.type_name(element)) != _norm(type_name):
                continue
            if not self.matches_filters(element, property_filters):
                continue
            matching.append(element)
        if not group_by:
            return len(matching)
        grouped: Counter[str] = Counter()
        group_key = PROPERTY_ALIASES.get(group_by, group_by)
        for element in matching:
            value = self.property_value(element, group_key)
            grouped[str(value or "Onbekend")] += 1
        return dict(sorted(grouped.items()))

    def sum_numeric_property(
        self,
        entity_type: str,
        property_name: str,
        storey: str | None = None,
        type_name: str | None = None,
        property_filters: dict[str, Any] | None = None,
        group_by: str | None = None,
    ) -> dict[str, Any]:
        property_key = PROPERTY_ALIASES.get(property_name, property_name)
        group_key = PROPERTY_ALIASES.get(group_by, group_by) if group_by else None
        total = 0.0
        counted = 0
        skipped = 0
        groups: dict[str, dict[str, Any]] = defaultdict(lambda: {"total": 0.0, "count": 0})

        for element in self.elements(entity_type):
            if not self.matches_storey(element, storey):
                continue
            if type_name and _norm(self.type_name(element)) != _norm(type_name):
                continue
            if not self.matches_filters(element, property_filters):
                continue

            raw_value = self.property_value(element, property_key)
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                skipped += 1
                continue

            total += value
            counted += 1
            if group_key:
                group_value = self.property_value(element, group_key)
                label = str(group_value or "Onbekend")
                groups[label]["total"] += value
                groups[label]["count"] += 1

        result: dict[str, Any] = {
            "entity_type": entity_type,
            "property_name": property_key,
            "total": total,
            "counted_elements": counted,
            "skipped_elements": skipped,
        }
        if group_key:
            result["group_by"] = group_key
            result["groups"] = dict(sorted(groups.items()))
        return result

    def sum_numeric_property_for_elements(
        self,
        identifiers: list[Any],
        property_name: str,
        entity_type: str | None = None,
    ) -> dict[str, Any]:
        property_key = PROPERTY_ALIASES.get(property_name, property_name)
        total = 0.0
        counted = 0
        skipped = 0
        elements = self.find_elements(identifiers)
        for element in elements:
            if entity_type and not any(element.is_a(cls) for cls in self.entity_classes(entity_type)):
                skipped += 1
                continue
            raw_value = self.property_value(element, property_key)
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                skipped += 1
                continue
            total += value
            counted += 1
        return {
            "entity_type": entity_type,
            "property_name": property_key,
            "total": total,
            "counted_elements": counted,
            "skipped_elements": skipped,
            "requested_elements": len(identifiers),
            "found_elements": len(elements),
        }

    def details(
        self,
        identifier: str,
        include_properties: bool = True,
        include_psets: bool = True,
        include_relationships: bool = True,
    ) -> dict[str, Any]:
        element = self.find_element(identifier)
        if not element:
            raise ValueError(f"Element niet gevonden: {identifier}")
        data = self.item(element, include_properties=include_properties)
        if include_psets:
            data["property_sets"] = self.property_sets(element)
        if include_relationships:
            data["relationships"] = self.relationship_summary(element)
        return data

    def get_property_sets(self, identifier: str, pset_name: str | None = None) -> dict[str, Any]:
        element = self.find_element(identifier)
        if not element:
            raise ValueError(f"Element niet gevonden: {identifier}")
        psets = self.property_sets(element)
        if pset_name:
            return {pset_name: psets.get(pset_name, {})}
        return psets

    def relationship_summary(self, element: Any) -> dict[str, Any]:
        summary: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for inverse in self.model.get_inverse(element):
            if inverse.is_a("IfcRelContainedInSpatialStructure"):
                container = getattr(inverse, "RelatingStructure", None)
                if container:
                    summary["contained_in"].append(self.item(container))
            elif inverse.is_a("IfcRelSpaceBoundary"):
                space = getattr(inverse, "RelatingSpace", None)
                building_element = getattr(inverse, "RelatedBuildingElement", None)
                if space and space != element:
                    summary["bounds_space"].append(self.item(space))
                if building_element and building_element != element:
                    summary["bounded_by"].append(self.item(building_element))
            elif inverse.is_a("IfcRelFillsElement"):
                opening = getattr(inverse, "RelatingOpeningElement", None)
                if opening:
                    summary["fills_opening"].append(self.item(opening))
            elif inverse.is_a("IfcRelVoidsElement"):
                host = getattr(inverse, "RelatingBuildingElement", None)
                opening = getattr(inverse, "RelatedOpeningElement", None)
                if host and host != element:
                    summary["voids_host"].append(self.item(host))
                if opening and opening != element:
                    summary["has_opening"].append(self.item(opening))
        return dict(summary)

    def related_elements(
        self,
        source_entity_type: str,
        source_identifier: str,
        relation: str,
        target_entity_type: str | None = None,
        direction: str = "both",
    ) -> list[dict[str, Any]]:
        source = self.find_element(source_identifier)
        if not source:
            candidates = self.query_elements(source_entity_type, name_contains=source_identifier)
            if not candidates:
                raise ValueError(f"Bron niet gevonden: {source_identifier}")
            source = self.find_element(str(candidates[0]["id"]))

        relation_key = relation.upper()
        related: list[Any] = []

        if relation_key == "CONTAINS":
            if source.is_a("IfcSpatialStructureElement") or source.is_a("IfcBuildingStorey"):
                for inverse in self.model.get_inverse(source):
                    if inverse.is_a("IfcRelContainedInSpatialStructure"):
                        related.extend(getattr(inverse, "RelatedElements", []) or [])
            else:
                container = self._element_util.get_container(source)
                if container:
                    related.append(container)

        elif relation_key in {"BOUNDS_SPACE", "BOUNDED_BY"}:
            for rel in self.model.by_type("IfcRelSpaceBoundary"):
                space = getattr(rel, "RelatingSpace", None)
                element = getattr(rel, "RelatedBuildingElement", None)
                if source == space and element:
                    related.append(element)
                elif source == element and space:
                    related.append(space)

        elif relation_key in {"FILLS_OPENING", "FILLED_BY"}:
            if source.is_a("IfcOpeningElement"):
                for inverse in self.model.get_inverse(source):
                    if inverse.is_a("IfcRelFillsElement"):
                        element = getattr(inverse, "RelatedBuildingElement", None)
                        if element:
                            related.append(element)
            else:
                for inverse in self.model.get_inverse(source):
                    if inverse.is_a("IfcRelFillsElement"):
                        opening = getattr(inverse, "RelatingOpeningElement", None)
                        if opening:
                            related.append(opening)
                            for rel in self.model.get_inverse(opening):
                                if rel.is_a("IfcRelVoidsElement"):
                                    host = getattr(rel, "RelatingBuildingElement", None)
                                    if host:
                                        related.append(host)

        elif relation_key in {"HOSTS_OPENING", "VOIDS"}:
            for inverse in self.model.get_inverse(source):
                if inverse.is_a("IfcRelVoidsElement"):
                    opening = getattr(inverse, "RelatedOpeningElement", None)
                    if opening:
                        related.append(opening)

        else:
            raise ValueError("Ondersteunde relaties: CONTAINS, BOUNDS_SPACE, FILLS_OPENING, HOSTS_OPENING")

        if direction not in {"both", "out", "in"}:
            raise ValueError("direction moet 'both', 'out' of 'in' zijn.")

        seen: dict[int, Any] = {}
        for element in related:
            if target_entity_type and not any(element.is_a(cls) for cls in self.entity_classes(target_entity_type)):
                continue
            seen[element.id()] = element
        return [self.item(element) for element in seen.values()]

    def search(self, query: str, entity_types: list[str] | None = None, properties: list[str] | None = None, limit: int = 25) -> list[dict[str, Any]]:
        needles = [_norm(part) for part in query.split() if part.strip()]
        types = entity_types or sorted(ENTITY_CLASSES)
        hits = []
        for entity_type in types:
            for element in self.elements(entity_type):
                props = self.flat_properties(element)
                fields = properties or ["name", "type_name", "storey", "guid"]
                haystack_parts = [str(props.get(field, "")) for field in fields]
                if not properties:
                    for key, value in props.items():
                        if not isinstance(value, dict):
                            haystack_parts.append(f"{key} {value}")
                haystack = _norm(" ".join(haystack_parts))
                score = sum(1 for needle in needles if needle in haystack)
                if score:
                    row = self.item(element)
                    row["score"] = score
                    hits.append(row)
        hits.sort(key=lambda row: row["score"], reverse=True)
        return hits[: max(1, min(limit, 100))]
