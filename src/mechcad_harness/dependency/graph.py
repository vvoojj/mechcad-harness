from pathlib import Path
from typing import Any
import json

from .errors import DependencyConfigError, DependencyCycleError
from .models import ChangeImpact, DependencyEdge, DependencyRule


def _parse_config(text: str) -> dict[str, Any]:
    """Parse the small list-oriented YAML subset used by M3 configuration."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    data: dict[str, Any] = {"rules": [], "edges": []}
    section: str | None = None
    current: dict[str, Any] | None = None
    field: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        if not line.startswith(" ") and stripped.endswith(":"):
            section = stripped[:-1]
            if section in {"rules", "edges"}:
                data[section] = []
            continue
        if section is None:
            continue
        if stripped.startswith("- "):
            value = stripped[2:].strip()
            if ":" in value:
                key, item = value.split(":", 1)
                current = {key.strip(): _scalar(item.strip())}
                data[section].append(current)
            else:
                if current is None or field is None:
                    raise ValueError("list item has no parent field")
                current.setdefault(field, []).append(_scalar(value))
            continue
        if ":" not in stripped:
            raise ValueError(f"invalid dependency configuration line: {raw_line}")
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if current is not None and line.startswith("  "):
            if value:
                current[key] = _scalar(value)
                field = None
            else:
                current[key] = []
                field = key
        elif value:
            data[key] = _scalar(value)
        else:
            data[key] = []
    return data


def _scalar(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _parts(path: str) -> tuple[str, ...]:
    if not isinstance(path, str) or not path.startswith("/") or path == "/":
        raise DependencyConfigError(f"invalid dependency path: {path!r}")
    segments = tuple(path[1:].split("/"))
    if any(not segment or "~" in segment for segment in segments):
        raise DependencyConfigError(f"invalid dependency path: {path!r}")
    return segments


def path_matches(pattern: str, path: str) -> bool:
    pattern_parts = _parts(pattern)
    path_parts = _parts(path)
    if len(pattern_parts) > len(path_parts):
        return False
    return all(expected == "*" or expected == actual for expected, actual in zip(pattern_parts, path_parts))


class DependencyGraph:
    def __init__(self, rules: list[DependencyRule], edges: list[DependencyEdge]):
        self.rules = rules
        self.edges = edges
        self._nodes = {node for rule in rules for node in rule.invalidates}
        self._nodes.update(edge.source for edge in edges)
        self._nodes.update(edge.target for edge in edges)
        self._downstream: dict[str, tuple[str, ...]] = {}
        for edge in edges:
            self._downstream.setdefault(edge.source, set()).add(edge.target)
        self._downstream = {source: tuple(sorted(targets)) for source, targets in self._downstream.items()}
        self._check_cycles()

    @classmethod
    def from_yaml(cls, path: str | Path) -> "DependencyGraph":
        try:
            data: Any = _parse_config(Path(path).read_text(encoding="utf-8"))
            rules = [DependencyRule.model_validate(rule) for rule in data.get("rules", [])]
            edges_data = data.get("edges", [])
            edges = []
            for edge in edges_data:
                if "from" in edge:
                    edge = {"source": edge["from"], "target": edge["to"]}
                edges.append(DependencyEdge.model_validate(edge))
            for rule in rules:
                for pattern in rule.when:
                    _parts(pattern)
        except Exception as exc:
            if isinstance(exc, DependencyConfigError):
                raise
            raise DependencyConfigError(f"invalid dependency configuration: {path}") from exc
        return cls(rules, edges)

    @property
    def nodes(self) -> tuple[str, ...]:
        return tuple(sorted(self._nodes))

    def knows(self, node: str) -> bool:
        return node in self._nodes

    def _check_cycles(self) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise DependencyCycleError(f"dependency cycle detected at {node}")
            if node in visited:
                return
            visiting.add(node)
            for target in self._downstream.get(node, ()):
                visit(target)
            visiting.remove(node)
            visited.add(node)

        for node in sorted(self._nodes):
            visit(node)

    def _transitive(self, node: str, result: set[str]) -> None:
        if node in result:
            return
        result.add(node)
        for target in self._downstream.get(node, ()):
            self._transitive(target, result)

    def impact(self, changed_paths: list[str] | tuple[str, ...]) -> ChangeImpact:
        normalized_paths = tuple(dict.fromkeys(changed_paths))
        direct = {
            node
            for path in normalized_paths
            for rule in self.rules
            if any(path_matches(pattern, path) for pattern in rule.when)
            for node in rule.invalidates
        }
        all_nodes: set[str] = set()
        for node in sorted(direct):
            self._transitive(node, all_nodes)
        return ChangeImpact(
            changed_paths=normalized_paths,
            direct_nodes=tuple(sorted(direct)),
            all_nodes=tuple(sorted(all_nodes)),
        )
