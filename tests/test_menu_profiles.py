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
            stop_event=Mock(), plain_result=lambda text: text,
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


if __name__ == "__main__":
    unittest.main()
