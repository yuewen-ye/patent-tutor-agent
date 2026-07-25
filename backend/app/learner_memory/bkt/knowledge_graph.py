"""Read-only knowledge-DAG adapter used by CAT diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from backend.app.curriculum.learning_path import load_knowledge_dag

_WEIGHT_MAP = {"高": 3, "中": 2, "低": 1}


@dataclass(frozen=True, slots=True)
class KnowledgeGraph:
    nodes: dict[str, dict[str, Any]]
    children: dict[str, tuple[str, ...]]
    parents: dict[str, tuple[str, ...]]
    prerequisites: dict[str, tuple[str, ...]]
    dependents: dict[str, tuple[str, ...]]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "KnowledgeGraph":
        nodes = {
            str(node["node_id"]): dict(node)
            for node in payload.get("nodes", [])
            if isinstance(node, dict) and node.get("node_id")
        }
        children: dict[str, list[str]] = {node_id: [] for node_id in nodes}
        parents: dict[str, list[str]] = {node_id: [] for node_id in nodes}
        prerequisites: dict[str, list[str]] = {node_id: [] for node_id in nodes}
        dependents: dict[str, list[str]] = {node_id: [] for node_id in nodes}
        for edge in payload.get("edges", []):
            source = str(edge.get("from") or "")
            target = str(edge.get("to") or "")
            if source not in nodes or target not in nodes:
                raise ValueError(f"knowledge edge references unknown node: {source}->{target}")
            if edge.get("type") == "contains":
                children[source].append(target)
                parents[target].append(source)
            elif edge.get("type") == "prerequisite":
                prerequisites[target].append(source)
                dependents[source].append(target)
        return cls(
            nodes=nodes,
            children={key: tuple(value) for key, value in children.items()},
            parents={key: tuple(value) for key, value in parents.items()},
            prerequisites={key: tuple(value) for key, value in prerequisites.items()},
            dependents={key: tuple(value) for key, value in dependents.items()},
        )

    def get_weight(self, skill_id: str) -> int:
        node = self.nodes.get(skill_id, {})
        return _WEIGHT_MAP.get(str(node.get("exam_weight", "低")), 1)

    def get_high_weight_leaves(self, *, minimum_weight: int = 2) -> list[str]:
        return [
            node_id
            for node_id in self.nodes
            if not self.children[node_id] and self.get_weight(node_id) >= minimum_weight
        ]

    def get_children(self, skill_id: str) -> tuple[str, ...]:
        return self.children.get(skill_id, ())

    def get_parents(self, skill_id: str) -> tuple[str, ...]:
        return self.parents.get(skill_id, ())

    def get_prerequisites(self, skill_id: str) -> tuple[str, ...]:
        return self.prerequisites.get(skill_id, ())

    def get_dependents(self, skill_id: str) -> tuple[str, ...]:
        return self.dependents.get(skill_id, ())

    def all_node_ids(self) -> list[str]:
        return list(self.nodes)


@lru_cache(maxsize=1)
def load_knowledge_graph() -> KnowledgeGraph:
    return KnowledgeGraph.from_payload(load_knowledge_dag())
