from __future__ import annotations

from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import load_dotenv  # noqa: E402
from ifc_model import IfcModel  # noqa: E402
from tools import register_tools  # noqa: E402


class FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class SmokeTests(unittest.TestCase):
    def test_dotenv_loader_sets_missing_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text("SMOKE_TEST_VALUE=ok\n", encoding="utf-8")
            os.environ.pop("SMOKE_TEST_VALUE", None)
            load_dotenv(env_path)
            self.assertEqual(os.environ["SMOKE_TEST_VALUE"], "ok")

    def test_parameter_tools_are_registered(self) -> None:
        mcp = FakeMCP()
        register_tools(mcp, lambda: None, Mock())
        expected = {
            "get_model_summary",
            "get_available_values",
            "query_elements",
            "count_elements",
            "sum_numeric_property",
            "get_related_elements",
            "get_element_details",
            "get_property_sets",
            "search_elements",
        }
        self.assertTrue(expected.issubset(mcp.tools.keys()))

    def test_get_available_values_accepts_missing_entity_type(self) -> None:
        fake_model = Mock()
        fake_model.available_values_by_entity.return_value = {"Space": [12.5]}
        mcp = FakeMCP()
        register_tools(mcp, lambda: fake_model, Mock())

        result = mcp.tools["get_available_values"](property_name="GrossFloorArea")

        self.assertEqual(result, {"Space": [12.5]})
        fake_model.available_values_by_entity.assert_called_once_with("GrossFloorArea")

    def test_sum_numeric_property_defaults_to_space(self) -> None:
        fake_model = Mock()
        fake_model.sum_numeric_property.return_value = {"total": 42.0}
        mcp = FakeMCP()
        register_tools(mcp, lambda: fake_model, Mock())

        result = mcp.tools["sum_numeric_property"](property_name="GrossFloorArea")

        self.assertEqual(result, {"total": 42.0})
        fake_model.sum_numeric_property.assert_called_once_with(
            "Space",
            "GrossFloorArea",
            None,
            None,
            None,
            None,
        )

    def test_query_elements_accepts_storey_name_alias_and_defaults_to_space(self) -> None:
        fake_model = Mock()
        fake_model.query_elements.return_value = [{"id": 1}]
        mcp = FakeMCP()
        register_tools(mcp, lambda: fake_model, Mock())

        result = mcp.tools["query_elements"](storey_name="00 begane grond")

        self.assertEqual(result, [{"id": 1}])
        fake_model.query_elements.assert_called_once_with(
            "Space",
            "00 begane grond",
            None,
            None,
            None,
        )

    def test_query_elements_accepts_element_type_alias(self) -> None:
        fake_model = Mock()
        fake_model.query_elements.return_value = [{"id": 1}]
        mcp = FakeMCP()
        register_tools(mcp, lambda: fake_model, Mock())

        result = mcp.tools["query_elements"](
            element_type="Wall",
            storey_name="00 begane grond",
        )

        self.assertEqual(result, [{"id": 1}])
        fake_model.query_elements.assert_called_once_with(
            "Wall",
            "00 begane grond",
            None,
            None,
            None,
        )

    def test_count_elements_accepts_storey_name_alias_and_defaults_to_space(self) -> None:
        fake_model = Mock()
        fake_model.count_elements.return_value = 7
        mcp = FakeMCP()
        register_tools(mcp, lambda: fake_model, Mock())

        result = mcp.tools["count_elements"](storey_name="00 begane grond")

        self.assertEqual(result, 7)
        fake_model.count_elements.assert_called_once_with(
            "Space",
            "00 begane grond",
            None,
            None,
            None,
        )

    def test_count_elements_accepts_element_type_alias(self) -> None:
        fake_model = Mock()
        fake_model.count_elements.return_value = 7
        mcp = FakeMCP()
        register_tools(mcp, lambda: fake_model, Mock())

        result = mcp.tools["count_elements"](
            element_type="Wall",
            storey_name="00 begane grond",
        )

        self.assertEqual(result, 7)
        fake_model.count_elements.assert_called_once_with(
            "Wall",
            "00 begane grond",
            None,
            None,
            None,
        )

    def test_sum_numeric_property_accepts_storey_name_alias(self) -> None:
        fake_model = Mock()
        fake_model.sum_numeric_property.return_value = {"total": 12.0}
        mcp = FakeMCP()
        register_tools(mcp, lambda: fake_model, Mock())

        result = mcp.tools["sum_numeric_property"](storey_name="00 begane grond")

        self.assertEqual(result, {"total": 12.0})
        fake_model.sum_numeric_property.assert_called_once_with(
            "Space",
            "GrossFloorArea",
            "00 begane grond",
            None,
            None,
            None,
        )

    def test_sum_numeric_property_accepts_element_selection(self) -> None:
        fake_model = Mock()
        fake_model.sum_numeric_property_for_elements.return_value = {"total": 30.0}
        mcp = FakeMCP()
        register_tools(mcp, lambda: fake_model, Mock())

        result = mcp.tools["sum_numeric_property"](
            elements=[1, 2],
            property_set_name="Pset_SpaceCommon",
        )

        self.assertEqual(result, {"total": 30.0})
        fake_model.sum_numeric_property_for_elements.assert_called_once_with(
            [1, 2],
            "GrossFloorArea",
            "Space",
        )

    def test_storey_matching_allows_partial_names(self) -> None:
        model = object.__new__(IfcModel)
        model.storey = lambda element: "00 begane grond"  # type: ignore[method-assign]

        self.assertTrue(model.matches_storey(object(), "begane grond"))
        self.assertTrue(model.matches_storey(object(), "00 begane grond"))
        self.assertFalse(model.matches_storey(object(), "eerste verdieping"))

    def test_optional_real_ifc_model_can_be_opened(self) -> None:
        path = os.getenv("IFC_TEST_MODEL_PATH")
        if not path:
            self.skipTest("Set IFC_TEST_MODEL_PATH to smoke test a real IFC file.")
        model = IfcModel(path)
        self.assertIsInstance(model.get_model_summary(), dict)


if __name__ == "__main__":
    unittest.main()
