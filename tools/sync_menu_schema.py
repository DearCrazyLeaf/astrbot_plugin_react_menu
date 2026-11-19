"""Sync the registered API menu templates into AstrBot's root schema."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def sync_templates(schema: dict[str, Any]) -> dict[str, Any]:
    from api_menus.registry import PROVIDERS

    updated = copy.deepcopy(schema)
    menu_settings = updated["global_settings"]["items"]
    umo_field = menu_settings["umo_menus"]["templates"]["menu"]["items"]["umo"]
    for collection in ("menus", "umo_menus"):
        templates = menu_settings[collection]["templates"]
        # Preserve hand-maintained static cards and rebuild the provider cards.
        templates = {
            key: template for key, template in templates.items()
            if "provider_id" not in template["items"] and key not in PROVIDERS
        }
        for provider_id, spec in PROVIDERS.items():
            template = copy.deepcopy(spec.template)
            fields = template["items"]
            if fields.get("provider_id", {}).get("default") != provider_id:
                raise ValueError(f"{spec.schema_path}: provider_id 默认值应为 {provider_id}")
            if "umo" in fields:
                raise ValueError(f"{spec.schema_path}: umo 字段由同步脚本添加")
            if collection == "umo_menus":
                template["items"] = {"umo": copy.deepcopy(umo_field), **fields}
            templates[provider_id] = template
        menu_settings[collection]["templates"] = templates
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check only, without writing the schema")
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT))
    schema_path = ROOT / "_conf_schema.json"
    original = json.loads(schema_path.read_text(encoding="utf-8"))
    updated = sync_templates(original)
    if updated == original:
        print("API menu templates are in sync.")
        return 0
    if args.check:
        print("API menu templates differ. Run python tools/sync_menu_schema.py.", file=sys.stderr)
        return 1
    schema_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Updated _conf_schema.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
