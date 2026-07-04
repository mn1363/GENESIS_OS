"""Central registry for all storage repositories.

Unchanged contract from the Phase 4 scaffold: a plain name -> repository
lookup, populated by `di_wire.wire_storage()`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RepositoryRegistry:
    """Central registry for all storage repositories."""

    _repos: dict[str, Any] = field(default_factory=dict)

    def register(self, name: str, repo: Any) -> None:
        self._repos[name] = repo

    def get(self, name: str) -> Any:
        if name not in self._repos:
            raise KeyError(f"Repository not found: {name}")
        return self._repos[name]
