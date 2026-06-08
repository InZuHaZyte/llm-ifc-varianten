from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from ifc_model import IfcModel


ModelProvider = Callable[[], IfcModel]


def register_tools(mcp: Any, model: ModelProvider, logger: logging.Logger) -> None:
    @mcp.tool()
    def get_model_summary() -> dict[str, Any]:
        logger.info("Tool called: get_model_summary")
        return model().get_model_summary()

    @mcp.tool()
    def get_available_values(property_name: str, entity_type: str | None = None) -> list[Any] | dict[str, list[Any]]:
        """Return distinct values for a property.

        If entity_type is unknown, omit it to search all supported entity types.
        """
        logger.info(
            "Tool called: get_available_values entity_type=%s property_name=%s",
            entity_type,
            property_name,
        )
        if entity_type is None:
            return model().available_values_by_entity(property_name)
        return model().available_values(entity_type, property_name)

    @mcp.tool()
    def query_elements(
        entity_type: str | None = None,
        element_type: str | None = None,
        storey: str | None = None,
        storey_name: str | None = None,
        type_name: str | None = None,
        name_contains: str | None = None,
        property_filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Query IFC elements. If entity_type is omitted, Space is used."""
        resolved_entity_type = entity_type or element_type or "Space"
        resolved_storey = storey or storey_name
        logger.info(
            "Tool called: query_elements entity_type=%s storey=%s type_name=%s",
            resolved_entity_type,
            resolved_storey,
            type_name,
        )
        return model().query_elements(
            resolved_entity_type,
            resolved_storey,
            type_name,
            name_contains,
            property_filters,
        )

    @mcp.tool()
    def count_elements(
        entity_type: str | None = None,
        element_type: str | None = None,
        storey: str | None = None,
        storey_name: str | None = None,
        type_name: str | None = None,
        property_filters: dict[str, Any] | None = None,
        group_by: str | None = None,
    ) -> int | dict[str, int]:
        """Count IFC elements. If entity_type is omitted, Space is used."""
        resolved_entity_type = entity_type or element_type or "Space"
        resolved_storey = storey or storey_name
        logger.info(
            "Tool called: count_elements entity_type=%s group_by=%s",
            resolved_entity_type,
            group_by,
        )
        return model().count_elements(
            resolved_entity_type,
            resolved_storey,
            type_name,
            property_filters,
            group_by,
        )

    @mcp.tool()
    def sum_numeric_property(
        property_name: str = "GrossFloorArea",
        entity_type: str | None = None,
        element_type: str | None = None,
        storey: str | None = None,
        storey_name: str | None = None,
        type_name: str | None = None,
        property_filters: dict[str, Any] | None = None,
        group_by: str | None = None,
        elements: list[Any] | None = None,
        property_set_name: str | None = None,
    ) -> dict[str, Any]:
        """Sum a numeric IFC property. Defaults to Space GrossFloorArea."""
        resolved_entity_type = entity_type or element_type or "Space"
        resolved_storey = storey or storey_name
        logger.info(
            "Tool called: sum_numeric_property entity_type=%s property_name=%s group_by=%s",
            resolved_entity_type,
            property_name,
            group_by,
        )
        if elements is not None:
            return model().sum_numeric_property_for_elements(
                elements,
                property_name,
                resolved_entity_type,
            )
        return model().sum_numeric_property(
            resolved_entity_type,
            property_name,
            resolved_storey,
            type_name,
            property_filters,
            group_by,
        )

    @mcp.tool()
    def get_related_elements(
        source_entity_type: str,
        source_identifier: str,
        relation: str,
        target_entity_type: str | None = None,
        direction: str = "both",
    ) -> list[dict[str, Any]]:
        logger.info(
            "Tool called: get_related_elements source_entity_type=%s relation=%s",
            source_entity_type,
            relation,
        )
        return model().related_elements(
            source_entity_type,
            source_identifier,
            relation,
            target_entity_type,
            direction,
        )

    @mcp.tool()
    def get_element_details(
        identifier: str,
        include_properties: bool = True,
        include_psets: bool = True,
        include_relationships: bool = True,
    ) -> dict[str, Any]:
        logger.info("Tool called: get_element_details identifier=%s", identifier)
        return model().details(identifier, include_properties, include_psets, include_relationships)

    @mcp.tool()
    def get_property_sets(identifier: str, pset_name: str | None = None) -> dict[str, Any]:
        logger.info("Tool called: get_property_sets identifier=%s pset_name=%s", identifier, pset_name)
        return model().get_property_sets(identifier, pset_name)

    @mcp.tool()
    def search_elements(
        query: str,
        entity_types: list[str] | None = None,
        properties: list[str] | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        logger.info("Tool called: search_elements query=%s limit=%s", query, limit)
        return model().search(query, entity_types, properties, limit)
