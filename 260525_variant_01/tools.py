from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from ifc_model import IfcModel


ModelProvider = Callable[[], IfcModel]


def register_tools(mcp: Any, model: ModelProvider, logger: logging.Logger) -> None:
    @mcp.tool()
    def count_walls() -> int:
        logger.info("Tool called: count_walls")
        return model().count("Wall")

    @mcp.tool()
    def count_windows() -> int:
        logger.info("Tool called: count_windows")
        return model().count("Window")

    @mcp.tool()
    def count_doors() -> int:
        logger.info("Tool called: count_doors")
        return model().count("Door")

    @mcp.tool()
    def count_spaces() -> int:
        logger.info("Tool called: count_spaces")
        return model().count("Space")

    @mcp.tool()
    def count_storeys() -> int:
        logger.info("Tool called: count_storeys")
        return model().count("Storey")

    @mcp.tool()
    def list_storeys() -> list[dict[str, Any]]:
        logger.info("Tool called: list_storeys")
        return model().list_by_type("Storey")

    @mcp.tool()
    def list_spaces() -> list[dict[str, Any]]:
        logger.info("Tool called: list_spaces")
        return model().list_by_type("Space")

    @mcp.tool()
    def list_wall_types() -> list[str]:
        logger.info("Tool called: list_wall_types")
        return model().distinct_type_names("Wall")

    @mcp.tool()
    def list_window_types() -> list[str]:
        logger.info("Tool called: list_window_types")
        return model().distinct_type_names("Window")

    @mcp.tool()
    def list_door_types() -> list[str]:
        logger.info("Tool called: list_door_types")
        return model().distinct_type_names("Door")

    @mcp.tool()
    def count_walls_by_storey() -> dict[str, int]:
        logger.info("Tool called: count_walls_by_storey")
        return model().count_by_storey("Wall")

    @mcp.tool()
    def count_windows_by_storey() -> dict[str, int]:
        logger.info("Tool called: count_windows_by_storey")
        return model().count_by_storey("Window")

    @mcp.tool()
    def count_doors_by_storey() -> dict[str, int]:
        logger.info("Tool called: count_doors_by_storey")
        return model().count_by_storey("Door")

    @mcp.tool()
    def count_spaces_by_storey() -> dict[str, int]:
        logger.info("Tool called: count_spaces_by_storey")
        return model().count_by_storey("Space")

    @mcp.tool()
    def list_walls_ground_floor() -> list[dict[str, Any]]:
        logger.info("Tool called: list_walls_ground_floor")
        return model().elements_on_storey_alias("Wall", ("begane", "ground", "00", "level 0"))

    @mcp.tool()
    def list_windows_ground_floor() -> list[dict[str, Any]]:
        logger.info("Tool called: list_windows_ground_floor")
        return model().elements_on_storey_alias("Window", ("begane", "ground", "00", "level 0"))

    @mcp.tool()
    def list_doors_ground_floor() -> list[dict[str, Any]]:
        logger.info("Tool called: list_doors_ground_floor")
        return model().elements_on_storey_alias("Door", ("begane", "ground", "00", "level 0"))

    @mcp.tool()
    def list_walls_first_floor() -> list[dict[str, Any]]:
        logger.info("Tool called: list_walls_first_floor")
        return model().elements_on_storey_alias("Wall", ("eerste", "first", "01", "level 1"))

    @mcp.tool()
    def list_windows_first_floor() -> list[dict[str, Any]]:
        logger.info("Tool called: list_windows_first_floor")
        return model().elements_on_storey_alias("Window", ("eerste", "first", "01", "level 1"))

    @mcp.tool()
    def list_doors_first_floor() -> list[dict[str, Any]]:
        logger.info("Tool called: list_doors_first_floor")
        return model().elements_on_storey_alias("Door", ("eerste", "first", "01", "level 1"))

    @mcp.tool()
    def list_spaces_bounded_by_walls() -> list[dict[str, Any]]:
        logger.info("Tool called: list_spaces_bounded_by_walls")
        return model().spaces_bounded_by_walls()

    @mcp.tool()
    def list_walls_bounding_spaces() -> dict[str, list[dict[str, Any]]]:
        logger.info("Tool called: list_walls_bounding_spaces")
        return model().walls_bounding_spaces()

    @mcp.tool()
    def list_windows_filling_walls() -> list[dict[str, Any]]:
        logger.info("Tool called: list_windows_filling_walls")
        return model().filling_elements("Window")

    @mcp.tool()
    def list_doors_filling_walls() -> list[dict[str, Any]]:
        logger.info("Tool called: list_doors_filling_walls")
        return model().filling_elements("Door")

    @mcp.tool()
    def get_project_summary() -> dict[str, Any]:
        logger.info("Tool called: get_project_summary")
        return model().project_summary()

    @mcp.tool()
    def get_model_statistics() -> dict[str, Any]:
        logger.info("Tool called: get_model_statistics")
        return model().model_statistics()

    @mcp.tool()
    def get_available_element_categories() -> list[str]:
        logger.info("Tool called: get_available_element_categories")
        return model().available_categories()

    @mcp.tool()
    def get_wall_statistics() -> dict[str, Any]:
        """Geeft aantal wanden en totale wandoppervlakte (m²), uitgesplitst per
        verdieping én per wandtype. Gebruik dit voor vragen over aantallen,
        oppervlakten of verdeling van wanden."""
        logger.info("Tool called: get_wall_statistics")
        return model().wall_statistics()

    @mcp.tool()
    def get_door_statistics() -> dict[str, Any]:
        """Geeft aantal deuren en totale deuropppervlakte (m²), uitgesplitst per
        verdieping én per deurtype. Gebruik dit voor vragen over aantallen,
        oppervlakten of verdeling van deuren."""
        logger.info("Tool called: get_door_statistics")
        return model().door_statistics()

    @mcp.tool()
    def get_window_statistics() -> dict[str, Any]:
        """Geeft aantal ramen en totale raamoppervlakte (m²), uitgesplitst per
        verdieping én per raamtype. Gebruik dit voor vragen over aantallen,
        oppervlakten of verdeling van ramen."""
        logger.info("Tool called: get_window_statistics")
        return model().window_statistics()

    @mcp.tool()
    def get_space_statistics() -> dict[str, Any]:
        """Geeft aantal ruimtes met bruto vloeroppervlakte (BVO) en netto
        vloeroppervlakte (NVO) in m², uitgesplitst per verdieping. Gebruik dit
        voor vragen over vloeroppervlak, BVO, NVO of ruimteaantallen."""
        logger.info("Tool called: get_space_statistics")
        return model().space_statistics()
