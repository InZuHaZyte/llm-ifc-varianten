from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from ifc_model import IfcModel


ModelProvider = Callable[[], IfcModel]


def register_tools(mcp: Any, model: ModelProvider, logger: logging.Logger) -> None:
    # --- OUDE TOOLS (uitgeschakeld) ---
    #
    # @mcp.tool()
    # def get_model_summary() -> dict[str, Any]:
    #     logger.info("Tool called: get_model_summary")
    #     return model().get_model_summary()
    #
    # @mcp.tool()
    # def get_available_values(property_name: str, entity_type: str | None = None) -> list[Any] | dict[str, list[Any]]:
    #     """Return distinct values for a property.
    #
    #     If entity_type is unknown, omit it to search all supported entity types.
    #     """
    #     logger.info(
    #         "Tool called: get_available_values entity_type=%s property_name=%s",
    #         entity_type,
    #         property_name,
    #     )
    #     if entity_type is None:
    #         return model().available_values_by_entity(property_name)
    #     return model().available_values(entity_type, property_name)
    #
    # @mcp.tool()
    # def query_elements(
    #     entity_type: str | None = None,
    #     element_type: str | None = None,
    #     storey: str | None = None,
    #     storey_name: str | None = None,
    #     type_name: str | None = None,
    #     name_contains: str | None = None,
    #     property_filters: dict[str, Any] | None = None,
    # ) -> list[dict[str, Any]]:
    #     """Query IFC elements. If entity_type is omitted, Space is used."""
    #     resolved_entity_type = entity_type or element_type or "Space"
    #     resolved_storey = storey or storey_name
    #     logger.info(
    #         "Tool called: query_elements entity_type=%s storey=%s type_name=%s",
    #         resolved_entity_type,
    #         resolved_storey,
    #         type_name,
    #     )
    #     return model().query_elements(
    #         resolved_entity_type,
    #         resolved_storey,
    #         type_name,
    #         name_contains,
    #         property_filters,
    #     )
    #
    # @mcp.tool()
    # def count_elements(
    #     entity_type: str | None = None,
    #     element_type: str | None = None,
    #     storey: str | None = None,
    #     storey_name: str | None = None,
    #     type_name: str | None = None,
    #     property_filters: dict[str, Any] | None = None,
    #     group_by: str | None = None,
    # ) -> int | dict[str, int]:
    #     """Count IFC elements. If entity_type is omitted, Space is used."""
    #     resolved_entity_type = entity_type or element_type or "Space"
    #     resolved_storey = storey or storey_name
    #     logger.info(
    #         "Tool called: count_elements entity_type=%s group_by=%s",
    #         resolved_entity_type,
    #         group_by,
    #     )
    #     return model().count_elements(
    #         resolved_entity_type,
    #         resolved_storey,
    #         type_name,
    #         property_filters,
    #         group_by,
    #     )
    #
    # @mcp.tool()
    # def sum_numeric_property(
    #     property_name: str = "GrossFloorArea",
    #     entity_type: str | None = None,
    #     element_type: str | None = None,
    #     storey: str | None = None,
    #     storey_name: str | None = None,
    #     type_name: str | None = None,
    #     property_filters: dict[str, Any] | None = None,
    #     group_by: str | None = None,
    #     elements: list[Any] | None = None,
    #     property_set_name: str | None = None,
    # ) -> dict[str, Any]:
    #     """Sum a numeric IFC property. Defaults to Space GrossFloorArea."""
    #     resolved_entity_type = entity_type or element_type or "Space"
    #     resolved_storey = storey or storey_name
    #     logger.info(
    #         "Tool called: sum_numeric_property entity_type=%s property_name=%s group_by=%s",
    #         resolved_entity_type,
    #         property_name,
    #         group_by,
    #     )
    #     if elements is not None:
    #         return model().sum_numeric_property_for_elements(
    #             elements,
    #             property_name,
    #             resolved_entity_type,
    #         )
    #     return model().sum_numeric_property(
    #         resolved_entity_type,
    #         property_name,
    #         resolved_storey,
    #         type_name,
    #         property_filters,
    #         group_by,
    #     )
    #
    # @mcp.tool()
    # def get_related_elements(
    #     source_entity_type: str,
    #     source_identifier: str,
    #     relation: str,
    #     target_entity_type: str | None = None,
    #     direction: str = "both",
    # ) -> list[dict[str, Any]]:
    #     logger.info(
    #         "Tool called: get_related_elements source_entity_type=%s relation=%s",
    #         source_entity_type,
    #         relation,
    #     )
    #     return model().related_elements(
    #         source_entity_type,
    #         source_identifier,
    #         relation,
    #         target_entity_type,
    #         direction,
    #     )
    #
    # @mcp.tool()
    # def get_element_details(
    #     identifier: str,
    #     include_properties: bool = True,
    #     include_psets: bool = True,
    #     include_relationships: bool = True,
    # ) -> dict[str, Any]:
    #     logger.info("Tool called: get_element_details identifier=%s", identifier)
    #     return model().details(identifier, include_properties, include_psets, include_relationships)
    #
    # @mcp.tool()
    # def get_property_sets(identifier: str, pset_name: str | None = None) -> dict[str, Any]:
    #     logger.info("Tool called: get_property_sets identifier=%s pset_name=%s", identifier, pset_name)
    #     return model().get_property_sets(identifier, pset_name)
    #
    # @mcp.tool()
    # def search_elements(
    #     query: str,
    #     entity_types: list[str] | None = None,
    #     properties: list[str] | None = None,
    #     limit: int = 25,
    # ) -> list[dict[str, Any]]:
    #     logger.info("Tool called: search_elements query=%s limit=%s", query, limit)
    #     return model().search(query, entity_types, properties, limit)

    # --- NIEUWE TOOLS ---

    @mcp.tool()
    def get_model_summary() -> dict[str, Any]:
        """Geef een algemeen overzicht van het IFC-model.

        Retourneert projectnaam, beschikbare IFC-entiteiten, aantallen per categorie,
        verdiepingen en ruimtes. Gebruik dit als startpunt voordat je specifieke vragen beantwoordt.
        """
        logger.info("Tool called: get_model_summary")
        return model().get_model_summary()

    @mcp.tool()
    def describe_entity_type(entity_type: str) -> dict[str, Any]:
        """Ontdek welke informatie beschikbaar is voor een IFC-entiteitstype.

        Retourneert beschikbare eigenschappen, Property Sets (Psets), relaties,
        veelvoorkomende waarden en mogelijke filtervelden.
        Gebruik dit wanneer je niet zeker weet welke eigenschappen beschikbaar zijn.

        Voorbeelden: IfcWall, IfcDoor, IfcWindow, IfcSpace, IfcSlab, IfcBuildingElementProxy
        """
        logger.info("Tool called: describe_entity_type entity_type=%s", entity_type)
        return model().describe_entity_type(entity_type)

    @mcp.tool()
    def get_available_values(
        entity_type: str | None = None,
        property: str | None = None,
        property_name: str | None = None,
    ) -> list[Any] | dict[str, list[Any]]:
        """Haal alle unieke waarden op van een eigenschap voor een entiteitstype.

        Gebruik dit voordat je filters toepast wanneer de exacte waarde nog onbekend is.
        Helpt bij het ontdekken van verdiepingsnamen, type-namen, materialen, classificaties.

        Voorbeeld: get_available_values(entity_type="IfcWall", property="TypeName")
        Als entity_type wordt weggelaten, worden alle entiteitstypen doorzocht.
        """
        resolved_property = property or property_name
        if not resolved_property:
            raise ValueError("Geef 'property' of 'property_name' op.")
        logger.info(
            "Tool called: get_available_values entity_type=%s property=%s",
            entity_type,
            resolved_property,
        )
        if entity_type is None:
            return model().available_values_by_entity(resolved_property)
        return model().available_values(entity_type, resolved_property)

    @mcp.tool()
    def query_elements(
        entity_type: str | None = None,
        element_type: str | None = None,
        storey: str | None = None,
        storey_name: str | None = None,
        type_name: str | None = None,
        name_contains: str | None = None,
        filters: dict[str, Any] | None = None,
        property_filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Vraag IFC-elementen op basis van filters op.

        entity_type: IFC-entiteitstype (bijv. IfcWall, IfcDoor, IfcSpace, IfcSlab)
        storey: filter op verdiepingsnaam (ook storey_name is geldig)
        type_name: filter op type-naam
        name_contains: filter op naam (gedeeltelijke match)
        filters: JSON-object met eigenschap-waarde filters. Filterwaarden zijn ALTIJD scalair.
            LET OP: filters moet een JSON-object (dict) zijn, NOOIT een lijst.
            Goed:   {"storey": "01 eerste verdieping", "LoadBearing": true}
            Fout:   [["storey", "=", "01 eerste verdieping"]]
            Fout:   {"LoadBearing": [true], "storey": ["01 eerste verdieping"]}
        property_filters: alias voor filters

        Gebruik query_elements voor een lijst van individuele elementen met details.
        Gebruik aggregate_elements als je aantallen, totalen of uitsplitsingen nodig hebt.
        """
        resolved_entity_type = entity_type or element_type or "Wall"
        resolved_storey = storey or storey_name
        combined = dict(filters or property_filters or {})
        if combined:
            resolved_storey = resolved_storey or combined.pop("storey", None) or combined.pop("storey_name", None)
        resolved_filters = combined or None
        logger.info(
            "Tool called: query_elements entity_type=%s storey=%s type_name=%s",
            resolved_entity_type,
            resolved_storey,
            type_name,
        )
        return model().query_elements(resolved_entity_type, resolved_storey, type_name, name_contains, resolved_filters)

    @mcp.tool()
    def aggregate_elements(
        entity_type: str | None = None,
        operation: str = "count",
        property_name: str | None = None,
        storey: str | None = None,
        storey_name: str | None = None,
        type_name: str | None = None,
        filters: dict[str, Any] | None = None,
        property_filters: dict[str, Any] | None = None,
        group_by: str | list[str] | None = None,
    ) -> dict[str, Any]:
        """Bereken statistieken en samenvattingen van IFC-elementen.

        GEBRUIK DEZE TOOL als de gebruiker vraagt om "hoeveel", "welke types", "per verdieping",
        "per type", "samenvatting", of als er veel elementen verwacht worden.
        Gebruik LIEVER aggregate_elements dan query_elements voor tellingen en uitsplitsingen.

        operation: count | sum | average | min | max
        property_name: eigenschap voor sum/average/min/max (niet nodig bij count)
        group_by: groepeer op één veld (string) of meerdere velden (lijst van strings).
            Meerdere velden worden gecombineerd: "name / type_name"

        filters: JSON-object met eigenschap-waarde filters (ALTIJD een dict, nooit een lijst).
            Filterwaarden zijn altijd scalaire waarden, NOOIT arrays.
            Goed: {"LoadBearing": true, "storey": "01 eerste verdieping"}
            Fout: {"LoadBearing": [true], "storey": ["01 eerste verdieping"]}

        Voorbeelden:
        - Dragende wanden per naam en type: operation="count", group_by=["name", "type_name"], filters={"LoadBearing": true}
        - Aantal wanden per verdieping: operation="count", group_by="storey"
        - m² vloeroppervlak per type: operation="sum", property_name="GrossFloorArea", group_by="type_name"
        """
        if not entity_type:
            raise ValueError("entity_type is vereist voor aggregate_elements.")
        resolved_storey = storey or storey_name
        combined = dict(filters or property_filters or {})
        if combined:
            resolved_storey = resolved_storey or combined.pop("storey", None) or combined.pop("storey_name", None)
        resolved_filters = combined or None
        logger.info(
            "Tool called: aggregate_elements entity_type=%s operation=%s property_name=%s group_by=%s",
            entity_type,
            operation,
            property_name,
            group_by,
        )
        return model().aggregate_elements(
            entity_type, operation, property_name, resolved_storey, type_name, resolved_filters, group_by
        )

    @mcp.tool()
    def get_element_details(
        identifier: str,
        include_properties: bool = True,
        include_psets: bool = True,
        include_relationships: bool = True,
    ) -> dict[str, Any]:
        """Haal alle beschikbare informatie van één specifiek element op.

        Retourneert basisgegevens, eigenschappen, Property Sets, type-informatie en classificaties.
        identifier: GUID, naam of numeriek element-ID

        Gebruik dit nadat een specifiek element is gevonden via query_elements of search_elements.
        """
        logger.info("Tool called: get_element_details identifier=%s", identifier)
        return model().details(identifier, include_properties, include_psets, include_relationships)

    @mcp.tool()
    def get_related_elements(
        source_entity_type: str,
        source_identifier: str,
        relation: str,
        target_entity_type: str | None = None,
        direction: str = "both",
    ) -> list[dict[str, Any]]:
        """Onderzoek relaties tussen IFC-elementen.

        relation: CONTAINS | BOUNDS_SPACE | FILLS_OPENING | HOSTS_OPENING
        source_identifier: GUID, naam of element-ID van het bronelement
        target_entity_type: filter resultaten op entiteitstype (optioneel)

        Voorbeelden:
        - Welke ruimtes worden begrensd door een wand: relation="BOUNDS_SPACE"
        - Welke ramen/deuren zitten in een wand: relation="HOSTS_OPENING"
        - Welke elementen bevinden zich op een verdieping: relation="CONTAINS"
        """
        logger.info(
            "Tool called: get_related_elements source_entity_type=%s relation=%s",
            source_entity_type,
            relation,
        )
        return model().related_elements(
            source_entity_type, source_identifier, relation, target_entity_type, direction
        )

    @mcp.tool()
    def search_elements(
        query: str,
        entity_types: list[str] | None = None,
        properties: list[str] | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        """Zoek vrije tekst in het IFC-model.

        Zoekt in namen, type-namen, objecttypen, beschrijvingen en classificaties.
        Gebruik dit wanneer onbekend is waar een object zich bevindt of hoe het exact gemodelleerd is.

        Voorbeelden: dorpel, waterslag, pv-paneel, lift, balkon
        """
        logger.info("Tool called: search_elements query=%s limit=%s", query, limit)
        return model().search(query, entity_types, properties, limit)

    @mcp.tool()
    def get_property_sets(identifier: str, pset_name: str | None = None) -> dict[str, Any]:
        """Haal alle Property Sets (Psets) van een element op.

        Gebruik dit wanneer specifieke BIM-eigenschappen nodig zijn die niet zichtbaar zijn
        in de basisgegevens, zoals brandwerendheid, akoestische waarden, U-waarden,
        constructieve eigenschappen of fabrikantinformatie.

        identifier: GUID, naam of numeriek element-ID
        pset_name: filter op een specifieke Pset (optioneel)
        """
        logger.info("Tool called: get_property_sets identifier=%s pset_name=%s", identifier, pset_name)
        return model().get_property_sets(identifier, pset_name)

    @mcp.tool()
    def explain_model_structure() -> dict[str, Any]:
        """Beschrijf hoe het huidige IFC-model is opgebouwd.

        Retourneert voor elke aanwezige IFC-entiteit: aantallen, aanwezige Property Sets,
        veelgebruikte eigenschappen en beschikbare relaties.
        Gebruik dit wanneer je het model wilt verkennen voordat je gerichte queries uitvoert.
        """
        logger.info("Tool called: explain_model_structure")
        return model().explain_model_structure()
