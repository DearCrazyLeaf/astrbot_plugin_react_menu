"""Metadata for a registered API menu adapter."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

RESERVED_CARD_FIELDS = frozenset(
    {"menu_id", "provider_id", "name", "keywords", "title", "items", "umo"}
)


@dataclass(frozen=True)
class ProviderSpec:
    provider_id: str
    plugin_id: str
    display_name: str
    api_versions: tuple[int, ...]
    platforms: tuple[str, ...]
    schema_path: Path
    unconfigured_keywords: tuple[str, ...] = ()
    legacy_root_dir: str = ""
    legacy_shared_level: str = ""

    @cached_property
    def template(self) -> dict[str, Any]:
        return json.loads(self.schema_path.read_text(encoding="utf-8"))

    @cached_property
    def option_keys(self) -> tuple[str, ...]:
        return tuple(key for key in self.template["items"] if key not in RESERVED_CARD_FIELDS)

    def migrate_card(self, card: dict[str, Any]) -> bool:
        """Optionally upgrade a persisted menu card in place."""
        return False

    def layout_for_card(
        self, card: dict[str, Any], normalize_items: Callable[[Any], list[dict[str, str]]]
    ) -> dict[str, Any]:
        """Build consumer-side presentation settings (not passed to the target plugin)."""
        return {}

    def options_for_card(
        self, card: dict[str, Any], layout: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return {key: card[key] for key in self.option_keys if key in card}

    def present_page(
        self, page: dict[str, Any], title: str, items: list[dict[str, str]], layout: dict[str, Any]
    ) -> tuple[str, list[dict[str, str]]]:
        """Optionally lay out a page using the actions advertised by the provider."""
        return title, items

    def max_concurrent_user_flows(self, layout: dict[str, Any]) -> int | None:
        """Return the per-session limit for active user-scoped flows, if any."""
        return None

    def mentions_owner(self, page: dict[str, Any]) -> bool:
        """Whether the rendered page should mention the user who opened it."""
        return False

    def starts_user_flow(self, state: Any, action_id: str) -> bool:
        """Whether a shared-page action starts a private user-scoped flow."""
        return False

    def page_scope(self, page: dict[str, Any]) -> str:
        scope = page.get("scope")
        if scope in ("shared", "user"):
            return scope
        state = page.get("state")
        if (
            self.legacy_shared_level
            and isinstance(state, dict)
            and state.get("level") == self.legacy_shared_level
        ):
            return "shared"
        return "user"
