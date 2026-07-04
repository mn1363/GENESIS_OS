from dataclasses import dataclass
from typing import Dict, Type, Any


@dataclass
class RepositoryRegistry:
    """
    Central registry for all storage repositories.
    """

    _repos: Dict[str, Any]

    def __init__(self):
        self._repos = {}

    def register(self, name: str, repo: Any) -> None:
        self._repos[name] = repo

    def get(self, name: str) -> Any:
        if name not in self._repos:
            raise KeyError(f"Repository not found: {name}")
        return self._repos[name]