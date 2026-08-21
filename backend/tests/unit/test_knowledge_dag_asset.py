from __future__ import annotations

import pytest

from backend.app.curriculum.learning_path import load_knowledge_dag

pytestmark = pytest.mark.unit


def test_runtime_knowledge_dag_has_chapters_subsections_and_knowledge_points() -> None:
    graph = load_knowledge_dag()
    nodes = {str(node["node_id"]): node for node in graph["nodes"]}
    contains_edges = {
        (str(edge["from"]), str(edge["to"]))
        for edge in graph["edges"]
        if edge.get("type") == "contains"
    }
    chapter_nodes = [node for node in nodes.values() if node.get("level") == 1]
    subsection_nodes = [node for node in nodes.values() if node.get("level") == 2]

    assert len(chapter_nodes) == 10
    assert len(subsection_nodes) == 33
    assert all(node["knowledge_sub_nodes"] for node in chapter_nodes)
    assert all(node["knowledge_points"] for node in subsection_nodes)
    assert all(
        isinstance(point, dict)
        and isinstance(point.get("point"), str)
        and point["point"].strip()
        for node in subsection_nodes
        for point in node["knowledge_points"]
    )
    assert all(
        (str(node["node_id"]), str(child_id)) in contains_edges
        for node in nodes.values()
        for child_id in node["knowledge_sub_nodes"]
    )
    assert all(
        child_id in nodes
        for node in nodes.values()
        for child_id in node["knowledge_sub_nodes"]
    )
    assert contains_edges == {
        (str(node["node_id"]), str(child_id))
        for node in nodes.values()
        for child_id in node["knowledge_sub_nodes"]
    }
