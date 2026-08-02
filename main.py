from __future__ import annotations

import asyncio
import json
import random
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
        self.menu_header_image_url = str(self._config_get("menu_header_image_url", "") or "").strip()
        self.menu_divider_char = str(self._config_get("menu_divider_char", "─"))[:1] or "─"
        self.menu_divider_length = int(self._config_get("menu_divider_length", 28))
        self.menu_timeout = int(self._config_get("menu_timeout_seconds", 600))
        self.debounce_seconds = int(self._config_get("debounce_seconds", 3))
        self.menu_max_reactions = int(self._config_get("menu_max_reactions", 0) or 0)
        self.menu_repeat_block = bool(self._config_get("menu_repeat_block", True))
        self.menu_repeat_reply = str(self._config_get("menu_repeat_reply", "当前菜单已经生效，正在冷却中，直接点表情或发序号/内容即可触发~"))
        self.face_pool = self._normalize_face_pool(self._config_get("face_pool", []))
        self.menu_items = self._normalize_menu_items(self._config_get("menu_items", None))

        self._active_menus: dict[str, dict[str, Any]] = {}
        self._recent_virtual_commands: dict[tuple[str, str, str], float] = {}
        self._debounce: dict[tuple[str, str, str], float] = {}
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        try:
            self._data_dir = StarTools.get_data_dir(PLUGIN_ID)
        except Exception:
            self._data_dir = None

        logger.info(
            f"[react_menu] 已加载，菜单关键词={self.menu_keywords}，菜单项数量={len(self.menu_items)} face_pool={len(self.face_pool)}"
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
    def _normalize_face_pool(raw: Any) -> list[str]:
        if isinstance(raw, list):
            values = [str(value).strip() for value in raw if str(value).strip()]
            return list(dict.fromkeys(values))
        if isinstance(raw, str):
            values = [value.strip() for value in raw.replace("\n", " ").replace(",", " ").split() if value.strip()]
            return list(dict.fromkeys(values))
        return [str(i) for i in range(128, 201)]

    def _normalize_menu_items(self, raw: Any) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        if isinstance(raw, str):
            lines = [line.strip() for line in raw.splitlines() if line.strip()]
        elif isinstance(raw, list):
            lines = raw
        else:
            lines = []

        for raw_value in lines:
            if isinstance(raw_value, dict):
                label = str(raw_value.get("label", "")).strip()
                command = str(raw_value.get("command", label or raw_value.get("desc", ""))).strip()
                face_id = str(raw_value.get("face_id", "")).strip()
                if not label and command:
                    label = command.lstrip("/")
                if not command and label:
                    command = label
                if not label or not command:
                    continue
                items.append({"label": label, "command": command, "face_id": face_id})
                continue

            if isinstance(raw_value, str):
                text = raw_value.strip()
                if not text:
                    continue
                label, command = self._split_menu_item_text(text)
                if not label or not command:
                    continue
                items.append({"label": label, "command": command, "face_id": ""})
                continue

        return items

    @staticmethod
    def _split_menu_item_text(text: str) -> tuple[str, str]:
        text = (text or "").strip()
        if not text:
            return "", ""

        # 优先按逗号分隔
        for sep in (",", "，"):
            if sep in text:
                left, right = text.split(sep, 1)
                label = left.strip().lstrip("/")
                command = right.strip()
                if not label:
                    label = command.lstrip("/")
                if not command:
                    command = label
                return label, command

        # 支持 `显示 / 指令` 或 `显示/指令`
        if "/" in text and text.find("/") > 0:
            left, right = text.split("/", 1)
            label = left.strip()
            command = right.strip()
            if not label:
                label = command.lstrip("/")
            if not command:
                command = label
            return label, command

        # 最后按第一个空格分隔为 label 和 command
        if " " in text:
            left, right = text.split(" ", 1)
            label = left.strip()
            command = right.strip()
            if not label:
                label = command.lstrip("/")
            if not command:
                command = label
            return label, command

        return text, text

    @staticmethod
    def _normalize_command(command: str) -> str:
        command = (command or "").strip()
        if not command:
            return ""
        if not command.startswith("/"):
            return "/" + command
        return command

    def _assign_face_ids(self, items: list[dict[str, str]]) -> list[dict[str, str]]:
        items = [dict(item) for item in items]
        existing = {item["face_id"] for item in items if item.get("face_id")}
        unassigned = [item for item in items if not item.get("face_id")]
        if not unassigned:
            return items

        available = [fid for fid in self.face_pool if fid not in existing]
        if len(available) < len(unassigned):
            fallback_ids = [str(i) for i in range(128, 201) if str(i) not in existing and str(i) not in available]
            available.extend(fallback_ids)
            if len(available) < len(unassigned):
                logger.warning(
                    f"[react_menu] face_pool 可用 face_id 不足，可能出现重复ID映射或部分菜单无法贴表情：需要={len(unassigned)} 可用={len(available)}"
                )

        random.shuffle(available)
        for item in unassigned:
            if not available:
                item["face_id"] = "0"
            else:
                item["face_id"] = str(available.pop())

        return items

    def _find_active_menu_for_group(self, group_id: str) -> tuple[str, dict[str, Any]] | tuple[None, None]:
        now = time.time()
        active = [
            (mid, data)
            for mid, data in self._active_menus.items()
            if data.get("group_id") == group_id and now - data["created_at"] <= self.menu_timeout
        ]
        if not active:
            return None, None
        return max(active, key=lambda pair: pair[1]["created_at"])

    def _has_active_menu_in_group(self, group_id: str) -> bool:
        menu_id, menu_data = self._find_active_menu_for_group(group_id)
        return menu_data is not None

    def _match_menu_item(self, text: str, items: list[dict[str, str]]) -> dict[str, str] | None:
        normalized = text.strip().lower()
        if not normalized:
            return None

        if normalized.isdigit():
            index = int(normalized) - 1
            if 0 <= index < len(items):
                return items[index]

        for item in items:
            if normalized == item.get("label", "").strip().lower():
                return item
            command = item.get("command", "")
            normalized_command = self._normalize_command(command).strip().lower()
            if normalized == normalized_command or normalized == normalized_command.lstrip("/"):
                return item

        return None

    async def _handle_menu_selection(self, event: AstrMessageEvent, text: str, menu_data: dict[str, Any]) -> bool:
        item = self._match_menu_item(text, menu_data.get("items", []))
        if item is None:
            return False

        command = item.get("command", "").strip()
        if not command:
            return False

        group_id = str(event.get_group_id())
        user_id = str(event.get_sender_id() or "")
        if not user_id:
            logger.debug("[react_menu] 选择菜单项但无法获取用户ID")
            return False

        logger.info(
            f"[react_menu] 菜单文本触发命令: user={user_id} group={group_id} text={text} command={command}"
        )
        await self._execute_as_user(event, user_id, group_id, self._normalize_command(command))
        self._stop_event(event)
        return True

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
            # 清理最近虚拟命令记录，避免无限增长（过期 30s）
            self._recent_virtual_commands = {
                key: ts
                for key, ts in self._recent_virtual_commands.items()
                if now - ts < 30
            }

    def _build_text_menu(self, items: list[dict[str, str]]) -> str:
        lines = []
        if self.menu_header_image_url:
            lines.append(f"[CQ:image,file={self.menu_header_image_url}]")
            lines.append("")
        lines.append(self.menu_title)
        lines.append(self.menu_divider_char * self.menu_divider_length)
        for index, item in enumerate(items, start=1):
            lines.append(f"  {index}. {item['label']}")
        lines.append(self.menu_divider_char * self.menu_divider_length)
        lines.append("👆 下方按顺序贴表情，第1个表情对应第1项，第2个表情对应第2项。也可直接回复序号或菜单内容触发。")
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

    async def _send_menu(self, event: AstrMessageEvent, menu_text: str) -> bool:
        bot = self._get_bot(event)
        if bot is None:
            return False

        try:
            response = await bot.send_group_msg(
                group_id=int(event.get_group_id()),
                message=menu_text,
            )
        except Exception as exc:
            logger.error(f"[react_menu] 发送菜单失败: {exc}")
            self._stop_event(event)
            return False

        message_id = str(response.get("message_id", "") or response.get("message_id"))
        if not message_id:
            logger.error("[react_menu] 未获取到菜单消息message_id")
            self._stop_event(event)
            return False

        items = self._assign_face_ids(self.menu_items)
        if self.menu_max_reactions > 0:
            emoji_items = [item for item in items if item.get("face_id")][: self.menu_max_reactions]
        else:
            emoji_items = [item for item in items if item.get("face_id")]
        emoji_map = {
            item["face_id"]: {"command": item["command"], "label": item["label"]}
            for item in emoji_items
        }
        self._active_menus[message_id] = {
            "group_id": str(event.get_group_id()),
            "created_at": time.time(),
            "emoji_map": emoji_map,
            "items": items,
        }

        for item in emoji_items:
            face_id_str = item["face_id"]
            if not face_id_str:
                continue
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
        return True

    @filter.command("菜单")
    async def on_menu_command(self, event: AstrMessageEvent):
        if not event.get_group_id():
            return

        menu_text = self._build_text_menu(self.menu_items)
        if not await self._send_menu(event, menu_text):
            yield event.plain_result(menu_text)

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        if not event.get_group_id():
            return

        # ━━━ 三重防护：跳过 react_menu 自身推入的虚拟事件，防止无限循环 ━━━
        # 方式1: raw_message dict 检查（正常路径）
        raw = self._parse_raw_message(event)
        if raw and raw.get("_react_menu_internal"):
            logger.debug("[react_menu] 跳过内部虚拟事件，防止循环触发")
            return

        # 方式2: 兜底——raw_message 可能被平台序列化为非标准格式（如 Python repr），
        #        导致 _parse_raw_message 的 json.loads 失败返回 None。
        #        直接检查 raw_message 字符串中是否含标记。
        raw_str = ""
        message_obj = getattr(event, "message_obj", None)
        if message_obj is not None:
            raw_str = str(getattr(message_obj, "raw_message", "") or "")
        if not raw_str:
            raw_str = str(getattr(event, "raw_message", "") or "")
        if "_react_menu_internal" in raw_str:
            logger.debug("[react_menu] 跳过内部虚拟事件(raw_message字符串兜底)，防止循环触发")
            return

        # 方式3: 兜底——message_id 前缀检查（虚拟事件 message_id 以 react_menu_ 开头）
        msg_id = ""
        if message_obj is not None:
            msg_id = str(getattr(message_obj, "message_id", "") or "")
        if msg_id.startswith("react_menu_"):
            logger.debug("[react_menu] 跳过内部虚拟事件(message_id兜底)，防止循环触发")
            return

        # 方式4: 兜底——平台可能会在 commit_event 后丢失 raw_message 的标记，
        #         此时检查最近虚拟命令记录，若匹配则跳过
        try:
            recent_key = (str(event.get_group_id()), str(event.get_sender_id() or ""), str(event.message_str or ""))
            if recent_key in self._recent_virtual_commands:
                logger.debug("[react_menu] 跳过最近记录的虚拟命令，防止回环")
                return
        except Exception:
            pass

        text = (event.message_str or "").strip()
        if not text:
            return

        menu_keyword_set = {keyword.strip().lower() for keyword in self.menu_keywords if isinstance(keyword, str)}
        if text.lower() not in menu_keyword_set:
            _, menu_data = self._find_active_menu_for_group(str(event.get_group_id()))
            if menu_data and await self._handle_menu_selection(event, text, menu_data):
                return
            return

        group_id = str(event.get_group_id())
        if self.menu_repeat_block and self._has_active_menu_in_group(group_id):
            logger.info(f"[react_menu] 菜单冷却阻断: group={group_id}")
            yield event.plain_result(self.menu_repeat_reply)
            self._stop_event(event)
            return

        logger.info(f"[react_menu] 纯文本菜单触发: text={text} user={event.get_sender_id()} group={group_id}")
        menu_text = self._build_text_menu(self.menu_items)
        if not await self._send_menu(event, menu_text):
            yield event.plain_result(menu_text)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_reaction_event(self, event: AstrMessageEvent):
        await self._handle_reaction_event(event)

    async def _handle_reaction_event(self, event: AstrMessageEvent) -> None:
        raw = self._parse_raw_message(event)
        if not raw:
            logger.debug("[react_menu] 无法解析 reaction raw_message")
            return

        group_id = event.get_group_id() or str(raw.get("group_id") or raw.get("group") or "")
        if not group_id:
            logger.debug("[react_menu] reaction group_id 缺失")
            return

        notice_type = str(raw.get("notice_type") or "").lower().strip()
        if notice_type not in ("group_msg_reaction", "group_msg_emoji_like"):
            # 某些平台会把 reaction 事件塞在 message / post_type / sub_type 的组合中，这里做兼容。
            if not (raw.get("post_type") == "notice" or raw.get("type") == "notice"):
                logger.debug(f"[react_menu] 非 reaction 通知类型: notice_type={notice_type} raw={raw}")
                return

        # 按你的预期，任何表情变更事件都可以触发命令；防抖负责避免重复点击。
        # 这里不再因为 sub_type/is_add 的值而直接跳过，避免前面几项正常、后面几项被误拦住。
        sub_type = str(raw.get("sub_type") or "").lower().strip()
        if notice_type == "group_msg_reaction" and sub_type and sub_type not in {"add", "remove", "set", "cancel", "delete", ""}:
            logger.debug(f"[react_menu] 未识别的 reaction sub_type={sub_type}, 仍继续处理 raw={raw}")

        message_id = self._resolve_raw_field(raw, ("message_id", "msg_id", "message_id_str", "msgId", "messageId"))
        if not message_id:
            message_id = self._resolve_raw_field(raw.get("message", {}) if isinstance(raw.get("message"), dict) else {}, ("message_id", "msg_id", "message_id_str", "msgId", "messageId"))
        clicker_id = self._resolve_raw_field(
            raw,
            (
                "user_id",
                "operator_id",
                "target_id",
                "sender_id",
                "from_uin",
                "qq",
                "user",
                "actor_id",
                "author_id",
            ),
        )
        face_id = self._extract_face_id(raw)

        logger.info(f"[react_menu] reaction event parsed: message_id={message_id} clicker_id={clicker_id} face_id={face_id} notice_type={notice_type} raw={raw}")

        if not message_id or not clicker_id or not face_id:
            logger.debug(
                f"[react_menu] reaction 字段缺失: message_id={message_id}, clicker_id={clicker_id}, face_id={face_id}, raw={raw}"
            )
            return

        menu_data = self._active_menus.get(message_id)
        if menu_data is None:
            return

        # 忽略过期菜单
        if time.time() - menu_data["created_at"] > self.menu_timeout:
            self._active_menus.pop(message_id, None)
            return

        # 忽略菜单发送者自动贴表情引起的回调（在菜单创建后短时间内发生的 reaction）
        try:
            if time.time() - menu_data.get("created_at", 0) < 1.5:
                logger.debug(f"[react_menu] 忽略菜单创建期间的自动 reaction: message_id={message_id}")
                return
        except Exception:
            pass

        # 忽略机器人自身产生的 reaction（自贴表情或其它机器人动作）
        bot_id = ""
        try:
            bot_id = str(getattr(event, "self_id", None) or getattr(event.message_obj, "self_id", None) or raw.get("self_id") or "")
        except Exception:
            bot_id = ""
        if bot_id and clicker_id and str(clicker_id) == bot_id:
            logger.debug(f"[react_menu] 忽略机器人自身的 reaction: bot_id={bot_id} message_id={message_id}")
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
        normalized = self._normalize_command(command)
        await self._execute_as_user(event, clicker_id, group_id, normalized)
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
        if face_id is not None:
            return str(face_id)

        # OneBot v11 group_msg_emoji_like: emoji_id 在 likes 数组中
        likes = raw.get("likes")
        if isinstance(likes, list) and likes:
            first = likes[0]
            if isinstance(first, dict):
                fid = first.get("emoji_id") or first.get("face_id")
                if fid is not None:
                    return str(fid)

        message = raw.get("message")
        if isinstance(message, dict):
            face = message.get("face") or message.get("emoji")
            if isinstance(face, dict):
                face_id = face.get("id") or face.get("face_id") or face.get("emoji_id")
                if face_id is not None:
                    return str(face_id)
        elif isinstance(message, list):
            for item in message:
                if not isinstance(item, dict):
                    continue
                if item.get("type") in {"face", "emoji"}:
                    face_id = item.get("id") or item.get("face_id") or item.get("emoji_id")
                    if face_id is not None:
                        return str(face_id)
        elif isinstance(message, str):
            # 支持部分平台直接在 notice raw_message 中带 CQ 码文本
            import re

            match = re.search(r"(?:face|emoji),id=(\d+)", message)
            if match:
                return match.group(1)

        # 兼容一些不常见字段名
        for key in ("face", "emoji", "emoji_id", "face_id"):
            val = raw.get(key)
            if val is not None:
                return str(val)

        return ""

    @staticmethod
    def _resolve_raw_field(raw: dict[str, Any], keys: tuple[str, ...]) -> str:
        for key in keys:
            value = raw.get(key)
            if value is not None and str(value).strip():
                return str(value)
            # 支持嵌套 data 字段
            if isinstance(value, dict):
                for nested in ("user_id", "operator_id", "target_id", "message_id", "face_id", "emoji_id"):
                    nested_value = value.get(nested)
                    if nested_value is not None and str(nested_value).strip():
                        return str(nested_value)
        return ""

    @staticmethod
    def _resolve_session_identity(event: AstrMessageEvent, group_id: str) -> str:
        session = None
        session = getattr(event, "unified_msg_origin", None) or getattr(event, "session_id", None)
        if session:
            return session

        if hasattr(event, "get_platform_name"):
            try:
                platform_name = event.get_platform_name()
            except Exception:
                platform_name = None
            if platform_name:
                return f"{platform_name}:group_message:{group_id}"

        platform_type = getattr(event, "platform_id", None)
        if platform_type:
            return f"{platform_type}:group_message:{group_id}"

        return f"aiocqhttp:group_message:{group_id}"

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
                fake_msg.message_str = command
                fake_msg.message = [Plain(text=command)]
                fake_msg.raw_message = {"_react_menu_internal": True}

                # 记录最近虚拟命令，防止平台在 commit_event 后去掉 raw 标记导致回环
                try:
                    key = (str(group_id), str(user_id), str(command))
                    self._recent_virtual_commands[key] = time.time()
                except Exception:
                    pass

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
                    logger.info(f"[react_menu] 已推入虚拟事件: user={user_id} cmd={command}")
                    return
            except Exception as exc:
                logger.warning(f"[react_menu] 构造虚拟事件失败: {exc}")

        try:
            session = getattr(event, "unified_msg_origin", None) or getattr(event, "session_id", None)
            if not session:
                session = self._resolve_session_identity(event, group_id)
            await self.context.send_message(
                session=session,
                message_chain=MessageChain([Plain(command)]),
            )
            logger.info(f"[react_menu] fallback 发送指令文本: session={session} cmd={command}")
        except Exception as exc:
            logger.error(f"[react_menu] 触发目标命令失败: {exc}")
