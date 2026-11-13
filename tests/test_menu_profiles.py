"""Offline behavior checks, without importing AstrBot or contacting OneBot."""

import ast
import asyncio
import copy
import json
import random
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock


ROOT = Path(__file__).resolve().parents[1]


def load_plugin():
    # Execute the actual plugin class and constants; only replace framework imports.
    source = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
    body = [ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)]
    body += [node for node in source.body if isinstance(node, (ast.Assign, ast.AnnAssign, ast.ClassDef))]
    namespace = {
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
    exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])), str(ROOT / "main.py"), "exec"), namespace)
    return namespace["ReactMenuPlugin"]


Plugin = load_plugin()
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
        self.assertTrue(schema["session_settings"]["invisible"])


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


if __name__ == "__main__":
    unittest.main()
