from pathlib import Path

from .errors import OwnershipViolationError


class OwnershipPolicy:
    def __init__(self, rules: list[dict[str, str]]):
        self.rules = [(rule["path"], rule["owner"]) for rule in rules]

    @classmethod
    def from_file(cls, path: str | Path) -> "OwnershipPolicy":
        rules: list[dict[str, str]] = []
        section = False
        current: dict[str, str] = {}
        for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line == "ownership:":
                section = True
            elif section and line.startswith("- path:"):
                if current:
                    rules.append(current)
                current = {"path": line.split(":", 1)[1].strip()}
            elif section and line.startswith("owner:") and current:
                current["owner"] = line.split(":", 1)[1].strip()
        if current:
            rules.append(current)
        return cls(rules)

    @staticmethod
    def _segments(path: str) -> list[str]:
        return path.strip("/").split("/")

    def owner_for(self, path: str) -> str | None:
        path_segments = self._segments(path)
        matches: list[tuple[int, str]] = []
        for rule_path, owner in self.rules:
            rule_segments = self._segments(rule_path)
            if len(rule_segments) <= len(path_segments) and all(
                expected == actual or expected == "*"
                for expected, actual in zip(rule_segments, path_segments)
            ):
                matches.append((sum(segment != "*" for segment in rule_segments), owner))
        return max(matches)[1] if matches else None

    def check(self, path: str, actor: str) -> None:
        owner = self.owner_for(path)
        if owner is None:
            raise OwnershipViolationError(f"no owner governs path: {path}")
        if owner != actor:
            raise OwnershipViolationError(f"actor {actor!r} does not own {path}; owner is {owner!r}")
