from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Plain
from astrbot.api.star import Context, Star, StarTools
from astrbot.core.message.message_event_result import MessageChain

PLUGIN_ID = "astrbot_plugin_react_menu"

try:
    from astrbot.api.platform import AstrBotMessage, MessageMember
except ImportError:
    AstrBotMessage = None  # type: ignore
    MessageMember = None  # type: ignore


class ReactMenuPlugin(Star):
    def __init__(self, context: Context, config: Any):
        super().__init__(context)
        self.context = context
        self.config = config

        self.menu_keywords = self._config_get("menu_keywords", ["菜单"])
        self.menu_title = str(self._config_get("menu_title", "🎮 娱乐菜单"))
        self.menu_timeout = int(self._config_get("menu_timeout_seconds", 600))
        self.debounce_seconds = int(self._config_get("debounce_seconds", 3))
        self.emoji_mapping = self._normalize_mapping(self._config_get("emoji_mapping", {}))

        self._active_menus: dict[str, dict[str, Any]] = {}
        self._debounce: dict[tuple[str, str, str], float] = {}
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        try:
            self._data_dir = StarTools.get_data_dir(PLUGIN_ID)
        except Exception:
            self._data_dir = None

        logger.info(
            f"[react_menu] 已加载，菜单关键词={self.menu_keywords}，映射emoji数量={len(self.emoji_mapping)}"
        )

    def _config_get(self, key: str, default: Any) -> Any:
        if hasattr(self.config, "get"):
            try:
                return self.config.get(key, default)
            except Exception:
                pass
        try:
            return getattr(self.config, key, default)
        except Exception:
            return default

    @staticmethod
    def _normalize_mapping(raw: Any) -> dict[str, dict[str, str]]:
        mapping: dict[str, dict[str, str]] = {}
        if not isinstance(raw, dict):
            return mapping
        for raw_key, raw_value in raw.items():
            key = str(raw_key).strip()
            if not key:
                continue
            if not isinstance(raw_value, dict):
                continue
            command = str(raw_value.get("command", "")).strip()
            desc = str(raw_value.get("desc", "")).strip()
            if not command or not desc:
                continue
            mapping[key] = {"command": command, "desc": desc}
        return mapping

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(60)
            now = time.time()
            expired = [mid for mid, data in self._active_menus.items() if now - data["created_at"] > self.menu_timeout]
            for mid in expired:
                self._active_menus.pop(mid, None)
                logger.debug(f"[react_menu] 清理过期菜单: message_id={mid}")

            self._debounce = {
                key: stamp
                for key, stamp in self._debounce.items()
                if now - stamp < self.debounce_seconds
            }

    def _build_text_menu(self) -> str:
        lines = [self.menu_title, "─" * 12]
        for face_id, info in self.emoji_mapping.items():
            lines.append(f"  {info['desc']}")
        lines.append("─" * 12)
        lines.append("👆 点击上方表情即可触发对应功能")
        return "\n".join(lines)

    def _get_bot(self, event: AstrMessageEvent) -> Any:
        bot = getattr(event, "bot", None)
        if bot is None:
            return None
        if not hasattr(bot, "set_msg_emoji_like") or not hasattr(bot, "send_group_msg"):
            return None
        return bot

    def _stop_event(self, event: AstrMessageEvent) -> None:
        if hasattr(event, "stop_event") and callable(getattr(event, "stop_event")):
            try:
                event.stop_event()
            except Exception:
                pass

    @filter.command("菜单")
    async def on_menu_command(self, event: AstrMessageEvent):
        if not event.get_group_id():
            return

        bot = self._get_bot(event)
        menu_text = self._build_text_menu()
        if bot is None:
            yield event.plain_result(menu_text)
            return

        try:
            response = await bot.send_group_msg(
                group_id=int(event.get_group_id()),
                message=menu_text,
            )
        except Exception as exc:
            logger.error(f"[react_menu] 发送菜单失败: {exc}")
            yield event.plain_result(menu_text)
            self._stop_event(event)
            return

        message_id = str(response.get("message_id", "") or response.get("message_id"))
        if not message_id:
            logger.error("[react_menu] 未获取到菜单消息message_id")
            yield event.plain_result(menu_text)
            self._stop_event(event)
            return

        self._active_menus[message_id] = {
            "group_id": str(event.get_group_id()),
            "created_at": time.time(),
            "emoji_map": self.emoji_mapping,
        }

        for face_id_str in self.emoji_mapping.keys():
            try:
                face_id = int(face_id_str)
                await bot.set_msg_emoji_like(
                    message_id=message_id,
                    emoji_id=face_id,
                    set=True,
                )
                await asyncio.sleep(0.25)
            except Exception as exc:
                logger.warning(f"[react_menu] 贴表情失败 face_id={face_id_str}: {exc}")

        self._stop_event(event)

    @filter.event_message_type(filter.EventMessageType.OTHER_MESSAGE)
    async def on_reaction_event(self, event: AstrMessageEvent):
        group_id = event.get_group_id() or ""
        if not group_id:
            return

        raw = self._parse_raw_message(event)
        if not raw:
            return

        if raw.get("notice_type") != "group_msg_reaction":
            return

        if not self._is_react_operation(raw.get("operation")):
            return

        message_id = str(raw.get("message_id", "") or raw.get("msg_id", ""))
        clicker_id = str(raw.get("target_id") or raw.get("user_id") or "")
        face_id = self._extract_face_id(raw)

        if not message_id or not clicker_id or not face_id:
            logger.debug(f"[react_menu] reaction 字段缺失: {raw}")
            return

        menu_data = self._active_menus.get(message_id)
        if menu_data is None:
            return

        if time.time() - menu_data["created_at"] > self.menu_timeout:
            self._active_menus.pop(message_id, None)
            return

        debounce_key = (message_id, clicker_id, face_id)
        now = time.time()
        last = self._debounce.get(debounce_key)
        if last is not None and now - last < self.debounce_seconds:
            logger.debug(f"[react_menu] 防抖跳过: {debounce_key}")
            return
        self._debounce[debounce_key] = now

        mapping = menu_data["emoji_map"].get(face_id)
        if mapping is None:
            logger.debug(f"[react_menu] 未映射的 face_id={face_id}")
            return

        command = mapping.get("command", "").strip()
        if not command:
            logger.debug(f"[react_menu] 映射指令为空: face_id={face_id}")
            return

        logger.info(f"[react_menu] 触发菜单命令: user={clicker_id} face_id={face_id} -> {command}")
        await self._execute_as_user(event, clicker_id, group_id, command)
        self._stop_event(event)

    def _parse_raw_message(self, event: AstrMessageEvent) -> dict[str, Any] | None:
        raw = None
        message_obj = getattr(event, "message_obj", None)
        if message_obj is not None:
            raw = getattr(message_obj, "raw_message", None)
        if raw is None:
            raw = getattr(event, "raw_message", None)
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                return None
        if isinstance(raw, dict):
            return raw
        return None

    @staticmethod
    def _extract_face_id(raw: dict[str, Any]) -> str:
        face_id = raw.get("face_id") or raw.get("emoji_id")
        if face_id is None:
            message = raw.get("message")
            if isinstance(message, dict):
                face = message.get("face")
                if isinstance(face, dict):
                    face_id = face.get("id") or face.get("face_id")
        return str(face_id or "")

    @staticmethod
    def _is_react_operation(operation: Any) -> bool:
        if operation is None:
            return False
        if isinstance(operation, str):
            operation = operation.lower().strip()
            return operation in {"1", "react", "add", "set"}
        if isinstance(operation, int):
            return operation == 1
        return False

    async def _execute_as_user(self, event: AstrMessageEvent, user_id: str, group_id: str, command: str) -> None:
        if user_id and AstrBotMessage is not None and MessageMember is not None:
            try:
                fake_msg = AstrBotMessage()
                fake_msg.self_id = getattr(event.message_obj, "self_id", None) or getattr(event, "self_id", None) or ""
                fake_msg.sender = MessageMember(user_id=user_id, nickname=user_id)
                fake_msg.type = getattr(event.message_obj, "type", None) or getattr(event, "message_type", None) or ""
                fake_msg.group_id = group_id
                fake_msg.session_id = group_id
                fake_msg.message_id = f"react_menu_{int(time.time() * 1000)}_{user_id}"
                fake_msg.message_str = f"/{command}"
                fake_msg.message = [Plain(text=f"/{command}")]
                fake_msg.raw_message = {}

                platform_id = None
                if hasattr(event, "get_platform_id"):
                    try:
                        platform_id = event.get_platform_id()
                    except Exception:
                        platform_id = None
                if platform_id is None:
                    platform_id = getattr(event, "platform_id", None)
                platform = None
                if platform_id is not None and hasattr(self.context, "get_platform_inst"):
                    try:
                        platform = self.context.get_platform_inst(platform_id)
                    except Exception:
                        platform = None
                if platform is not None and hasattr(platform, "create_event") and hasattr(platform, "commit_event"):
                    fake_event = platform.create_event(fake_msg)
                    platform.commit_event(fake_event)
                    logger.info(f"[react_menu] 已推入虚拟事件: user={user_id} cmd=/{command}")
                    return
            except Exception as exc:
                logger.warning(f"[react_menu] 构造虚拟事件失败: {exc}")

        try:
            session = f"aiocqhttp:group_message:{group_id}"
            await self.context.send_message(
                session=session,
                message_chain=MessageChain([Plain(f"/{command}")]),
            )
            logger.info(f"[react_menu] fallback 发送指令文本: session={session} cmd=/{command}")
        except Exception as exc:
            logger.error(f"[react_menu] 触发目标命令失败: {exc}")
