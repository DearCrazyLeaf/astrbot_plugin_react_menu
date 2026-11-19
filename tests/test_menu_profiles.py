"""Offline behavior checks, without importing AstrBot or contacting OneBot."""

import ast
import asyncio
import copy
from importlib import import_module
import json
import random
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch


ROOT = Path(__file__).resolve().parents[1]


def load_plugin():
    # Execute the actual plugin class and constants; only replace framework imports.
    source = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
    body = [ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)]
    body += [
        node for node in source.body
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.ClassDef))
        or (isinstance(node, ast.ImportFrom) and node.level > 0)
    ]
    namespace = {
        "__package__": ROOT.name,
        "asyncio": asyncio, "json": json, "random": random, "time": time,
        "logger": Mock(), "Star": type("Star", (), {"__init__": lambda self, context: None}),
        "StarTools": SimpleNamespace(get_data_dir=lambda name: None),
        "AstrBotMessage": SimpleNamespace, "MessageMember": SimpleNamespace,
        "Plain": lambda text: SimpleNamespace(text=text), "MessageChain": list,
        "filter": SimpleNamespace(
            event_message_type=lambda value: lambda method: method,
            EventMessageType=SimpleNamespace(GROUP_MESSAGE=1, ALL=2),
        ),
    }
    sys.path.insert(0, str(ROOT.parent))
    try:
        exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])), str(ROOT / "main.py"), "exec"), namespace)
    finally:
        sys.path.pop(0)
    return namespace["ReactMenuPlugin"]


Plugin = load_plugin()

api_runtime = import_module(f"{ROOT.name}.api_menus.runtime")
PROVIDERS = api_runtime.PROVIDERS
platform_for_event = api_runtime.platform_for_event
ProviderSpec = api_runtime.ProviderSpec

A = "adapter-a:GroupMessage:123"
B = "adapter-b:GroupMessage:123"
C = "adapter-c:GroupMessage:123"


def menu(keyword, command, umo=None):
    result = {"__template_key": "menu", "name": command, "title": command,
              "keywords": [keyword], "items": [{"label": command, "command": command, "face_id": "14"}]}
    if umo is not None:
        result["umo"] = umo
    return result


def config(entries=None):
    return {"global_settings": {"menus": [menu("global", "global_cmd")], "umo_menus": entries or []}}


def profile(data):
    obj = Plugin.__new__(Plugin)
    obj.config = data
    obj._load_menu_profiles()
    return obj


class ProfileTests(unittest.TestCase):
    def test_empty_list_uses_global_for_every_instance(self):
        obj = profile(config())
        for umo in (A, B, C):
            self.assertEqual(obj._menu_for_session_keyword(umo, "global")["name"], "global_cmd")

    def test_same_umo_combines_cards_and_instances_remain_separate(self):
        obj = profile(config([menu("open", "first", A), menu("tools", "second", A), menu("open", "third", B)]))
        self.assertEqual(len(obj.session_menus[A]), 2)
        self.assertEqual(obj._menu_for_session_keyword(A, "open")["name"], "first")
        self.assertEqual(obj._menu_for_session_keyword(A, "/tools")["name"], "second")
        self.assertEqual(obj._menu_for_session_keyword(B, "open")["name"], "third")
        self.assertIsNone(obj._menu_for_session_keyword(A, "global"))
        self.assertIsNone(obj._menus_for_session(C))

    def test_invalid_or_empty_cards_never_enable_global(self):
        for entries in ([{"umo": "invalid"}], [{"umo": A, "items": []}], [None]):
            obj = profile(config(entries))
            self.assertIsNone(obj._menu_for_session_keyword(C, "global"))
            self.assertFalse(obj._menus_for_session(A))

    def test_duplicate_keywords_are_scoped_to_umo(self):
        obj = profile(config([menu("/Open", "first", A), menu("open", "second", A), menu("OPEN", "third", B)]))
        self.assertEqual(len(obj.session_menus[A]), 1)
        self.assertEqual(obj._menu_for_session_keyword(B, "open")["name"], "third")

    def test_cs2_provider_keyword_takes_precedence_over_static_menu(self):
        api_menu = {"__template_key": "cs2_openweaponscase", "name": "CS2 开箱",
                    "keywords": ["开箱"], "title": "CS2 开箱", "items": []}
        static_menu = menu("开箱", "static_open")
        obj = profile({"global_settings": {"menus": [static_menu, api_menu], "umo_menus": []}})
        self.assertEqual(obj._menu_for_session_keyword(A, "开箱")["provider_id"], "cs2_openweaponscase")
        self.assertIsNone(obj._menu_for_session_keyword(A, "static_open"))

    def test_nested_migration_is_saved_once_and_not_resurrected(self):
        class SavedConfig(dict):
            save_config = Mock()
        data = SavedConfig(config())
        data["session_settings"] = {"sessions": [
            {"umo": A, "menus": [menu("one", "first"), menu("two", "second")]},
            {"umo": B, "menus": []},
        ]}
        obj = profile(data)
        self.assertEqual(len(obj.session_menus[A]), 2)
        self.assertEqual(obj.session_menus[B], [])
        self.assertEqual(data["session_settings"]["sessions"], [])
        data.save_config.assert_called_once()
        data["global_settings"]["umo_menus"] = []
        self.assertFalse(profile(data)._umo_mode)
        data.save_config.assert_called_once()

    def test_old_global_menu_is_visible_and_consumed(self):
        schema = json.loads((ROOT / "_conf_schema.json").read_text(encoding="utf-8"))
        data = {"global_settings": {"menus": copy.deepcopy(schema["global_settings"]["items"]["menus"]["default"])},
                "menus": copy.deepcopy(schema["global_settings"]["items"]["menus"]["default"]),
                "menu_keywords": ["old"], "menu_title": "old title", "menu_items": ["old label,old_cmd"]}
        self.assertEqual(profile(data)._menu_for_session_keyword(A, "old")["title"], "old title")
        self.assertEqual(data["menu_items"], [])
        data["global_settings"]["menus"] = []
        self.assertEqual(profile(data).global_menus, [])

    def test_object_items_are_migrated_to_simple_strings(self):
        class SavedConfig(dict):
            save_config = Mock()

        data = SavedConfig({
            "global_settings": {
                "menus": [{
                    "name": "旧菜单",
                    "keywords": ["菜单"],
                    "title": "旧菜单",
                    "items": [
                        {"label": "每日老婆", "command": "抽老婆", "face_id": "14"},
                        {"label": "今日小猪", "command": "今日小猪", "face_id": ""},
                    ],
                }],
                "umo_menus": [],
            }
        })
        obj = profile(data)
        self.assertEqual(
            data["global_settings"]["menus"][0]["items"],
            ["每日老婆,抽老婆,14", "今日小猪"],
        )
        self.assertEqual(obj.global_menus[0]["items"][0]["face_id"], "14")
        data.save_config.assert_called_once()
        profile(data)
        data.save_config.assert_called_once()

    def test_simple_item_syntax_preserves_command_and_face_id(self):
        obj = profile(config([{
            **menu("open", "unused", A),
            "items": ["显示名称,实际指令,66", "相同内容"],
        }]))
        self.assertEqual(obj.session_menus[A][0]["items"], [
            {"label": "显示名称", "command": "实际指令", "face_id": "66"},
            {"label": "相同内容", "command": "相同内容", "face_id": ""},
        ])

    def test_unicode_emoji_prefix_becomes_onebot_emoji_id(self):
        obj = Plugin.__new__(Plugin)
        items = obj._normalize_menu_items([
            "🍚 今天吃啥,吃什么",
            "☕️ 咖啡,咖啡",
            "👍🏻 点赞,点赞",
            "第二项,second",
        ])
        self.assertEqual(items, [
            {"label": "🍚 今天吃啥", "command": "吃什么", "face_id": "127834"},
            {"label": "☕️ 咖啡", "command": "咖啡", "face_id": "9749"},
            {"label": "👍🏻 点赞", "command": "点赞", "face_id": "128077"},
            {"label": "第二项", "command": "second", "face_id": ""},
        ])
        self.assertEqual(obj._match_menu_item("今天吃啥", items)["command"], "吃什么")

    def test_unicode_emoji_in_face_pool_is_normalized(self):
        obj = Plugin.__new__(Plugin)
        self.assertEqual(obj._normalize_face_pool(["🍚", "14", "🍚"]), ["127834", "14"])

    def test_explicit_unicode_emoji_stays_in_item_order_before_random_pool(self):
        obj = Plugin.__new__(Plugin)
        obj.face_pool = ["14", "66"]
        items = obj._normalize_menu_items(["🍚 米饭,rice", "第二项,second", "第三项,third"])
        assigned = obj._assign_face_ids(items)
        self.assertEqual(assigned[0]["face_id"], "127834")
        self.assertEqual([item["label"] for item in assigned], ["🍚 米饭", "第二项", "第三项"])
        self.assertEqual(len({item["face_id"] for item in assigned}), 3)

    def test_schema_contains_only_one_card_level(self):
        schema = json.loads((ROOT / "_conf_schema.json").read_text(encoding="utf-8"))
        section = schema["global_settings"]["items"]
        self.assertEqual(list(section), ["menus", "umo_menus"])
        for key in section:
            self.assertEqual(section[key]["type"], "template_list")
            fields = section[key]["templates"]["menu"]["items"]
            self.assertNotIn("template_list", [field["type"] for field in fields.values()])
            self.assertEqual(fields["items"]["items"]["type"], "string")
            for entry in section[key]["default"]:
                self.assertTrue(all(isinstance(item, str) for item in entry["items"]))
        self.assertEqual(section["umo_menus"]["templates"]["menu"]["items"]["umo"]["type"], "string")
        self.assertIn("cs2_openweaponscase", section["menus"]["templates"])
        self.assertIn("cs2_openweaponscase", section["umo_menus"]["templates"])
        self.assertEqual(
            section["menus"]["templates"]["cs2_openweaponscase"]["items"]["keywords"]["default"],
            ["开箱"],
        )
        for key in section:
            fields = section[key]["templates"]["cs2_openweaponscase"]["items"]
            self.assertNotIn("capsule_label", fields)
            for group in ("home_menu", "type_menu", "case_menu", "quantity_menu"):
                self.assertEqual(fields[group]["type"], "object")
                self.assertEqual(fields[group]["items"]["items"]["items"]["type"], "string")
            self.assertEqual(fields["type_menu"]["items"]["items"]["default"], [
                "武器箱,api:category:case", "纪念包,api:category:souvenir", "收藏品,api:category:collection", "取消选择,api:nav:cancel",
            ])
            quantity = fields["quantity_menu"]["items"]
            self.assertEqual(quantity["title_template"]["default"], "选择开箱数量：{item}")
            self.assertEqual(quantity["items"]["default"][:5], [f"开 {n} 个,api:quantity:{n}" for n in (1, 5, 10, 20, 50)])
        provider_template = PROVIDERS["cs2_openweaponscase"].template["items"]
        for group in ("home_menu", "type_menu", "case_menu", "quantity_menu"):
            for field in provider_template[group]["items"].values():
                hint = field.get("hint", "")
                self.assertNotIn("。", hint)
                self.assertNotIn(".", hint)
        self.assertTrue(schema["session_settings"]["invisible"])


    def test_cs2_flat_options_migrate_once_even_if_webui_prepopulated_defaults(self):
        class SavedConfig(dict):
            save_config = Mock()

        template = PROVIDERS["cs2_openweaponscase"].template["items"]
        card = {
            "__template_key": "cs2_openweaponscase", "keywords": ["开箱"], "umo": A,
            "title": "我的开箱", "inventory_label": "我的库存", "capsule_label": "旧选项",
            "quantity_options": "8,2", "quantity_option_template": "抽 {count} 次", "cancel_label": "退出",
            "next_page_label": "继续翻页", "page_indicator_template": "",
            "home_menu": {key: copy.deepcopy(field["default"]) for key, field in template["home_menu"]["items"].items()},
            "type_menu": {"items": []},
        }
        data = SavedConfig(config([card]))
        obj = profile(data)
        self.assertEqual(card["home_menu"]["title"], "我的开箱")
        self.assertIn("我的库存,库存", card["home_menu"]["items"])
        self.assertEqual(card["type_menu"]["items"], [])
        self.assertEqual(card["case_menu"]["page_indicator_template"], "")
        self.assertIn("继续翻页,api:nav:next", card["case_menu"]["items"])
        self.assertEqual(card["quantity_menu"]["items"], [
            "抽 2 次,api:quantity:2", "抽 8 次,api:quantity:8", "返回箱子选择,api:nav:back", "退出,api:nav:cancel",
        ])
        self.assertNotIn("capsule_label", card)
        self.assertNotIn("quantity_options", card)
        self.assertEqual(obj.session_menus[A][0]["provider_options"]["quantity_options"], "2,8")
        card["quantity_menu"]["items"] = []
        obj._load_menu_profiles()
        self.assertEqual(card["quantity_menu"]["items"], [])
        data.save_config.assert_called_once()


class OptionMigrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_values_survive_group_defaults_and_save_only_once(self):
        class SavedConfig(dict):
            save_config = Mock()

        schema = json.loads((ROOT / "_conf_schema.json").read_text(encoding="utf-8"))
        data = SavedConfig(config())
        # Keep this test focused on option migration; item migration is tested above.
        data["global_settings"]["menus"][0]["items"] = ["global_cmd,global_cmd,14"]
        for name in ("interaction_settings", "appearance_settings", "reaction_settings"):
            data[name] = {key: copy.deepcopy(field["default"]) for key, field in schema[name]["items"].items()}
        data.update(menu_timeout_seconds=120, debounce_seconds=0, menu_repeat_block=False,
                    menu_repeat_reply="", menu_header_image_url="https://example.com/menu.png",
                    menu_divider_char="=", menu_divider_length=12, menu_footer_text="custom footer",
                    menu_max_reactions=0, face_pool=["14", "66"])
        obj = Plugin(None, data)
        obj._cleanup_task.cancel()
        await asyncio.gather(obj._cleanup_task, return_exceptions=True)
        self.assertEqual(obj.menu_timeout, 120)
        self.assertEqual(obj.debounce_seconds, 0)
        self.assertFalse(obj.menu_repeat_block)
        self.assertEqual(obj.menu_repeat_reply, "")
        self.assertEqual(obj.menu_header_image_url, "https://example.com/menu.png")
        self.assertEqual(obj.menu_divider_char, "=")
        self.assertEqual(obj.menu_divider_length, 12)
        self.assertEqual(obj.menu_footer_text, "custom footer")
        self.assertEqual(obj.menu_max_reactions, 0)
        self.assertEqual(obj.face_pool, ["14", "66"])
        data.save_config.assert_called_once()
        # A later WebUI change must win over any retained legacy fields.
        data["appearance_settings"]["menu_footer_text"] = ""
        data["menu_footer_text"] = "stale legacy footer"
        obj = Plugin(None, data)
        obj._cleanup_task.cancel()
        await asyncio.gather(obj._cleanup_task, return_exceptions=True)
        self.assertEqual(obj.menu_footer_text, "")
        data.save_config.assert_called_once()

    async def test_new_grouped_config_uses_values_without_legacy_options(self):
        data = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        obj = Plugin(None, data)
        obj._cleanup_task.cancel()
        await asyncio.gather(obj._cleanup_task, return_exceptions=True)
        self.assertEqual(obj.menu_timeout, data["interaction_settings"]["menu_timeout_seconds"])
        self.assertEqual(obj.menu_footer_text, data["appearance_settings"]["menu_footer_text"])
        self.assertEqual(obj.face_pool, data["reaction_settings"]["face_pool"])


class EventTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.obj = Plugin(None, config([menu("one", "first", A), menu("two", "second", A), menu("one", "third", B)]))
        self.obj._send_menu = AsyncMock(return_value=True)
        self.obj._execute_as_user = AsyncMock()

    async def asyncTearDown(self):
        self.obj._cleanup_task.cancel()
        await asyncio.gather(self.obj._cleanup_task, return_exceptions=True)

    @staticmethod
    def event(umo, text="", raw=None):
        return SimpleNamespace(
            get_platform_id=lambda: umo.split(":", 1)[0], get_group_id=lambda: "123",
            get_sender_id=lambda: "42", message_str=text, unified_msg_origin=umo,
            message_obj=SimpleNamespace(raw_message=raw or {}, message_id="input", self_id="999"),
            stop_event=Mock(), plain_result=lambda text: text, send=AsyncMock(),
        )

    async def test_real_group_handler_dispatches_and_blocks_unregistered_umo(self):
        for umo, word in ((A, "one"), (A, "two"), (B, "one"), (C, "one"), (A, "global")):
            _ = [result async for result in self.obj.on_group_message(self.event(umo, word))]
        self.assertEqual([call.args[1]["name"] for call in self.obj._send_menu.await_args_list], ["first", "second", "third"])

    async def test_reactions_resolve_original_message_and_platform_instance(self):
        for umo, mid, command in ((A, "10", "first"), (A, "11", "second"), (B, "10", "third")):
            self.obj._active_menus[(umo, mid)] = {"created_at": time.time() - 3, "timeout": 60,
                "emoji_map": {"14": {"command": command}}}
        for umo, mid in ((A, "10"), (A, "11"), (B, "10"), (C, "10")):
            raw = {"notice_type": "group_msg_reaction", "group_id": "123", "message_id": mid,
                   "user_id": "42", "emoji_id": "14", "self_id": "999"}
            event = self.event(umo, raw=raw)
            event.unified_msg_origin = "incorrect:OtherMessage:notice"
            await self.obj._handle_reaction_event(event)
        self.assertEqual([call.args[-1] for call in self.obj._execute_as_user.await_args_list], ["/first", "/second", "/third"])


class NavigationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.parent = {**menu("main", "parent", A),
                       "items": ["更多功能,/TOOLS,14", "外部功能,external_cmd,66", "返回本页,main,5"]}
        self.child = {**menu("tools", "child A", A), "items": ["返回主菜单,main,14"]}
        self.platform = SimpleNamespace(
            create_event=Mock(side_effect=self.virtual_event), commit_event=Mock(),
        )
        self.context = SimpleNamespace(
            get_platform_inst=Mock(return_value=self.platform), send_message=AsyncMock(),
        )
        self.obj = Plugin(self.context, config([self.parent, self.child, menu("tools", "child B", B)]))
        self.obj._send_menu = AsyncMock(return_value=True)
        self.activate(A, "10", self.obj._menu_for_session_keyword(A, "main"))

    async def asyncTearDown(self):
        self.obj._cleanup_task.cancel()
        await asyncio.gather(self.obj._cleanup_task, return_exceptions=True)

    @staticmethod
    def virtual_event(message):
        event = EventTests.event(A, message.message_str)
        event.message_obj = message
        return event

    def activate(self, umo, mid, selected_menu):
        self.obj._active_menus[(umo, mid)] = {
            "group_id": "123", "session_id": umo, "menu_id": selected_menu["menu_id"],
            "created_at": time.time() - 3, "timeout": 60, "items": selected_menu["items"],
            "emoji_map": {item["face_id"]: item for item in selected_menu["items"] if item["face_id"]},
        }

    @staticmethod
    def reaction(umo, mid="10"):
        return EventTests.event(umo, raw={
            "notice_type": "group_msg_reaction", "group_id": "123", "message_id": mid,
            "user_id": "42", "emoji_id": "14", "self_id": "999",
        })

    async def test_text_selections_open_submenu_without_virtual_events(self):
        for text in ("1", "更多功能"):
            event = EventTests.event(A, text)
            self.assertEqual([reply async for reply in self.obj.on_group_message(event)], [])
            self.assertEqual(self.obj._send_menu.await_args.args[1]["name"], "child A")
            event.stop_event.assert_called()
        self.assertEqual(self.obj._send_menu.await_count, 2)
        self.platform.commit_event.assert_not_called()
        self.assertEqual(self.obj._recent_virtual_commands, {})

    async def test_reactions_open_submenu_in_the_original_umo(self):
        self.activate(B, "10", self.obj._normalize_menus([self.parent])[0])
        for umo in (A, B, C):
            await self.obj._handle_reaction_event(self.reaction(umo))
        self.assertEqual([call.args[1]["name"] for call in self.obj._send_menu.await_args_list],
                         ["child A", "child B"])
        self.platform.commit_event.assert_not_called()

    async def test_global_menus_can_navigate(self):
        self.obj.config = {"global_settings": {"menus": [self.parent, self.child], "umo_menus": []}}
        self.obj._load_menu_profiles()
        self.activate(C, "10", self.obj._menu_for_session_keyword(C, "main"))
        event = EventTests.event(C, "更多功能")
        _ = [reply async for reply in self.obj.on_group_message(event)]
        self.assertEqual(self.obj._send_menu.await_args.args[1]["name"], "child A")
        self.platform.commit_event.assert_not_called()

    async def test_submenu_uses_the_same_cooldown_as_direct_open(self):
        self.activate(A, "11", self.obj._menu_for_session_keyword(A, "tools"))
        # Text and reaction selection still refer to the original parent menu.
        self.obj._active_menus[(A, "10")]["created_at"] = time.time() - 2
        text_event = EventTests.event(A, "1")
        self.assertEqual([reply async for reply in self.obj.on_group_message(text_event)], [])
        text_event.send.assert_awaited_once_with(self.obj.menu_repeat_reply)
        reaction = self.reaction(A)
        await self.obj._handle_reaction_event(reaction)
        reaction.send.assert_awaited_once_with(self.obj.menu_repeat_reply)
        direct = EventTests.event(A, "tools")
        self.assertEqual([reply async for reply in self.obj.on_group_message(direct)], [self.obj.menu_repeat_reply])
        self.obj._send_menu.assert_not_awaited()
        self.platform.commit_event.assert_not_called()

    async def test_submenu_sends_plain_text_fallback(self):
        self.obj._send_menu.return_value = False
        expected = self.obj._build_text_menu(self.obj._menu_for_session_keyword(A, "tools"))
        for event in (EventTests.event(A, "1"), self.reaction(A)):
            if event.message_str:
                _ = [reply async for reply in self.obj.on_group_message(event)]
            else:
                await self.obj._handle_reaction_event(event)
            event.send.assert_awaited_once_with(expected)
        self.platform.commit_event.assert_not_called()

    async def test_external_commands_still_use_virtual_events_and_loop_guard(self):
        event = EventTests.event(A, "2")
        _ = [reply async for reply in self.obj.on_group_message(event)]
        self.platform.commit_event.assert_called_once()
        virtual = self.platform.commit_event.call_args.args[0]
        message = virtual.message_obj
        self.assertEqual((message.sender.user_id, message.group_id, message.message_str),
                         ("42", "123", "/external_cmd"))
        self.assertTrue(message.raw_message["_react_menu_internal"])
        _ = [reply async for reply in self.obj.on_group_message(virtual)]
        self.platform.commit_event.assert_called_once()
        self.obj._send_menu.assert_not_awaited()

    async def test_self_reference_and_return_links_do_not_recurse(self):
        self.obj.menu_repeat_block = False
        event = EventTests.event(A, "3")
        _ = [reply async for reply in self.obj.on_group_message(event)]
        self.assertEqual(self.obj._send_menu.await_args.args[1]["name"], "parent")
        self.obj._active_menus.clear()
        self.activate(A, "11", self.obj._menu_for_session_keyword(A, "tools"))
        _ = [reply async for reply in self.obj.on_group_message(EventTests.event(A, "1"))]
        self.assertEqual(self.obj._send_menu.await_args.args[1]["name"], "parent")
        self.assertEqual(self.obj._send_menu.await_count, 2)
        self.platform.commit_event.assert_not_called()


class InteractiveMenuTests(unittest.IsolatedAsyncioTestCase):
    class Provider:
        def __init__(self):
            self.actions = []
            self.page_options = []
            self.action_options = []

        def get_interactive_menu_api_info(self):
            return {"provider_id": "cs2_openweaponscase", "api_version": 1,
                    "enabled": True, "supported_platforms": ["aiocqhttp"]}

        def get_interactive_menu_page(self, state=None, display_options=None):
            self.page_options.append(copy.deepcopy(display_options))
            if state is None:
                title, state = "", {"level": "home"}
                items = [
                    {"label": label, "action_id": f"home:{action}"}
                    for action, label in (
                        ("self_open", "快速开箱"),
                        ("inventory", "查看库存"),
                        ("price_help", "开箱帮助"),
                        ("case_list", "武器箱一览"),
                        ("clear_inventory", "清空库存记录（个人）"),
                        ("update_cases", "更新武器箱数据（管理员）"),
                        ("clear_cache", "清理本地图片缓存（管理员）"),
                    )
                ]
            elif state.get("level") == "type":
                title = display_options["type_page_title"]
                items = [
                    {"label": display_options["category_option_template"].replace(
                        "{label}", display_options.get(f"{key}_label", label)
                    ).replace("{count}", "2"), "action_id": f"category:{key}"}
                    for key, label in (("case", "武器箱"), ("souvenir", "纪念包"), ("collection", "收藏品"),
                                       ("capsule", "胶囊/涂鸦/布章"))
                ]
                items.append({"label": "取消", "action_id": "nav:cancel"})
            elif state.get("level") == "container":
                title = "选择武器箱"
                first = state.get("page", 0) == 0
                name = "测试武器箱" if first else "第二页武器箱"
                items = [{"label": name, "action_id": f"container:{name}"},
                         {"label": "翻页", "action_id": "nav:next" if first else "nav:prev"},
                         {"label": "返回", "action_id": "nav:back"}, {"label": "取消", "action_id": "nav:cancel"}]
            elif state.get("level") == "quantity":
                title = "选择开箱数量"
                items = [{"label": f"开 {count} 个", "action_id": f"quantity:{count}"}
                         for count in display_options["quantity_options"].split(",") if count and int(count) <= 50]
                items.extend([{"label": "返回", "action_id": "nav:back"}, {"label": "取消", "action_id": "nav:cancel"}])
            else:
                raise AssertionError(f"Unexpected state: {state}")
            return {"kind": "page", "page": {"title": title, "state": state, "items": items}}

        def handle_interactive_menu_action(self, state, action_id, display_options=None):
            self.actions.append((copy.deepcopy(state), action_id))
            self.action_options.append(copy.deepcopy(display_options))
            if action_id == "home:self_open":
                return self.get_interactive_menu_page({"level": "type"}, display_options)
            home_commands = {
                "home:inventory": "库存",
                "home:price_help": "开箱菜单",
                "home:case_list": "武器箱列表",
                "home:clear_inventory": "清除库存",
                "home:update_cases": "更新武器箱",
                "home:clear_cache": "清除缓存",
            }
            if action_id in home_commands:
                return {
                    "kind": "command", "command": home_commands[action_id],
                    "keep_menu": True,
                }
            if action_id == "category:case":
                return self.get_interactive_menu_page(
                    {"level": "container", "category": "case", "page": 0}, display_options
                )
            if action_id in ("nav:next", "nav:prev"):
                return self.get_interactive_menu_page(
                    {**state, "page": 1 if action_id == "nav:next" else 0}, display_options
                )
            if action_id.startswith("container:"):
                return self.get_interactive_menu_page({
                    "level": "quantity", "container_name": action_id.removeprefix("container:")
                }, display_options)
            return {
                "kind": "command",
                "command": f"开箱 {action_id.removeprefix('quantity:')} 测试武器箱",
                "keep_menu": True,
            }

    async def asyncSetUp(self):
        self.provider = self.Provider()
        metadata = SimpleNamespace(
            activated=True,
            plugin_id="luooka/astrbot_plugin_openweaponscase",
            root_dir_name="astrbot_plugin_openweaponscase",
            star_cls=self.provider,
        )
        self.context = SimpleNamespace(get_all_stars=lambda: [metadata])
        api_menu = {"__template_key": "cs2_openweaponscase", "menu_id": "cs2_openweaponscase",
                    "name": "CS2 开箱", "keywords": ["开箱"], "home_menu": {"title": "CS2 开箱"}}
        self.obj = Plugin(self.context, {"global_settings": {"menus": [api_menu], "umo_menus": []}})
        self.obj._assign_face_ids = lambda items: [dict(item, face_id="") for item in items]
        self.obj._dispatch_native_command = AsyncMock()

        class Bot:
            def __init__(inner_self):
                inner_self.counter = 0
                inner_self.deleted = []
                inner_self.messages = []
                inner_self.reactions = []

            async def send_group_msg(inner_self, group_id, message):
                inner_self.counter += 1
                inner_self.messages.append(message)
                return {"message_id": str(inner_self.counter)}

            async def set_msg_emoji_like(inner_self, **kwargs):
                inner_self.reactions.append(kwargs)

            async def delete_msg(inner_self, message_id):
                inner_self.deleted.append(message_id)

        self.bot = Bot()

    async def asyncTearDown(self):
        self.obj._cleanup_task.cancel()
        await asyncio.gather(self.obj._cleanup_task, return_exceptions=True)

    def event(self, text="", user="42", raw=None):
        return SimpleNamespace(
            get_platform_name=lambda: "aiocqhttp",
            get_platform_id=lambda: "production-qq-bot", get_group_id=lambda: "123",
            get_sender_id=lambda: user, message_str=text, unified_msg_origin=A,
            message_obj=SimpleNamespace(raw_message=raw or {}, message_id="input", self_id="999"),
            bot=self.bot, stop_event=Mock(), plain_result=lambda value: value, send=AsyncMock(),
        )

    def test_platform_name_is_used_instead_of_custom_instance_id(self):
        event = self.event()
        self.assertEqual(platform_for_event(event), "aiocqhttp")

    def test_other_platform_name_is_not_overridden_by_custom_id(self):
        event = self.event()
        event.get_platform_name = lambda: "discord"
        event.get_platform_id = lambda: "aiocqhttp"
        self.assertEqual(platform_for_event(event), "discord")

    async def open_menu(self):
        event = self.event("开箱")
        self.assertEqual([reply async for reply in self.obj.on_group_message(event)], [])
        self.assertEqual(len(self.obj._active_menus), 1)

    async def test_provider_template_normalizes_without_static_items(self):
        normalized = self.obj._menu_for_session_keyword(A, "开箱")
        self.assertEqual(normalized["provider_id"], "cs2_openweaponscase")
        self.assertEqual(normalized["items"], [])
        self.assertEqual(normalized["provider_options"]["quantity_options"], "1,5,10,20,50")
        self.assertEqual(normalized["provider_layout"]["home_menu"]["title"], "CS2 开箱")
        self.assertEqual(normalized["provider_layout"]["max_concurrent_users"], 3)

    async def test_api_menu_inherits_global_expiry_appearance_and_reaction_limits(self):
        self.obj.menu_timeout = 17
        self.obj.menu_header_image_url = "https://example.com/menu.png"
        self.obj.menu_divider_char = "="
        self.obj.menu_divider_length = 6
        self.obj.menu_footer_text = "全局菜单页尾"
        self.obj.menu_max_reactions = 1
        self.obj.face_pool = ["14", "15"]
        del self.obj._assign_face_ids

        await self.open_menu()
        _, active = next(iter(self.obj._active_menus.items()))
        message = self.bot.messages[-1]
        self.assertEqual(active["timeout"], 17)
        self.assertTrue(message.startswith(
            "[CQ:at,qq=42]\n\n[CQ:image,file=https://example.com/menu.png]\n\n"
        ))
        self.assertEqual(message.count("======"), 2)
        self.assertTrue(message.endswith("全局菜单页尾"))
        self.assertEqual(len(self.bot.reactions), 1)
        self.assertIsInstance(self.bot.reactions[0]["emoji_id"], int)

    async def test_api_menu_repeat_open_obeys_global_block_without_replacing_message(self):
        await self.open_menu()
        initial_messages = list(self.bot.messages)

        event = self.event("开箱", user="77")
        replies = [reply async for reply in self.obj.on_group_message(event)]

        self.assertEqual(replies, [self.obj.menu_repeat_reply])
        self.assertEqual(self.bot.messages, initial_messages)
        self.assertEqual(self.bot.deleted, [])
        self.assertEqual(len(self.provider.page_options), 1)

    async def test_expired_api_home_ignores_text_and_reaction_selection(self):
        self.obj.menu_timeout = 5
        await self.open_menu()
        (session_id, message_id), active = next(iter(self.obj._active_menus.items()))
        active["created_at"] -= 6

        text_event = self.event("1")
        self.assertEqual([reply async for reply in self.obj.on_group_message(text_event)], [])
        reaction = self.event(raw={
            "notice_type": "group_msg_reaction", "group_id": "123",
            "message_id": message_id, "user_id": "42", "emoji_id": "14", "self_id": "999",
        })
        await self.obj._handle_reaction_event(reaction)

        self.assertNotIn((session_id, message_id), self.obj._active_menus)
        self.assertEqual(self.provider.actions, [])

    async def test_repeated_quick_open_keeps_existing_user_page(self):
        await self.open_menu()
        root_key, root_menu = next(iter(self.obj._active_menus.items()))
        await self.select("1")
        messages_before = list(self.bot.messages)
        deleted_before = list(self.bot.deleted)
        actions_before = list(self.provider.actions)
        event = self.event()

        await self.obj._api_menus.handle_selection(
            event,
            "42",
            "123",
            root_menu,
            {"api_action_id": "home:self_open", "command": ""},
        )

        self.assertEqual(event.send.await_args.args, (self.obj.menu_repeat_reply,))
        self.assertEqual(self.bot.messages, messages_before)
        self.assertEqual(self.bot.deleted, deleted_before)
        self.assertEqual(self.provider.actions, actions_before)
        self.assertIn(root_key, self.obj._active_menus)
        self.assertTrue(any(
            data.get("owner_user_id") == "42"
            and data.get("provider_state", {}).get("level") == "type"
            for data in self.obj._active_menus.values()
        ))

    async def test_home_menu_mentions_opener_but_private_pages_do_not(self):
        await self.open_menu()
        self.assertTrue(self.bot.messages[-1].startswith("[CQ:at,qq=42]\n\n"))

        await self.select("1")
        self.assertNotIn("[CQ:at,qq=", self.bot.messages[-1])

    async def test_quick_open_concurrency_limit_is_per_group_and_allows_existing_user(self):
        card = self.obj.config["global_settings"]["menus"][0]
        card["max_concurrent_users"] = 1
        self.obj._load_menu_profiles()
        await self.open_menu()
        await self.select("1", user="42")
        api_menu = self.obj._menu_for_session_keyword(A, "开箱")
        type_page = self.provider.get_interactive_menu_page(
            {"level": "type"}, api_menu["provider_options"]
        )

        before = len(self.bot.messages)
        rejected_event = await self.select("1", user="77")
        rejected_event.send.assert_awaited_once()
        self.assertIn("人数已达上限（1 人）", rejected_event.send.await_args.args[0])
        self.assertEqual(len(self.bot.messages), before)
        self.assertTrue(any(
            data.get("owner_user_id") == "42"
            and data.get("provider_state", {}).get("level") == "type"
            for data in self.obj._active_menus.values()
        ))

        continued = await self.obj._api_menus._show_interactive_menu_page(
            self.event(user="42"), "42", "123", "cs2_openweaponscase", type_page, api_menu
        )
        self.assertIsNone(continued)
        self.assertIn("选择开箱种类", self.bot.messages[-1])

        another_group = self.event(user="77")
        another_group.get_group_id = lambda: "456"
        allowed = await self.obj._api_menus._show_interactive_menu_page(
            another_group, "77", "456", "cs2_openweaponscase", type_page, api_menu
        )
        self.assertIsNone(allowed)

        user_flow = next(
            flow for key, flow in self.obj._api_menus.flows.items()
            if key[0].endswith(":GroupMessage:123") and key[1] == "42" and key[-1] == "user"
        )
        user_flow["updated_at"] -= self.obj.menu_timeout + 1
        after_expiry = await self.obj._api_menus._show_interactive_menu_page(
            self.event(user="88"), "88", "123", "cs2_openweaponscase", type_page, api_menu
        )
        self.assertIsNone(after_expiry)

    async def test_zero_concurrency_limit_is_unlimited(self):
        card = self.obj.config["global_settings"]["menus"][0]
        card["max_concurrent_users"] = 0
        self.obj._load_menu_profiles()
        api_menu = self.obj._menu_for_session_keyword(A, "开箱")
        type_page = self.provider.get_interactive_menu_page(
            {"level": "type"}, api_menu["provider_options"]
        )
        for user_id in ("42", "77", "88", "99"):
            result = await self.obj._api_menus._show_interactive_menu_page(
                self.event(user=user_id), user_id, "123", "cs2_openweaponscase", type_page, api_menu
            )
            self.assertIsNone(result)
        self.assertEqual(len([
            flow for key, flow in self.obj._api_menus.flows.items() if key[-1] == "user"
        ]), 4)

    def enable_parent_menu(self, *, umo=False):
        settings = self.obj.config["global_settings"]
        parent = {**menu("总菜单", "总菜单"), "items": ["CS开箱游戏,开箱,14"]}
        if umo:
            settings["umo_menus"] = [
                {**card, "umo": "production-qq-bot:GroupMessage:123"}
                for card in [parent, *settings["menus"]]
            ]
        else:
            settings["menus"].insert(0, parent)
        self.obj._load_menu_profiles()
        self.obj._assign_face_ids = lambda items: items

    async def test_global_menu_selection_opens_provider_page(self):
        self.enable_parent_menu()
        parent = self.event("总菜单")
        self.assertEqual([reply async for reply in self.obj.on_group_message(parent)], [])

        selection = self.event("1", user="77")
        self.assertEqual([reply async for reply in self.obj.on_group_message(selection)], [])
        self.assertTrue(self.bot.messages[-1].startswith("[CQ:at,qq=77]\n\n"))
        self.assertIn("CS2 开箱", self.bot.messages[-1])
        self.assertEqual(len(self.provider.page_options), 1)
        active = next(menu for menu in self.obj._active_menus.values() if menu.get("provider_id"))
        self.assertEqual(active["owner_user_id"], "77")
        self.assertEqual(len(active["items"]), 7)
        self.assertEqual(self.obj._recent_virtual_commands, {})

    async def test_umo_menu_reaction_opens_provider_page_as_clicker(self):
        self.enable_parent_menu(umo=True)
        parent = self.event("总菜单")
        self.assertEqual([reply async for reply in self.obj.on_group_message(parent)], [])
        (session, message_id), active = next(iter(self.obj._active_menus.items()))
        active["created_at"] -= 3
        reaction = self.event(user="", raw={
            "notice_type": "group_msg_reaction", "group_id": "123", "message_id": message_id,
            "user_id": "77", "emoji_id": "14", "self_id": "999",
        })
        await self.obj._handle_reaction_event(reaction)

        self.assertEqual(len(self.provider.page_options), 1)
        nested = self.obj._active_menus[(session, str(self.bot.counter))]
        self.assertEqual(nested["owner_user_id"], "77")
        self.assertEqual(len(nested["items"]), 7)
        self.assertEqual(self.obj._recent_virtual_commands, {})

    async def test_nested_provider_does_not_render_when_disabled(self):
        self.enable_parent_menu()
        del self.obj._dispatch_native_command
        original_info = self.provider.get_interactive_menu_api_info
        self.provider.get_interactive_menu_api_info = lambda: {**original_info(), "enabled": False}
        self.context.get_platform_inst = Mock(return_value=SimpleNamespace(
            create_event=Mock(side_effect=lambda message: message), commit_event=Mock(),
        ))
        parent = self.event("总菜单")
        self.assertEqual([reply async for reply in self.obj.on_group_message(parent)], [])
        selection = self.event("1", user="77")
        self.assertEqual([reply async for reply in self.obj.on_group_message(selection)], [])

        self.assertEqual(len(self.bot.messages), 1)
        self.assertEqual(self.provider.page_options, [])
        platform = self.context.get_platform_inst.return_value
        platform.commit_event.assert_called_once()
        command = platform.commit_event.call_args.args[0]
        self.assertEqual(command.message_str, "/开箱")
        self.assertEqual(command.sender.user_id, "77")

    async def test_card_title_is_only_used_for_home_page(self):
        await self.open_menu()
        home_message = self.bot.messages[-1]
        self.assertIn("CS2 开箱", home_message)
        self.assertIn("1. 快速开箱", home_message)
        self.assertIn("3. 开箱帮助", home_message)
        self.assertIn("7. 清理本地图片缓存（管理员）", home_message)

        event = self.event("1")
        _ = [reply async for reply in self.obj.on_group_message(event)]
        submenu_message = self.bot.messages[-1]
        self.assertIn("选择开箱种类", submenu_message)
        self.assertNotIn("CS2 开箱", submenu_message)

    async def test_home_remains_public_and_active_after_opening_private_flow(self):
        await self.open_menu()
        old_key, old_data = next(iter(self.obj._active_menus.items()))
        event = self.event("1")
        self.assertEqual([reply async for reply in self.obj.on_group_message(event)], [])
        self.assertEqual(self.provider.actions, [({"level": "home"}, "home:self_open")])
        self.assertIn(old_key, self.obj._active_menus)
        self.assertEqual(len(self.obj._active_menus), 2)
        self.assertEqual(self.bot.deleted, [])

        other_user = self.event("2", user="77")
        _ = [reply async for reply in self.obj.on_group_message(other_user)]
        self.obj._dispatch_native_command.assert_awaited_with(
            other_user, "77", "123", "/库存"
        )
        self.assertIn(old_key, self.obj._active_menus)
        self.assertEqual(len(self.obj._active_menus), 2)
        self.assertEqual(self.bot.deleted, [])
        self.assertEqual(self.provider.actions, [({"level": "home"}, "home:self_open")])

    async def test_another_user_can_use_reaction_on_shared_home(self):
        self.obj._assign_face_ids = lambda items: [
            dict(item, face_id=str(index + 1)) for index, item in enumerate(items)
        ]
        await self.open_menu()
        _, active = next(iter(self.obj._active_menus.items()))
        active["created_at"] -= 2
        reaction = self.event(raw={
            "notice_type": "group_msg_reaction", "group_id": "123",
            "message_id": active["message_id"], "user_id": "77", "emoji_id": "1",
            "self_id": "999",
        })
        await self.obj._handle_reaction_event(reaction)
        self.assertEqual(self.provider.actions, [({"level": "home"}, "home:self_open")])
        self.assertEqual(len(self.obj._active_menus), 2)
        self.assertTrue(any(
            data.get("owner_user_id") == "77" and data.get("provider_state", {}).get("level") == "type"
            for data in self.obj._active_menus.values()
        ))

    async def test_private_opening_flow_rejects_other_users(self):
        self.obj._assign_face_ids = lambda items: [dict(item, face_id="14") for item in items]
        await self.open_menu()
        event = self.event("1", user="42")
        _ = [reply async for reply in self.obj.on_group_message(event)]
        private_key, private_menu = next(
            (key, data) for key, data in self.obj._active_menus.items()
            if data.get("provider_state", {}).get("level") == "type"
        )
        private_menu["created_at"] -= 2
        reaction = self.event(raw={
            "notice_type": "group_msg_reaction", "group_id": "123",
            "message_id": private_key[1], "user_id": "77", "emoji_id": "14",
            "self_id": "999",
        })
        await self.obj._handle_reaction_event(reaction)
        self.assertEqual(self.provider.actions, [({"level": "home"}, "home:self_open")])
        self.assertEqual(len(self.obj._active_menus), 2)

    async def test_final_selection_dispatches_native_command(self):
        await self.open_menu()
        for _ in range(3):
            event = self.event("1")
            _ = [reply async for reply in self.obj.on_group_message(event)]
        user_flow_key, user_flow = next(
            (key, flow) for key, flow in self.obj._api_menus.flows.items() if key[-1] == "user"
        )
        expiry_timestamp = user_flow["updated_at"]
        quantity_event = self.event("1")
        _ = [reply async for reply in self.obj.on_group_message(quantity_event)]
        self.assertEqual(self.obj._dispatch_native_command.await_args.args,
                         (quantity_event, "42", "123", "/开箱 1 测试武器箱"))
        self.assertEqual(len(self.obj._api_menus.flows), 2)
        flow = next(
            value for key, value in self.obj._api_menus.flows.items()
            if key[-1] == "user"
        )
        self.assertFalse(flow["processing"])
        self.assertEqual(len(self.obj._active_menus), 2)
        self.assertEqual(self.bot.deleted, [2, 3])
        self.assertTrue(any(
            data["message_id"] == "4"
            and data.get("provider_state", {}).get("level") == "quantity"
            for data in self.obj._active_menus.values()
        ))
        self.assertEqual(self.provider.actions, [
            ({"level": "home"}, "home:self_open"),
            ({"level": "type"}, "category:case"),
            ({"level": "container", "category": "case", "page": 0}, "container:测试武器箱"),
            ({"level": "quantity", "container_name": "测试武器箱"}, "quantity:1"),
        ])
        self.assertEqual(self.provider.action_options[-1], self.provider.page_options[0])
        self.assertNotIn("home_menu", self.provider.action_options[-1])

        third = self.event("1")
        _ = [reply async for reply in self.obj.on_group_message(third)]
        self.assertEqual(self.obj._dispatch_native_command.await_count, 2)
        self.assertEqual(len(self.obj._active_menus), 2)
        self.assertEqual(user_flow["updated_at"], expiry_timestamp)
        self.obj._api_menus.expire(
            expiry_timestamp + self.obj.menu_timeout + 1, self.obj.menu_timeout
        )
        self.assertNotIn(user_flow_key, self.obj._api_menus.flows)

    async def test_home_commands_dispatch_native_commands_in_display_order(self):
        selections = (
            (2, "/库存"),
            (3, "/开箱菜单"),
            (4, "/武器箱列表"),
            (5, "/清除库存"),
            (6, "/更新武器箱"),
            (7, "/清除缓存"),
        )
        for number, command in selections:
            with self.subTest(number=number):
                self.obj._active_menus.clear()
                self.obj._api_menus.flows.clear()
                await self.open_menu()
                self.bot.deleted.clear()
                event = self.event(str(number), user="77")
                _ = [reply async for reply in self.obj.on_group_message(event)]
                self.obj._dispatch_native_command.assert_awaited_with(
                    event, "77", "123", command
                )
                self.assertEqual(len(self.obj._active_menus), 1)
                self.assertEqual(self.bot.deleted, [])
                self.obj._dispatch_native_command.reset_mock()

    async def select(self, text, user="42"):
        event = self.event(text, user)
        self.assertEqual([reply async for reply in self.obj.on_group_message(event)], [])
        return event

    def configure_page(self, group, **fields):
        card = self.obj.config["global_settings"]["menus"][0]
        card.setdefault(group, {}).update(fields)
        self.obj._load_menu_profiles()

    async def test_unconfigured_categories_are_hidden_without_removing_api_support(self):
        await self.open_menu()
        await self.select("1")
        self.assertEqual([item["label"] for item in list(self.obj._active_menus.values())[-1]["items"]], [
            "武器箱（2）", "纪念包（2）", "收藏品（2）", "取消选择",
        ])
        self.configure_page("type_menu", items=["新上线的胶囊,api:category:capsule"])
        api_menu = self.obj._menu_for_session_keyword(A, "开箱")
        rendered = self.provider.get_interactive_menu_page({"level": "type"}, api_menu["provider_options"])
        rendered["page"]["items"] = [
            item for item in rendered["page"]["items"] if item["action_id"] != "category:capsule"
        ]
        reply = await self.obj._api_menus._show_interactive_menu_page(
            self.event(), "42", "123", "cs2_openweaponscase", rendered, api_menu
        )
        self.assertIn("没有可用选项", reply)
        await self.obj._api_menus._show_interactive_menu_page(
            self.event(), "42", "123", "cs2_openweaponscase",
            self.provider.get_interactive_menu_page({"level": "type"}, api_menu["provider_options"]), api_menu
        )
        self.assertIn("新上线的胶囊（2）", self.bot.messages[-1])

    async def test_custom_home_rows_share_command_and_reaction_dispatch(self):
        self.configure_page("home_menu", items=["新增功能,新功能 参数,14", "快速开箱,api:home:self_open"])
        self.obj._assign_face_ids = lambda items: items
        await self.open_menu()
        key, active = next(iter(self.obj._active_menus.items()))
        self.assertIn("1. 新增功能", self.bot.messages[-1])
        self.assertNotIn("查看库存", self.bot.messages[-1])
        selection = await self.select("1", user="77")
        self.obj._dispatch_native_command.assert_awaited_once_with(selection, "77", "123", "/新功能 参数")
        self.obj._dispatch_native_command.reset_mock()
        active["created_at"] -= 2
        reaction = self.event(raw={
            "notice_type": "group_msg_reaction", "group_id": "123",
            "message_id": active["message_id"], "user_id": "88", "emoji_id": "14", "self_id": "999",
        })
        await self.obj._handle_reaction_event(reaction)
        self.obj._dispatch_native_command.assert_awaited_once_with(reaction, "88", "123", "/新功能 参数")
        self.assertIn(key, self.obj._active_menus)
        self.assertEqual(self.bot.deleted, [])
        self.assertEqual(self.provider.actions, [])

    async def test_custom_home_command_can_open_another_menu(self):
        self.configure_page("home_menu", items=["更多工具,总菜单"])
        self.enable_parent_menu()
        await self.open_menu()
        await self.select("1", user="77")
        self.assertIn("总菜单", self.bot.messages[-1])
        self.assertIn("CS开箱游戏", self.bot.messages[-1])
        self.obj._dispatch_native_command.assert_not_awaited()
        self.assertEqual(len(self.obj._active_menus), 2)

    async def test_case_rows_follow_configuration_and_stale_page_cannot_run_commands(self):
        self.configure_page("case_menu", items=[
            "后页,api:nav:next", "前页,api:nav:prev", "候选：{item},api:items", "新增功能,新功能,14",
        ])
        self.obj._assign_face_ids = lambda items: items
        await self.open_menu()
        await self.select("1")
        await self.select("1")
        old_key, old_data = list(self.obj._active_menus.items())[-1]
        for active in self.obj._active_menus.values():
            active["created_at"] -= 2
        self.assertEqual([item["label"] for item in old_data["items"]], ["后页", "候选：测试武器箱", "新增功能"])
        reaction = self.event(raw={
            "notice_type": "group_msg_reaction", "group_id": "123",
            "message_id": old_data["message_id"], "user_id": "77", "emoji_id": "14", "self_id": "999",
        })
        await self.obj._handle_reaction_event(reaction)
        self.obj._dispatch_native_command.assert_not_awaited()
        await self.select("1")
        self.assertNotIn(old_key, self.obj._active_menus)
        self.assertEqual([item["label"] for item in list(self.obj._active_menus.values())[-1]["items"]], [
            "前页", "候选：第二页武器箱", "新增功能",
        ])
        reaction.message_obj.raw_message["user_id"] = "42"
        await self.obj._handle_reaction_event(reaction)
        self.obj._dispatch_native_command.assert_not_awaited()
        selection = await self.select("新增功能")
        self.obj._dispatch_native_command.assert_awaited_once_with(selection, "42", "123", "/新功能")

    async def test_quantity_rows_keep_user_order_and_respect_provider_limit(self):
        self.configure_page("quantity_menu", items=[
            "一次抽八份,api:quantity:8", "超额,api:quantity:99", "再抽两份,api:quantity:2", "返回,api:nav:back",
        ])
        await self.open_menu()
        for _ in range(3):
            await self.select("1")
        quantity_menu = list(self.obj._active_menus.values())[-1]
        self.assertEqual([item["api_action_id"] for item in quantity_menu["items"]], ["quantity:8", "quantity:2", "nav:back"])
        self.assertEqual([item["label"] for item in quantity_menu["items"]], ["一次抽八份", "再抽两份", "返回"])
        await self.select("1")
        self.assertEqual(self.provider.actions[-1][1], "quantity:8")
        self.assertIs(list(self.obj._active_menus.values())[-1], quantity_menu)

    async def test_second_registered_provider_uses_shared_runtime(self):
        spec = ProviderSpec(
            provider_id="example",
            plugin_id="test/example",
            display_name="示例菜单",
            api_versions=(2,),
            platforms=("aiocqhttp",),
            schema_path=PROVIDERS["cs2_openweaponscase"].schema_path,
        )
        example = SimpleNamespace(
            get_interactive_menu_api_info=Mock(return_value={
                "provider_id": "example", "api_version": 2, "enabled": True,
                "supported_platforms": ["aiocqhttp"],
            }),
            get_interactive_menu_page=AsyncMock(return_value={"kind": "page", "page": {
                "title": "示例菜单", "scope": "shared", "state": {"step": "start"},
                "items": [{"label": "查看记录", "action_id": "history"}],
            }}),
            handle_interactive_menu_action=AsyncMock(return_value={
                "kind": "command", "command": "查询记录", "keep_menu": True,
            }),
        )
        self.context.get_all_stars = lambda: [SimpleNamespace(
            activated=True, plugin_id="test/example", star_cls=example,
        )]
        settings = self.obj.config["global_settings"]
        settings["menus"] = [
            {"__template_key": "example", "keywords": ["示例"], "items": []},
            menu("查询记录", "同名普通菜单"),
        ]
        with patch.dict(PROVIDERS, {"example": spec}):
            self.obj._load_menu_profiles()
            trigger = self.event("示例")
            self.assertEqual([reply async for reply in self.obj.on_group_message(trigger)], [])
            self.assertIn("查看记录", self.bot.messages[-1])
            selection = self.event("1", user="77")
            self.assertEqual([reply async for reply in self.obj.on_group_message(selection)], [])
            example.handle_interactive_menu_action.assert_awaited_once_with(
                {"step": "start"}, "history", {}
            )
            self.obj._dispatch_native_command.assert_awaited_once_with(
                selection, "77", "123", "/查询记录"
            )
            self.assertEqual(len(self.bot.messages), 1)

    async def test_provider_version_mismatch_is_rejected(self):
        self.provider.get_interactive_menu_api_info = lambda: {
            "provider_id": "cs2_openweaponscase", "api_version": 99, "enabled": True,
        }
        resolved = await self.obj._api_menus.resolve(PROVIDERS["cs2_openweaponscase"], "aiocqhttp")
        self.assertIn("API 版本不兼容", resolved.error)


if __name__ == "__main__":
    unittest.main()
