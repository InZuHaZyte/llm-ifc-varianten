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

    def test_fixed_tools_are_registered(self) -> None:
        mcp = FakeMCP()
        register_tools(mcp, lambda: None, Mock())
        expected = {
            "count_walls",
            "count_windows",
            "count_doors",
            "count_spaces",
            "count_storeys",
            "list_storeys",
            "list_spaces",
            "list_wall_types",
            "list_window_types",
            "list_door_types",
            "count_walls_by_storey",
            "count_windows_by_storey",
            "count_doors_by_storey",
            "count_spaces_by_storey",
            "list_walls_ground_floor",
            "list_windows_ground_floor",
            "list_doors_ground_floor",
            "list_walls_first_floor",
            "list_windows_first_floor",
            "list_doors_first_floor",
            "list_spaces_bounded_by_walls",
            "list_walls_bounding_spaces",
            "list_windows_filling_walls",
            "list_doors_filling_walls",
            "get_project_summary",
            "get_model_statistics",
            "get_available_element_categories",
        }
        self.assertTrue(expected.issubset(mcp.tools.keys()))

    def test_optional_real_ifc_model_can_be_opened(self) -> None:
        path = os.getenv("IFC_TEST_MODEL_PATH")
        if not path:
            self.skipTest("Set IFC_TEST_MODEL_PATH to smoke test a real IFC file.")
        model = IfcModel(path)
        self.assertIsInstance(model.project_summary(), dict)


if __name__ == "__main__":
    unittest.main()
