from pathlib import Path

import pytest

from api_menus.contract import ProviderSpec
from api_menus.registry import _build_registry
from tools.validate_api_menus import validate_registry, validate_sync


def _spec(provider_id):
    return ProviderSpec(
        provider_id=provider_id,
        plugin_id="author/example",
        display_name="示例",
        api_versions=(1,),
        platforms=("aiocqhttp",),
        schema_path=Path(__file__).parents[1]
        / "api_menus/providers/cs2_openweaponscase/schema.json",
    )


def test_registered_api_menu_contracts_are_valid():
    assert validate_registry() == []


def test_generated_schema_is_in_sync():
    assert validate_sync() == []


def test_provider_ids_are_unique_case_insensitively():
    with pytest.raises(ValueError, match="重复注册菜单 API"):
        _build_registry((_spec("example_plugin"), _spec("EXAMPLE_PLUGIN")))
