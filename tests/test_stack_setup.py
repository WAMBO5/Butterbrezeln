"""Offline sanity check that the LangGraph + Anthropic SDK stack composes. No API calls."""
from typing import TypedDict

import anthropic
from langgraph.graph import END, START, StateGraph


class S(TypedDict):
    n: int


def test_graph_compiles_and_runs_offline():
    g = StateGraph(S)
    g.add_node("inc", lambda s: {"n": s["n"] + 1})
    g.add_edge(START, "inc")
    g.add_edge("inc", END)
    assert g.compile().invoke({"n": 1}) == {"n": 2}


def test_anthropic_client_constructs_without_network():
    assert anthropic.Anthropic(api_key="test-key").messages is not None


def test_product_graph_compiles():
    from pipeline.graph.map import build_graph

    nodes = set(build_graph().get_graph().nodes)
    assert {"components", "route", "judge", "coverage", "writer", "export"} <= nodes
