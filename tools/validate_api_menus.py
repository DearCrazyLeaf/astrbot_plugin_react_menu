"""Validate registered API menu providers and their templates."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PROVIDER_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
REQUIRED_TEMPLATE_FIELDS = ("menu_id", "name", "keywords", "provider_id")


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _registered_providers() -> dict[str, Any]:
    from api_menus.registry import PROVIDERS

    return PROVIDERS


def _validate_string_field(fields: dict[str, Any], key: str, errors: list[str]) -> None:
    field = fields.get(key)
    if not isinstance(field, dict) or field.get("type") != "string":
        errors.append(f"items.{key} 必须是 type=string 的字段")


def _validate_keywords_field(fields: dict[str, Any], errors: list[str]) -> None:
    field = fields.get("keywords")
    if not isinstance(field, dict) or field.get("type") != "list":
        errors.append("items.keywords 必须是 type=list 的字段")
        return
    item_schema = field.get("items")
    if not isinstance(item_schema, dict) or item_schema.get("type") != "string":
        errors.append("items.keywords.items 必须是 type=string 的字段")
    default = field.get("default")
    if not isinstance(default, list) or not default or not all(
        _is_non_empty_string(value) for value in default
    ):
        errors.append("items.keywords.default 必须是非空字符串列表")


def validate_provider(registry_key: str, spec: Any) -> list[str]:
    errors: list[str] = []
    provider_id = str(getattr(spec, "provider_id", "") or "").strip()
    prefix = f"{registry_key}:"

    if registry_key != provider_id:
        errors.append(f"{prefix} registry key 必须等于 provider_id {provider_id!r}")
    if not PROVIDER_ID_PATTERN.fullmatch(provider_id):
        errors.append(
            f"{prefix} provider_id 只能使用小写字母、数字、下划线和连字符，且必须以字母或数字开头"
        )

    plugin_id = str(getattr(spec, "plugin_id", "") or "").strip()
    if not plugin_id or plugin_id.count("/") != 1 or any(char.isspace() for char in plugin_id):
        errors.append(f"{prefix} plugin_id 必须是 author/name 形式，且不能包含空白")

    if not _is_non_empty_string(getattr(spec, "display_name", "")):
        errors.append(f"{prefix} display_name 必须是非空字符串")

    versions = getattr(spec, "api_versions", ())
    if not versions or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in versions):
        errors.append(f"{prefix} api_versions 必须是非空正整数序列")
    elif len(set(versions)) != len(versions):
        errors.append(f"{prefix} api_versions 不能重复")

    raw_platforms = tuple(str(value).strip() for value in getattr(spec, "platforms", ()))
    platforms = tuple(value.casefold() for value in raw_platforms)
    if not platforms or any(not value for value in platforms):
        errors.append(f"{prefix} platforms 必须是非空平台标识序列")
    elif len(set(platforms)) != len(platforms):
        errors.append(f"{prefix} platforms 不能重复")
    elif raw_platforms != platforms:
        errors.append(f"{prefix} platforms 必须使用小写平台标识")

    schema_path = Path(getattr(spec, "schema_path", ""))
    if not schema_path.is_file():
        errors.append(f"{prefix} schema_path 不存在：{schema_path}")
        return errors

    try:
        template = spec.template
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        errors.append(f"{prefix} schema.json 不是有效 JSON：{exc}")
        return errors

    if not isinstance(template, dict):
        errors.append(f"{prefix} schema.json 根对象必须是 object")
        return errors
    if not _is_non_empty_string(template.get("name")):
        errors.append(f"{prefix} schema.json 必须包含非空 name")
    display_item = template.get("display_item")
    fields = template.get("items")
    if not _is_non_empty_string(display_item):
        errors.append(f"{prefix} schema.json 必须包含非空 display_item")
    if not isinstance(fields, dict):
        errors.append(f"{prefix} schema.json.items 必须是 object")
        return errors
    if display_item and display_item not in fields:
        errors.append(f"{prefix} display_item 必须引用 schema.json.items 中的字段")

    for key in REQUIRED_TEMPLATE_FIELDS:
        if key not in fields:
            errors.append(f"{prefix} 缺少必需字段 items.{key}")
    _validate_string_field(fields, "menu_id", errors)
    _validate_string_field(fields, "name", errors)
    _validate_string_field(fields, "provider_id", errors)
    _validate_keywords_field(fields, errors)

    provider_field = fields.get("provider_id")
    if isinstance(provider_field, dict):
        if provider_field.get("default") != provider_id:
            errors.append(f"{prefix} items.provider_id.default 必须等于 provider_id")
        if provider_field.get("invisible") is not True:
            errors.append(f"{prefix} items.provider_id 必须设置 invisible=true")

    menu_id_field = fields.get("menu_id")
    if isinstance(menu_id_field, dict):
        if menu_id_field.get("default") != provider_id:
            errors.append(f"{prefix} items.menu_id.default 应与 provider_id 保持一致")
        if menu_id_field.get("invisible") is not True:
            errors.append(f"{prefix} items.menu_id 必须设置 invisible=true")

    if "umo" in fields:
        errors.append(f"{prefix} schema.json 不应声明 items.umo，UMO 字段由同步脚本添加")

    return errors


def validate_registry() -> list[str]:
    errors: list[str] = []
    normalized_ids: dict[str, str] = {}
    registered_schema_paths: set[Path] = set()

    for registry_key, spec in _registered_providers().items():
        normalized_id = str(registry_key).casefold()
        if normalized_id in normalized_ids:
            errors.append(
                f"provider_id 重复：{registry_key} 与 {normalized_ids[normalized_id]} 仅大小写不同"
            )
        else:
            normalized_ids[normalized_id] = registry_key
        schema_path = Path(getattr(spec, "schema_path", ""))
        registered_schema_paths.add(schema_path.resolve())
        errors.extend(validate_provider(registry_key, spec))

    provider_root = ROOT / "api_menus" / "providers"
    for schema_path in provider_root.glob("*/schema.json"):
        if schema_path.resolve() not in registered_schema_paths:
            errors.append(f"发现未注册的 API 菜单模板：{schema_path}")
    return errors


def validate_sync() -> list[str]:
    from tools.sync_menu_schema import sync_templates

    schema_path = ROOT / "_conf_schema.json"
    try:
        original = json.loads(schema_path.read_text(encoding="utf-8"))
        updated = sync_templates(original)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return [f"无法检查 _conf_schema.json 同步状态：{exc}"]
    if updated != original:
        return ["_conf_schema.json 与已注册 API 菜单模板不同，请运行 python tools/sync_menu_schema.py"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-sync", action="store_true", help="同时检查 _conf_schema.json 是否同步")
    args = parser.parse_args()

    errors = validate_registry()
    if args.check_sync:
        errors.extend(validate_sync())
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("API menu providers and templates are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
