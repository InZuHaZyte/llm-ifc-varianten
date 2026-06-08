"""
Basis smoke-tests — werken zonder een echte IFC of Neo4j.
Voer uit met: python -m pytest tests/ -v
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ifc.graph_builder import GraphData
from graph.retrieval import GraphRetriever
from llm.prompts import CYPHER_GENERATION_TEMPLATE, GRAPH_SCHEMA, EXAMPLE_QUERIES


def test_graph_data_summary_empty():
    data = GraphData()
    summary = data.summary()
    assert "Projects=0" in summary
    assert "Walls=0" in summary


def test_graph_data_summary_with_data():
    data = GraphData(
        walls=[{"guid": "abc", "name": "W1", "load_bearing": True}],
        storeys=[{"guid": "def", "name": "BG"}],
    )
    assert "Walls=1" in data.summary()
    assert "Storeys=1" in data.summary()


def test_cypher_prompt_contains_schema():
    prompt = CYPHER_GENERATION_TEMPLATE.format(
        schema=GRAPH_SCHEMA,
        examples=EXAMPLE_QUERIES,
        question="Hoeveel wanden zijn er?",
    )
    assert "Wall" in prompt
    assert "ON_STOREY" in prompt
    assert "Hoeveel wanden" in prompt


def test_format_results_empty():
    class FakeClient:
        pass

    retriever = GraphRetriever(FakeClient())  # type: ignore
    result = retriever.format_results([])
    assert result == "Geen resultaten gevonden."


def test_format_results_with_data():
    class FakeClient:
        pass

    retriever = GraphRetriever(FakeClient())  # type: ignore
    records = [{"name": "Wand 1", "load_bearing": True}]
    result = retriever.format_results(records)
    assert "Wand 1" in result
