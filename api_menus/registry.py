"""Built-in adapters, keyed by their stable provider IDs."""

from typing import Any

from .contract import ProviderSpec
from .providers.cs2_openweaponscase import SPEC as CS2_SPEC


def _build_registry(specs: tuple[ProviderSpec, ...]) -> dict[str, ProviderSpec]:
    providers: dict[str, ProviderSpec] = {}
    normalized_ids: dict[str, str] = {}
    for spec in specs:
        normalized_id = spec.provider_id.casefold()
        if normalized_id in normalized_ids:
            raise ValueError(f"重复注册菜单 API：{spec.provider_id}")
        providers[spec.provider_id] = spec
        normalized_ids[normalized_id] = spec.provider_id
    return providers


PROVIDERS = _build_registry((CS2_SPEC,))


def provider_for_card(card: dict[str, Any]) -> ProviderSpec | None:
    template_key = str(card.get("__template_key") or "").strip()
    explicit_id = str(card.get("provider_id") or "").strip()
    return PROVIDERS.get(template_key) or PROVIDERS.get(explicit_id)
