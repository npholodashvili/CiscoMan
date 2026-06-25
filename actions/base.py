"""Base classes and utilities for Action Cards."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jinja2 import Environment, StrictUndefined

_jinja = Environment(undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)


@dataclass
class Param:
    key: str
    label: str
    kind: str = "text"  # text | int | textarea | select | bool
    default: Any = ""
    help: str = ""
    options: list[str] = field(default_factory=list)
    placeholder: str = ""


@dataclass
class Action:
    id: str
    name: str
    category: str
    kind: str  # 'show' or 'config'
    explanation: str
    template: str
    params: list[Param] = field(default_factory=list)
    save_after: bool = False
    use_textfsm: bool = False
    danger: bool = False
    platforms: list[str] = field(default_factory=lambda: ["all"])

    def render(self, values: dict) -> list[str]:
        """Render the Jinja template into a list of CLI lines."""
        rendered = _jinja.from_string(self.template).render(**values)
        return [ln.rstrip() for ln in rendered.splitlines() if ln.strip()]