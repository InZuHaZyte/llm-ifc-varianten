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
    "Roof": ("IfcRoof",),
    "Stair": ("IfcStair",),
    "Covering": ("IfcCovering",),
    "Column": ("IfcColumn",),
    "Beam": ("IfcBeam",),
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

    # ------------------------------------------------------------------
    # Quantity helpers
    # ------------------------------------------------------------------

    def _get_quantity(self, element: Any, *lookup_paths: tuple[str, str]) -> float | None:
        """Zoek een numerieke hoeveelheid op in de quantity sets van een element.
        lookup_paths: tuples van (qto_naam, property_naam).
        """
        try:
            psets = self._element_util.get_psets(element, qtos_only=True)
            for qto_name, prop_name in lookup_paths:
                if qto_name in psets and prop_name in psets[qto_name]:
                    val = psets[qto_name][prop_name]
                    if val is not None:
                        return float(val)
        except Exception:
            pass
        return None

    def _element_statistics(
        self,
        entity_type: str,
        area_paths: list[tuple[str, str]],
    ) -> dict[str, Any]:
        """Genereer statistieken (aantal + oppervlakte) per verdieping en per type."""
        elements = self.elements(entity_type)
        total_area = 0.0
        any_area = False
        per_storey: dict[str, dict] = {}
        per_type: dict[str, dict] = {}

        for el in elements:
            storey_name = self.storey(el) or "Onbekende bouwlaag"
            type_label = self.type_name(el) or "Onbekend type"
            area = self._get_quantity(el, *area_paths)

            if area is not None:
                any_area = True
                total_area += area
            area_val = round(area, 2) if area is not None else 0.0

            if storey_name not in per_storey:
                per_storey[storey_name] = {"aantal": 0, "oppervlakte_m2": 0.0}
            per_storey[storey_name]["aantal"] += 1
            per_storey[storey_name]["oppervlakte_m2"] += area_val

            if type_label not in per_type:
                per_type[type_label] = {"aantal": 0, "oppervlakte_m2": 0.0}
            per_type[type_label]["aantal"] += 1
            per_type[type_label]["oppervlakte_m2"] += area_val

        for v in per_storey.values():
            v["oppervlakte_m2"] = round(v["oppervlakte_m2"], 2)
        for v in per_type.values():
            v["oppervlakte_m2"] = round(v["oppervlakte_m2"], 2)

        return {
            "eenheid": "m2",
            "heeft_oppervlaktedata": any_area,
            "totaal": {
                "aantal": len(elements),
                "oppervlakte_m2": round(total_area, 2),
            },
            "per_verdieping": dict(sorted(per_storey.items())),
            "per_type": dict(sorted(per_type.items())),
        }

    def wall_statistics(self) -> dict[str, Any]:
        return self._element_statistics("Wall", [
            ("Qto_WallBaseQuantities", "NetSideArea"),
            ("Qto_WallBaseQuantities", "GrossSideArea"),
            ("BaseQuantities", "NetSideArea"),
        ])

    def door_statistics(self) -> dict[str, Any]:
        return self._element_statistics("Door", [
            ("Qto_DoorBaseQuantities", "Area"),
            ("BaseQuantities", "Area"),
        ])

    def window_statistics(self) -> dict[str, Any]:
        return self._element_statistics("Window", [
            ("Qto_WindowBaseQuantities", "Area"),
            ("BaseQuantities", "Area"),
        ])

    def space_statistics(self) -> dict[str, Any]:
        """Ruimtestatistieken met zowel BVO (bruto) als NVO (netto) per verdieping."""
        elements = self.elements("Space")
        total_bvo = 0.0
        total_nvo = 0.0
        per_storey: dict[str, dict] = {}

        for el in elements:
            storey_name = self.storey(el) or "Onbekende bouwlaag"
            bvo = self._get_quantity(el,
                ("Qto_SpaceBaseQuantities", "GrossFloorArea"),
                ("BaseQuantities", "GrossFloorArea"),
            ) or 0.0
            nvo = self._get_quantity(el,
                ("Qto_SpaceBaseQuantities", "NetFloorArea"),
                ("BaseQuantities", "NetFloorArea"),
            ) or 0.0

            total_bvo += bvo
            total_nvo += nvo

            if storey_name not in per_storey:
                per_storey[storey_name] = {"aantal": 0, "bvo_m2": 0.0, "nvo_m2": 0.0}
            per_storey[storey_name]["aantal"] += 1
            per_storey[storey_name]["bvo_m2"] += bvo
            per_storey[storey_name]["nvo_m2"] += nvo

        for v in per_storey.values():
            v["bvo_m2"] = round(v["bvo_m2"], 2)
            v["nvo_m2"] = round(v["nvo_m2"], 2)

        return {
            "eenheid": "m2",
            "totaal": {
                "aantal": len(elements),
                "bvo_m2": round(total_bvo, 2),
                "nvo_m2": round(total_nvo, 2),
            },
            "per_verdieping": dict(sorted(per_storey.items())),
        }

    # ------------------------------------------------------------------
    # Overview methods (actieve tools)
    # ------------------------------------------------------------------

    def _storey_object(self, element: Any) -> Any | None:
        """Geeft het IfcBuildingStorey-object terug waar het element in zit."""
        try:
            container = self._element_util.get_container(element)
            while container is not None:
                if container.is_a("IfcBuildingStorey"):
                    return container
                container = self._element_util.get_container(container)
        except Exception:
            pass
        return None

    def _storey_element_overview(
        self,
        entity_type: str,
        quantity_paths: list[tuple[str, str]],
        quantity_key: str = "area_m2",
        unit: str = "m2",
    ) -> dict[str, Any]:
        """Genereer per verdieping: totaal aantal + hoeveelheid, uitgesplitst per type."""
        storey_data: dict[str, dict] = {}

        for el in self.elements(entity_type):
            storey_obj = self._storey_object(el)
            s_name = self.name(storey_obj) if storey_obj else "Onbekende bouwlaag"
            elevation = float(getattr(storey_obj, "Elevation", 0) or 0) if storey_obj else 0.0
            quantity = self._get_quantity(el, *quantity_paths) if quantity_paths else None
            quantity_val = round(quantity, 2) if quantity is not None else 0.0
            type_label = self.type_name(el) or "Onbekend type"

            if s_name not in storey_data:
                storey_data[s_name] = {
                    "storey_name": s_name,
                    "elevation": elevation,
                    "count": 0,
                    quantity_key: 0.0,
                    "by_type": {},
                }
            storey_data[s_name]["count"] += 1
            storey_data[s_name][quantity_key] += quantity_val

            bt = storey_data[s_name]["by_type"]
            if type_label not in bt:
                bt[type_label] = {"type": type_label, "count": 0, quantity_key: 0.0}
            bt[type_label]["count"] += 1
            bt[type_label][quantity_key] += quantity_val

        storeys = sorted(storey_data.values(), key=lambda x: x["elevation"])
        for s in storeys:
            s[quantity_key] = round(s[quantity_key], 2)
            s["by_type"] = sorted(
                ({"type": t["type"], "count": t["count"], quantity_key: round(t[quantity_key], 2)}
                 for t in s["by_type"].values()),
                key=lambda x: x["count"],
                reverse=True,
            )

        return {"eenheid": unit, "storeys": storeys}

    def project_overview(self) -> dict[str, Any]:
        projects = self.model.by_type("IfcProject")
        sites = self.model.by_type("IfcSite")
        buildings = self.model.by_type("IfcBuilding")
        storey_objs = self.elements("Storey")
        storey_names = sorted(self.name(s) for s in storey_objs)
        return {
            "project": self.name(projects[0]) if projects else None,
            "site": self.name(sites[0]) if sites else None,
            "building": self.name(buildings[0]) if buildings else None,
            "ifc_schema": getattr(self.model, "schema", None),
            "totals": {key: self.count(key) for key in ("Wall", "Door", "Window", "Space", "Storey", "Slab", "Roof", "Stair", "Covering", "Column", "Beam")},
            "storey_names": storey_names,
        }

    def wall_overview(self) -> dict[str, Any]:
        return self._storey_element_overview("Wall", [
            ("Qto_WallBaseQuantities", "NetSideArea"),
            ("Qto_WallBaseQuantities", "GrossSideArea"),
            ("BaseQuantities", "NetSideArea"),
        ])

    def door_overview(self) -> dict[str, Any]:
        return self._storey_element_overview("Door", [
            ("Qto_DoorBaseQuantities", "Area"),
            ("BaseQuantities", "Area"),
        ])

    def window_overview(self) -> dict[str, Any]:
        return self._storey_element_overview("Window", [
            ("Qto_WindowBaseQuantities", "Area"),
            ("BaseQuantities", "Area"),
        ])

    def slab_overview(self) -> dict[str, Any]:
        return self._storey_element_overview("Slab", [
            ("Qto_SlabBaseQuantities", "GrossArea"),
            ("Qto_SlabBaseQuantities", "NetArea"),
            ("BaseQuantities", "GrossArea"),
        ])

    def roof_overview(self) -> dict[str, Any]:
        return self._storey_element_overview("Roof", [
            ("Qto_RoofBaseQuantities", "TotalSurfaceArea"),
            ("Qto_RoofBaseQuantities", "ProjectedArea"),
            ("BaseQuantities", "TotalSurfaceArea"),
        ])

    def stair_overview(self) -> dict[str, Any]:
        return self._storey_element_overview("Stair", [])

    def covering_overview(self) -> dict[str, Any]:
        return self._storey_element_overview("Covering", [
            ("Qto_CoveringBaseQuantities", "GrossArea"),
            ("Qto_CoveringBaseQuantities", "NetArea"),
            ("BaseQuantities", "GrossArea"),
        ])

    def column_overview(self) -> dict[str, Any]:
        return self._storey_element_overview("Column", [
            ("Qto_ColumnBaseQuantities", "GrossVolume"),
            ("BaseQuantities", "GrossVolume"),
        ], quantity_key="volume_m3", unit="m3")

    def beam_overview(self) -> dict[str, Any]:
        return self._storey_element_overview("Beam", [
            ("Qto_BeamBaseQuantities", "GrossVolume"),
            ("BaseQuantities", "GrossVolume"),
        ], quantity_key="volume_m3", unit="m3")

    def space_overview(self) -> dict[str, Any]:
        storey_data: dict[str, dict] = {}

        for el in self.elements("Space"):
            storey_obj = self._storey_object(el)
            s_name = self.name(storey_obj) if storey_obj else "Onbekende bouwlaag"
            elevation = float(getattr(storey_obj, "Elevation", 0) or 0) if storey_obj else 0.0
            bvo = self._get_quantity(el,
                ("Qto_SpaceBaseQuantities", "GrossFloorArea"),
                ("BaseQuantities", "GrossFloorArea"),
            ) or 0.0
            nvo = self._get_quantity(el,
                ("Qto_SpaceBaseQuantities", "NetFloorArea"),
                ("BaseQuantities", "NetFloorArea"),
            ) or 0.0

            if s_name not in storey_data:
                storey_data[s_name] = {
                    "storey_name": s_name,
                    "elevation": elevation,
                    "count": 0,
                    "bvo_m2": 0.0,
                    "nvo_m2": 0.0,
                    "spaces": [],
                }
            storey_data[s_name]["count"] += 1
            storey_data[s_name]["bvo_m2"] += bvo
            storey_data[s_name]["nvo_m2"] += nvo
            storey_data[s_name]["spaces"].append(self.name(el))

        storeys = sorted(storey_data.values(), key=lambda x: x["elevation"])
        for s in storeys:
            s["bvo_m2"] = round(s["bvo_m2"], 2)
            s["nvo_m2"] = round(s["nvo_m2"], 2)
            s["spaces"] = sorted(s["spaces"])

        return {"eenheid": "m2", "storeys": storeys}

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
