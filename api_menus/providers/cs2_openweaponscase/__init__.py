"""Adapter for the CS2 opening simulator's API version 1."""

import re
from collections.abc import Callable
from copy import deepcopy
from functools import cached_property
from pathlib import Path
from typing import Any

from ...contract import ProviderSpec

_PAGE_GROUPS = {
    "home": "home_menu",
    "type": "type_menu",
    "container": "case_menu",
    "quantity": "quantity_menu",
}
_CATEGORY_LABELS = {key: f"{key}_label" for key in ("case", "souvenir", "collection", "capsule")}
_LEGACY_FIELDS = {
    "home_menu": {"title": "title"},
    "type_menu": {
        "title": "type_page_title",
        "option_template": "category_option_template",
        "cancel_reply_text": "cancel_reply_text",
    },
    "case_menu": {
        "title_template": "container_page_title_template",
        "page_indicator_template": "page_indicator_template",
    },
    "quantity_menu": {"title_template": "quantity_page_title_template"},
}
_LEGACY_ROW_LABELS = {
    "home_menu": {
        "api:home:self_open": "self_open_label",
        "库存": "inventory_label",
        "开箱菜单": "price_help_label",
        "武器箱列表": "case_list_label",
        "清除库存": "clear_inventory_label",
        "更新武器箱": "update_cases_label",
        "清除缓存": "clear_cache_label",
    },
    "type_menu": {
        f"api:category:{key}": value for key, value in _CATEGORY_LABELS.items() if key != "capsule"
    },
    "case_menu": {
        "api:nav:prev": "previous_page_label",
        "api:nav:next": "next_page_label",
        "api:nav:back": "back_to_type_label",
    },
    "quantity_menu": {"api:nav:back": "back_to_container_label"},
}
_LEGACY_KEYS = frozenset(
    [key for fields in _LEGACY_FIELDS.values() for key in fields.values()]
    + [key for fields in _LEGACY_ROW_LABELS.values() for key in fields.values()]
    + ["capsule_label", "cancel_label", "quantity_options", "quantity_option_template"]
)


def _positive_count(value: Any) -> int | None:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return None
    return count if count > 0 else None


class CS2ProviderSpec(ProviderSpec):
    @cached_property
    def _layout_defaults(self) -> dict[str, Any]:
        return {
            group: {
                key: field["default"]
                for key, field in self.template["items"][group]["items"].items()
            }
            for group in _PAGE_GROUPS.values()
        }

    def migrate_card(self, card: dict[str, Any]) -> bool:
        if _LEGACY_KEYS.isdisjoint(card):
            return False
        legacy = {key: card.pop(key) for key in _LEGACY_KEYS if key in card}
        for group, defaults in self._layout_defaults.items():
            migrated = deepcopy(defaults)
            for new_key, old_key in _LEGACY_FIELDS[group].items():
                if isinstance(legacy.get(old_key), str) and (
                    legacy[old_key] or new_key == "page_indicator_template"
                ):
                    migrated[new_key] = legacy[old_key]

            labels = _LEGACY_ROW_LABELS[group]
            rows = []
            old_count_option = legacy.get("quantity_options")
            old_count_format = legacy.get("quantity_option_template") or "开 {count} 个"
            if not isinstance(old_count_format, str):
                old_count_format = "开 {count} 个"
            if group == "quantity_menu" and old_count_option is not None:
                values = (
                    old_count_option
                    if isinstance(old_count_option, list)
                    else re.split(r"[,，;；\s]+", str(old_count_option))
                )
                counts = sorted(
                    {count for value in values if (count := _positive_count(value))}
                ) or [1]
                rows.extend(
                    f"{old_count_format.replace('{count}', str(count))},api:quantity:{count}"
                    for count in counts
                )

            for row in defaults["items"]:
                label, command = row.split(",", 1)
                if command.startswith("api:quantity:"):
                    if old_count_option is not None:
                        continue
                    label = old_count_format.replace(
                        "{count}", command.removeprefix("api:quantity:")
                    )
                else:
                    legacy_field = (
                        "cancel_label" if command == "api:nav:cancel" else labels.get(command, "")
                    )
                    custom_label = legacy.get(legacy_field)
                    if isinstance(custom_label, str) and custom_label.strip():
                        label = custom_label.strip()
                rows.append(f"{label},{command}")
            migrated["items"] = rows

            # The Dashboard may already have filled missing groups with template defaults.
            # Keep edited grouped values (including empty lists), migrate the rest once.
            current = card.get(group)
            if isinstance(current, dict):
                migrated.update(
                    {key: value for key, value in current.items() if value != defaults.get(key)}
                )
            card[group] = migrated
        return True

    def layout_for_card(
        self, card: dict[str, Any], normalize_items: Callable[[Any], list[dict[str, str]]]
    ) -> dict[str, Any]:
        layout = {}
        for group, defaults in self._layout_defaults.items():
            values = card.get(group)
            fields = {**defaults, **values} if isinstance(values, dict) else dict(defaults)
            fields["items"] = normalize_items(fields["items"])
            layout[group] = fields
        default_limit = self.template["items"]["max_concurrent_users"]["default"]
        try:
            limit = int(card.get("max_concurrent_users", default_limit))
        except (TypeError, ValueError):
            limit = default_limit
        layout["max_concurrent_users"] = limit if limit >= 0 else default_limit
        return layout

    def max_concurrent_user_flows(self, layout: dict[str, Any]) -> int | None:
        try:
            limit = int(layout.get("max_concurrent_users", 3))
        except (TypeError, ValueError):
            limit = 3
        return limit if limit > 0 else None

    def mentions_owner(self, page: dict[str, Any]) -> bool:
        state = page.get("state")
        return isinstance(state, dict) and state.get("level") == "home"

    def starts_user_flow(self, state: Any, action_id: str) -> bool:
        return isinstance(state, dict) and state.get("level") == "home" and action_id == "home:self_open"

    def options_for_card(
        self, card: dict[str, Any], layout: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if not layout:
            return {}
        type_menu, case_menu, quantity_menu = (
            layout[key] for key in ("type_menu", "case_menu", "quantity_menu")
        )
        options = {
            "type_page_title": type_menu["title"],
            "category_option_template": type_menu["option_template"],
            "cancel_reply_text": type_menu["cancel_reply_text"],
            "container_page_title_template": case_menu["title_template"],
            "page_indicator_template": case_menu["page_indicator_template"],
            "quantity_page_title_template": quantity_menu["title_template"],
        }
        for item in type_menu["items"]:
            command = item["command"]
            if command.startswith("api:category:"):
                key = _CATEGORY_LABELS.get(command.removeprefix("api:category:"))
                if key:
                    options.setdefault(key, item["label"])
        options["quantity_options"] = ",".join(
            value
            for item in quantity_menu["items"]
            if (command := item["command"]).startswith("api:quantity:")
            and _positive_count(value := command.removeprefix("api:quantity:")) is not None
        )
        return options

    def present_page(
        self, page: dict[str, Any], title: str, items: list[dict[str, str]], layout: dict[str, Any]
    ) -> tuple[str, list[dict[str, str]]]:
        state = page.get("state")
        level = state.get("level") if isinstance(state, dict) else None
        group = _PAGE_GROUPS.get(level) if isinstance(level, str) else None
        if not group or group not in layout:
            return title, items
        fields = layout[group]
        if level == "home":
            title = str(fields["title"] or title)
        configured = fields["items"]
        available = {item["api_action_id"]: item for item in items}
        explicit = {
            item["command"].removeprefix("api:")
            for item in configured
            if item["command"].startswith("api:")
        }
        result = []
        used_actions = set()
        for item in configured:
            command = item["command"]
            if command == "api:items":
                if level == "container":
                    for action, option in available.items():
                        if (
                            action.startswith("container:")
                            and action not in explicit
                            and action not in used_actions
                        ):
                            result.append(
                                {
                                    **option,
                                    "label": item["label"].replace("{item}", option["label"]),
                                    "face_id": "",
                                }
                            )
                            used_actions.add(action)
                continue
            if not command.startswith("api:"):
                result.append(item)
                continue
            action = command.removeprefix("api:")
            option = available.get(action)
            if option is None or action in used_actions:
                continue
            # Known category labels go through API v1's configured name/count template.
            formatted_category = action.removeprefix(
                "category:"
            ) in _CATEGORY_LABELS and action.startswith("category:")
            result.append(
                {
                    **option,
                    "face_id": item["face_id"],
                    "label": option["label"] if formatted_category else item["label"],
                }
            )
            used_actions.add(action)
        return title, result


SPEC = CS2ProviderSpec(
    provider_id="cs2_openweaponscase",
    plugin_id="luooka/astrbot_plugin_openweaponscase",
    display_name="CS2 开箱",
    api_versions=(1,),
    platforms=("aiocqhttp",),
    schema_path=Path(__file__).with_name("schema.json"),
    unconfigured_keywords=("开箱",),
    legacy_root_dir="astrbot_plugin_openweaponscase",
    legacy_shared_level="home",
)
