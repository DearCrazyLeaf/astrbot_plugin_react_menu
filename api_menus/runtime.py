"""Discover API providers and coordinate dynamic menu pages and actions."""

from __future__ import annotations

import inspect
import time
from dataclasses import dataclass
from itertools import count
from typing import Any

from .contract import ProviderSpec
from .registry import PROVIDERS


@dataclass
class ProviderResolution:
    plugin: Any = None
    info: dict[str, Any] | None = None
    error: str | None = None
    missing: bool = False

    @property
    def enabled(self) -> bool:
        return self.plugin is not None and bool(self.info and self.info.get("enabled"))


def platform_for_event(event: Any) -> str:
    get_platform_name = getattr(event, "get_platform_name", None)
    if callable(get_platform_name):
        try:
            platform_name = get_platform_name()
        except Exception:
            platform_name = None
        if platform_name:
            return str(platform_name).casefold()
    try:
        platform_id = event.get_platform_id()
    except Exception:
        platform_id = getattr(event, "platform_id", None)
    return str(platform_id or "").casefold()


class ApiMenuRuntime:
    def __init__(self, host: Any, logger: Any):
        self.host = host
        self.logger = logger
        self.flows: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        self._revisions = count(1)

    async def resolve(self, spec: ProviderSpec, platform: str) -> ProviderResolution:
        get_all_stars = getattr(self.host.context, "get_all_stars", None)
        if not callable(get_all_stars):
            return ProviderResolution(error="当前 AstrBot 未提供插件实例查询接口，请升级 AstrBot 后重试。")
        name = spec.display_name
        try:
            stars = get_all_stars()
        except Exception as exc:
            self.logger.warning(f"[react_menu] 查询已加载插件失败: {exc}")
            return ProviderResolution(error=f"暂时无法查询{name}插件，请稍后重试。")

        matches = []
        outdated = False
        for metadata in stars or []:
            if not getattr(metadata, "activated", False):
                continue
            plugin_id = str(getattr(metadata, "plugin_id", "") or "").casefold()
            root = str(getattr(metadata, "root_dir_name", "") or "").casefold()
            if plugin_id != spec.plugin_id.casefold() and not (
                spec.legacy_root_dir and root == spec.legacy_root_dir.casefold()
            ):
                continue
            plugin = getattr(metadata, "star_cls", None)
            if not callable(getattr(plugin, "get_interactive_menu_api_info", None)):
                outdated = True
                continue
            try:
                info = await self._call_interactive_menu_api(plugin, "get_interactive_menu_api_info")
            except Exception as exc:
                self.logger.warning(f"[react_menu] 读取{name}菜单 API 信息失败: {exc}")
                continue
            if isinstance(info, dict) and info.get("provider_id") == spec.provider_id:
                matches.append((plugin, info))

        if not matches:
            if outdated:
                return ProviderResolution(error=f"已检测到{name}插件，请更新到支持互动菜单 API 的版本。")
            return ProviderResolution(error=f"未检测到已启用的{name}插件或其 API 接口。", missing=True)
        if len(matches) != 1:
            return ProviderResolution(error=f"检测到多个相同标识的{name}接口，请检查重复安装的插件。")

        plugin, info = matches[0]
        try:
            api_version = int(info.get("api_version"))
        except (TypeError, ValueError):
            api_version = -1
        if api_version not in spec.api_versions:
            versions = "、".join(map(str, spec.api_versions))
            return ProviderResolution(error=(
                f"{name}菜单 API 版本不兼容（当前 {info.get('api_version')}，"
                f"互动菜单接受 {versions}）。请检查两个插件的版本。"
            ))
        supported = info.get("supported_platforms")
        if isinstance(supported, list) and platform not in supported:
            return ProviderResolution(error=f"{name}菜单 API 未声明支持 {platform}。")
        return ProviderResolution(plugin=plugin, info=info)

    async def try_open(
        self, event: Any, menu: dict[str, Any], group_id: str, user_id: str
    ) -> tuple[bool, str | None]:
        spec = PROVIDERS[menu["provider_id"]]
        platform = platform_for_event(event)
        if not user_id or platform not in spec.platforms:
            return False, None
        session_id = self.host._resolve_session_identity(event, group_id)
        resolved = await self.resolve(spec, platform)
        if resolved.error:
            return True, resolved.error
        if not resolved.enabled:
            return False, None
        if getattr(self.host, "menu_repeat_block", False) and self.host._has_active_menu_in_group(
            group_id, session_id, menu["menu_id"]
        ):
            self.logger.info(f"[react_menu] API 菜单冷却阻断: group={group_id}")
            return True, self.host.menu_repeat_reply
        try:
            page = await self._call_interactive_menu_api(
                resolved.plugin, "get_interactive_menu_page", None, menu.get("provider_options", {})
            )
        except Exception as exc:
            self.logger.exception(f"[react_menu] 获取{spec.display_name}菜单失败: {exc}")
            return True, f"获取{spec.display_name}菜单失败，请检查目标插件日志。"
        return True, await self._show_interactive_menu_page(
            event, user_id, group_id, spec.provider_id, page, menu
        )

    async def check_unconfigured(self, event: Any, keyword: str) -> tuple[bool, str | None]:
        platform = platform_for_event(event)
        for spec in PROVIDERS.values():
            if keyword not in spec.unconfigured_keywords or platform not in spec.platforms:
                continue
            resolved = await self.resolve(spec, platform)
            if resolved.missing or (not resolved.error and not resolved.enabled):
                return True, None
            return True, resolved.error or (
                f"{spec.display_name} API 已就绪。请在互动菜单插件的全局菜单或对应 UMO 菜单中"
                f"添加“{spec.template['name']}”模板。"
            )
        return False, None

    def expire(self, now: float, timeout: int) -> None:
        self.flows = {
            key: flow for key, flow in self.flows.items()
            if now - flow.get("updated_at", now) <= timeout
        }

    def record_sent_page(self, page: dict[str, Any]) -> bool:
        key = self._provider_flow_key(
            page["session_id"], page["owner_user_id"], page["provider_id"], page["provider_scope"]
        )
        flow = self.flows.get(key)
        if not flow or flow.get("revision") != page.get("provider_revision"):
            return False
        flow["message_id"] = page["message_id"]
        flow["updated_at"] = float(page.get("created_at", time.time()))
        return True

    @staticmethod
    def can_select(page: dict[str, Any], user_id: str) -> bool:
        return page.get("provider_scope") == "shared" or page.get("owner_user_id") == user_id

    @staticmethod
    async def _call_interactive_menu_api(plugin: Any, method_name: str, *args: Any) -> Any:
        method = getattr(plugin, method_name, None)
        if not callable(method):
            raise AttributeError(f"provider 未实现 {method_name}")
        result = method(*args)
        if inspect.isawaitable(result):
            result = await result
        return result

    @staticmethod
    def _provider_flow_key(
        session_id: str, user_id: str, provider_id: str, scope: str = "user"
    ) -> tuple[str, str, str, str]:
        flow_user_id = "" if scope == "shared" else str(user_id)
        return session_id, flow_user_id, provider_id, scope

    def is_current(self, menu_data: dict[str, Any]) -> bool:
        provider_id = str(menu_data.get("provider_id") or "")
        owner_id = str(menu_data.get("owner_user_id") or "")
        if not provider_id or not owner_id:
            return False
        key = self._provider_flow_key(
            str(menu_data.get("session_id") or ""),
            owner_id,
            provider_id,
            menu_data.get("provider_scope", "user"),
        )
        flow = self.flows.get(key)
        return bool(
            flow
            and flow.get("revision") == menu_data.get("provider_revision")
            and flow.get("message_id") == menu_data.get("message_id")
        )

    def has_active_user_flow(self, session_id: str, user_id: str, provider_id: str) -> bool:
        key = self._provider_flow_key(session_id, user_id, provider_id, "user")
        flow = self.flows.get(key)
        if flow is None:
            return False

        now = time.time()
        timeout = max(0, int(getattr(self.host, "menu_timeout", 60)))
        if not flow.get("processing") and now - flow.get("updated_at", now) > timeout:
            return False

        message_id = str(flow.get("message_id") or "")
        if not message_id:
            return True
        menu_data = self.host._active_menus.get((session_id, message_id))
        return bool(
            menu_data
            and now - menu_data.get("created_at", now)
            <= menu_data.get("timeout", timeout)
            and self.is_current(menu_data)
        )

    def _invalidate_provider_flow(
        self, session_id: str, user_id: str, provider_id: str, scope: str = "user"
    ) -> None:
        key = self._provider_flow_key(session_id, user_id, provider_id, scope)
        self.flows.pop(key, None)
        stale_keys = [
            active_key
            for active_key, data in self.host._active_menus.items()
            if data.get("session_id") == session_id
            and data.get("provider_id") == provider_id
            and data.get("provider_scope", "user") == scope
            and (scope == "shared" or data.get("owner_user_id") == str(user_id))
        ]
        for active_key in stale_keys:
            self.host._active_menus.pop(active_key, None)

    async def _delete_provider_menu_message(
        self, event: Any, menu_data: dict[str, Any]
    ) -> None:
        message_id = str(menu_data.get("message_id") or "").strip()
        bot = getattr(event, "bot", None)
        delete_message = getattr(bot, "delete_msg", None)
        if not message_id or not callable(delete_message):
            return
        try:
            parsed_id: int | str = int(message_id) if message_id.isdigit() else message_id
            result = delete_message(message_id=parsed_id)
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            self.logger.debug(f"[react_menu] 清理旧 API 菜单消息失败: {exc}")

    async def _show_interactive_menu_page(
        self,
        event: Any,
        user_id: str,
        group_id: str,
        provider_id: str,
        page_result: Any,
        menu: dict[str, Any],
    ) -> str | None:
        spec = PROVIDERS[provider_id]
        name = spec.display_name
        if not isinstance(page_result, dict):
            return f"{name}插件返回了无效菜单数据，请检查插件版本。"
        if page_result.get("kind") == "error":
            return str(page_result.get("message") or f"{name}菜单暂时不可用。")
        if page_result.get("kind") != "page" or not isinstance(page_result.get("page"), dict):
            return f"{name}插件返回了无法识别的菜单页面，请检查插件版本。"

        page = page_result["page"]
        raw_items = page.get("items")
        if not isinstance(raw_items, list) or not raw_items:
            return f"{name}插件返回了空菜单页面，请重新打开菜单。"

        page_info = page.get("page_info")
        title = str(page.get("title") or menu.get("title") or name)
        if isinstance(page_info, dict):
            current, total = page_info.get("current"), page_info.get("total")
            if current is not None and total is not None:
                options = menu.get("provider_options", {})
                indicator = str(options.get(
                    "page_indicator_template", "（第 {current}/{total} 页）"
                ) or "")
                indicator = indicator.replace("{current}", str(current)).replace("{total}", str(total))
                title = f"{title}{indicator}"

        items = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            action_id = str(raw_item.get("action_id") or "")
            label = str(raw_item.get("label") or "").strip()
            if action_id and label:
                items.append({
                    "label": label,
                    "command": "",
                    "face_id": "",
                    "api_action_id": action_id,
                })
        if not items:
            return f"{name}插件返回了无效菜单选项，请重新打开菜单。"

        layout = menu.get("provider_layout", {})
        title, items = spec.present_page(page, title, items, layout)
        if not items:
            return f"{name}菜单此页没有可用选项，请检查菜单卡片的配置。"

        session_id = self.host._resolve_session_identity(event, group_id)
        scope = spec.page_scope(page)
        flow_key = self._provider_flow_key(session_id, user_id, provider_id, scope)
        limit = spec.max_concurrent_user_flows(layout)
        if scope == "user" and limit is not None:
            now = time.time()
            timeout = max(0, int(getattr(self.host, "menu_timeout", 60)))
            current_flow = self.flows.get(flow_key)
            current_flow_is_active = bool(
                current_flow
                and (
                    current_flow.get("processing")
                    or now - current_flow.get("updated_at", now) <= timeout
                )
            )
            active_count = sum(
                1
                for key, flow in self.flows.items()
                if key[0] == session_id
                and key[2] == provider_id
                and key[3] == "user"
                and (
                    flow.get("processing")
                    or now - flow.get("updated_at", now) <= timeout
                )
            )
            if not current_flow_is_active and active_count >= limit:
                return (
                    f"⚠️ 当前群内正在使用快速开箱的人数已达上限（{limit} 人），"
                    "请稍后重试。"
                )

        previous = self.flows.get(flow_key) or {}
        revision = next(self._revisions)
        self._invalidate_provider_flow(session_id, user_id, provider_id, scope)
        flow = {
            "revision": revision,
            "updated_at": time.time(),
            "message_id": None,
            "processing": False,
        }

        self.flows[flow_key] = flow
        await self._delete_provider_menu_message(event, previous)
        if self.flows.get(flow_key) is not flow:
            return None

        api_menu = {
            "menu_id": str(menu.get("menu_id") or f"api:{provider_id}"),
            "name": str(menu.get("name") or name),
            "title": title,
            "items": items,
            "provider_id": provider_id,
            "provider_state": page.get("state"),
            "provider_options": menu.get("provider_options", {}),
            "provider_layout": layout,
            "owner_user_id": str(user_id),
            "provider_scope": scope,
            "provider_revision": revision,
        }
        owner_id = str(user_id).strip()
        if spec.mentions_owner(page) and owner_id.isdigit():
            api_menu["mention_user_id"] = owner_id
        if await self.host._send_menu(event, api_menu):
            return None

        if self.flows.get(flow_key) is flow:
            self._invalidate_provider_flow(session_id, user_id, provider_id, scope)
            return self.host._build_text_menu(api_menu)
        return None

    async def handle_selection(
        self,
        event: Any,
        user_id: str,
        group_id: str,
        menu_data: dict[str, Any],
        item: dict[str, str],
    ) -> None:
        action_id = item.get("api_action_id", "")
        command = item.get("command", "").strip()
        if not action_id and not command:
            return
        provider_id = str(menu_data.get("provider_id") or "")
        scope = menu_data.get("provider_scope", "user")
        owner_id = str(menu_data.get("owner_user_id") or "")
        if not self.can_select(menu_data, str(user_id)):
            return
        if not self.is_current(menu_data):
            self.logger.debug("[react_menu] 忽略已失效的 API 菜单操作")
            return

        flow_user_id = owner_id if scope == "shared" else user_id
        flow_key = self._provider_flow_key(
            menu_data["session_id"], flow_user_id, provider_id, scope
        )
        flow = self.flows.get(flow_key)
        if flow is None:
            return
        if flow.get("processing"):
            return
        flow["processing"] = True

        spec = PROVIDERS[provider_id]
        name = spec.display_name
        platform = platform_for_event(event)
        if platform not in spec.platforms:
            flow["processing"] = False
            return
        resolved = await self.resolve(spec, platform)
        if self.flows.get(flow_key) is not flow:
            return
        if resolved.error or not resolved.enabled:
            self._invalidate_provider_flow(
                menu_data["session_id"], flow_user_id, provider_id, scope
            )
            await self._delete_provider_menu_message(event, menu_data)
            await event.send(event.plain_result(
                resolved.error or f"{name}互动菜单 API 已关闭，请在目标插件配置中重新开启。"
            ))
            return

        if (
            getattr(self.host, "menu_repeat_block", False)
            and spec.starts_user_flow(menu_data.get("provider_state"), action_id)
            and self.has_active_user_flow(menu_data["session_id"], user_id, provider_id)
        ):
            flow["processing"] = False
            await event.send(event.plain_result(self.host.menu_repeat_reply))
            return

        if not action_id:
            try:
                await self.host._execute_as_user(event, user_id, group_id, command)
            finally:
                if self.flows.get(flow_key) is flow:
                    flow["processing"] = False
            return

        try:
            result = await self._call_interactive_menu_api(
                resolved.plugin,
                "handle_interactive_menu_action",
                menu_data.get("provider_state"),
                action_id,
                menu_data.get("provider_options", {}),
            )
        except Exception as exc:
            self.logger.exception(f"[react_menu] 执行 {name}菜单操作失败: {exc}")
            if self.flows.get(flow_key) is not flow:
                return
            self._invalidate_provider_flow(
                menu_data["session_id"], flow_user_id, provider_id, scope
            )
            await self._delete_provider_menu_message(event, menu_data)
            await event.send(event.plain_result(f"{name}菜单操作失败，请重新打开菜单。"))
            return

        if self.flows.get(flow_key) is not flow:
            return

        if isinstance(result, dict) and result.get("kind") == "page":
            fallback = await self._show_interactive_menu_page(
                event,
                user_id,
                group_id,
                provider_id,
                result,
                {
                    "menu_id": menu_data.get("menu_id"),
                    "name": menu_data.get("menu_id"),
                    "title": name,
                    "provider_options": menu_data.get("provider_options", {}),
                    "provider_layout": menu_data.get("provider_layout", {}),
                },
            )
            if fallback:
                await event.send(event.plain_result(fallback))
            if self.flows.get(flow_key) is flow:
                flow["processing"] = False
            return

        if isinstance(result, dict) and result.get("kind") == "command" and result.get("keep_menu"):
            command = str(result.get("command") or "").strip()
            if command:
                try:
                    await self.host._dispatch_native_command(
                        event, user_id, group_id, command
                    )
                finally:
                    if self.flows.get(flow_key) is flow:
                        flow["processing"] = False
                return
            flow["processing"] = False
            await event.send(event.plain_result(f"{name}插件未返回原生指令。"))
            return

        self._invalidate_provider_flow(
            menu_data["session_id"], flow_user_id, provider_id, scope
        )
        await self._delete_provider_menu_message(event, menu_data)
        if isinstance(result, dict) and result.get("kind") == "command":
            command = str(result.get("command") or "").strip()
            if command:
                await self.host._dispatch_native_command(event, user_id, group_id, command)
                return
            message = f"{name}插件未返回原生指令。"
        elif isinstance(result, dict) and result.get("kind") == "cancel":
            message = str(result.get("message") or f"已取消{name}菜单。")
        elif isinstance(result, dict) and result.get("kind") == "error":
            message = str(result.get("message") or f"{name}菜单操作无效，请重新打开菜单。")
        else:
            message = f"{name}插件返回了无法识别的操作结果，请重新打开菜单。"
        await event.send(event.plain_result(message))
