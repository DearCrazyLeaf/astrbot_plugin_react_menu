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
_OPTION_GROUPS = {
    "interaction_settings": ("menu_timeout_seconds", "debounce_seconds", "menu_repeat_block", "menu_repeat_reply"),
    "appearance_settings": ("menu_header_image_url", "menu_divider_char", "menu_divider_length", "menu_footer_text"),
    "reaction_settings": ("menu_max_reactions", "face_pool"),
}
_DEFAULT_MENU_CONFIG = [{
    "__template_key": "menu",
    "menu_id": "entertainment",
    "name": "娱乐菜单",
    "keywords": ["菜单"],
    "title": "🎮 菜单",
    "items": [
        {"label": "每日老婆", "command": "抽老婆", "face_id": ""},
        {"label": "今日小猪", "command": "今日小猪", "face_id": ""},
        {"label": "随机VTB", "command": "dd", "face_id": ""},
    ],
}]

try:
    from astrbot.api.platform import AstrBotMessage, MessageMember
except ImportError:
    AstrBotMessage = None  # type: ignore
    MessageMember = None  # type: ignore

# Auto-generated from QFace QQ emoji index (https://koishi.js.org/QFace)
# syncedAt: 2026-09-28T03:43:28.805Z
# Only QQ system-emoji (EmojiType=1) ids that currently exist in QQ are listed.
# Each id maps to a single canonical emoji; ids sharing a name are visual duplicates
# (e.g. 1<->450 both are "撇嘴") and are de-duplicated by name during assignment.
# Source of truth for face_id validity: ids absent here are deprecated/invalid on modern QQ.
_QQ_FACE_NAMES: dict[str, str] = {
    "0": "惊讶",
    "1": "撇嘴",
    "2": "色",
    "3": "发呆",
    "4": "得意",
    "5": "流泪",
    "6": "害羞",
    "7": "闭嘴",
    "8": "睡",
    "9": "大哭",
    "10": "尴尬",
    "11": "发怒",
    "12": "调皮",
    "13": "呲牙",
    "14": "微笑",
    "15": "难过",
    "16": "酷",
    "18": "抓狂",
    "19": "吐",
    "20": "偷笑",
    "21": "可爱",
    "22": "白眼",
    "23": "傲慢",
    "24": "饥饿",
    "25": "困",
    "26": "惊恐",
    "27": "流汗",
    "28": "憨笑",
    "29": "悠闲",
    "30": "奋斗",
    "31": "咒骂",
    "32": "疑问",
    "33": "嘘",
    "34": "晕",
    "35": "折磨",
    "36": "衰",
    "37": "骷髅",
    "38": "敲打",
    "39": "再见",
    "41": "发抖",
    "42": "爱情",
    "43": "跳跳",
    "46": "猪头",
    "49": "拥抱",
    "53": "蛋糕",
    "55": "炸弹",
    "56": "刀",
    "59": "便便",
    "60": "咖啡",
    "63": "玫瑰",
    "64": "凋谢",
    "66": "爱心",
    "67": "心碎",
    "74": "太阳",
    "75": "月亮",
    "76": "赞",
    "77": "踩",
    "78": "握手",
    "79": "胜利",
    "85": "飞吻",
    "86": "怄火",
    "89": "西瓜",
    "96": "冷汗",
    "97": "擦汗",
    "98": "抠鼻",
    "99": "鼓掌",
    "100": "糗大了",
    "101": "坏笑",
    "102": "左哼哼",
    "103": "右哼哼",
    "104": "哈欠",
    "105": "鄙视",
    "106": "委屈",
    "107": "快哭了",
    "108": "阴险",
    "109": "左亲亲",
    "110": "吓",
    "111": "可怜",
    "112": "菜刀",
    "114": "篮球",
    "116": "示爱",
    "118": "抱拳",
    "119": "勾引",
    "120": "拳头",
    "121": "差劲",
    "122": "爱你",
    "123": "NO",
    "124": "OK",
    "125": "转圈",
    "129": "挥手",
    "137": "鞭炮",
    "144": "喝彩",
    "146": "爆筋",
    "147": "棒棒糖",
    "148": "喝奶",
    "169": "手枪",
    "171": "茶",
    "172": "眨眼睛",
    "173": "泪奔",
    "174": "无奈",
    "175": "卖萌",
    "176": "小纠结",
    "177": "喷血",
    "178": "斜眼笑",
    "179": "doge",
    "180": "惊喜",
    "181": "戳一戳",
    "182": "笑哭",
    "183": "我最美",
    "185": "羊驼",
    "187": "幽灵",
    "193": "大笑",
    "194": "不开心",
    "198": "呃",
    "200": "求求",
    "201": "点赞",
    "202": "无聊",
    "203": "托脸",
    "204": "吃",
    "206": "害怕",
    "210": "飙泪",
    "211": "我不看",
    "212": "托腮",
    "214": "啵啵",
    "215": "糊脸",
    "216": "拍头",
    "217": "扯一扯",
    "218": "舔一舔",
    "219": "蹭一蹭",
    "221": "顶呱呱",
    "222": "抱抱",
    "223": "暴击",
    "224": "开枪",
    "225": "撩一撩",
    "226": "拍桌",
    "227": "拍手",
    "229": "干杯",
    "230": "嘲讽",
    "231": "哼",
    "232": "佛系",
    "233": "掐一掐",
    "235": "颤抖",
    "237": "偷看",
    "238": "扇脸",
    "239": "原谅",
    "240": "喷脸",
    "241": "生日快乐",
    "243": "甩头",
    "244": "扔狗",
    "262": "脑阔疼",
    "263": "沧桑",
    "264": "捂脸",
    "265": "辣眼睛",
    "266": "哦哟",
    "267": "头秃",
    "268": "问号脸",
    "269": "暗中观察",
    "270": "emm",
    "271": "吃瓜",
    "272": "呵呵哒",
    "273": "我酸了",
    "277": "汪汪",
    "278": "汗",
    "281": "无眼笑",
    "282": "敬礼",
    "283": "狂笑",
    "284": "面无表情",
    "285": "摸鱼",
    "286": "魔鬼笑",
    "287": "哦",
    "288": "请",
    "289": "睁眼",
    "290": "敲开心",
    "292": "让我康康",
    "293": "摸锦鲤",
    "294": "期待",
    "295": "拿到红包",
    "297": "拜谢",
    "298": "元宝",
    "299": "牛啊",
    "300": "胖三斤",
    "301": "好闪",
    "302": "左拜年",
    "303": "右拜年",
    "305": "右亲亲",
    "306": "牛气冲天",
    "307": "喵喵",
    "311": "打call",
    "312": "变形",
    "314": "仔细分析",
    "317": "菜汪",
    "318": "崇拜",
    "319": "比心",
    "320": "庆祝",
    "322": "拒绝",
    "323": "嫌弃",
    "324": "吃糖",
    "325": "惊吓",
    "326": "生气",
    "332": "举牌牌",
    "333": "烟花",
    "334": "虎虎生威",
    "336": "豹富",
    "337": "花朵脸",
    "338": "我想开了",
    "339": "舔屏",
    "341": "打招呼",
    "342": "酸Q",
    "343": "我方了",
    "344": "大怨种",
    "345": "红包多多",
    "346": "你真棒棒",
    "347": "大展宏兔",
    "348": "福萝卜",
    "349": "坚强",
    "350": "贴贴",
    "351": "敲敲",
    "352": "咦",
    "353": "拜托",
    "354": "尊嘟假嘟",
    "355": "耶",
    "356": "666",
    "357": "裂开",
    "358": "骰子",
    "359": "包剪锤",
    "360": "亲亲",
    "361": "狗狗笑哭",
    "362": "好兄弟",
    "363": "狗狗可怜",
    "364": "超级赞",
    "365": "狗狗生气",
    "366": "芒狗",
    "367": "狗狗疑问",
    "368": "奥特笑哭",
    "369": "彩虹",
    "370": "祝贺",
    "371": "冒泡",
    "372": "气呼呼",
    "373": "忙",
    "374": "波波流泪",
    "375": "超级鼓掌",
    "376": "跺脚",
    "377": "嗨",
    "378": "企鹅笑哭",
    "379": "企鹅流泪",
    "380": "真棒",
    "381": "路过",
    "382": "emo",
    "383": "企鹅爱心",
    "384": "晚安",
    "385": "太气了",
    "386": "呜呜呜",
    "387": "太好笑",
    "388": "太头疼",
    "389": "太赞了",
    "390": "太头秃",
    "391": "太沧桑",
    "392": "龙年快乐",
    "393": "新年中龙",
    "394": "新年大龙",
    "395": "略略略",
    "396": "狼狗",
    "397": "抛媚眼",
    "398": "超级ok",
    "399": "tui",
    "400": "快乐",
    "401": "超级转圈",
    "402": "别说话",
    "403": "出去玩",
    "404": "闪亮登场",
    "405": "好运来",
    "406": "姐是女王",
    "407": "我听听",
    "408": "臭美",
    "409": "送你花花",
    "410": "么么哒",
    "411": "一起嗨",
    "412": "开心",
    "413": "摇起来",
    "415": "划龙舟",
    "416": "中龙舟",
    "417": "大龙舟",
    "418": "填罐罐",
    "419": "火车",
    "420": "中火车",
    "421": "大火车",
    "422": "粽于等到你",
    "423": "复兴号",
    "424": "续标识",
    "425": "求放过",
    "426": "玩火",
    "427": "偷感",
    "428": "收到",
    "429": "蛇年快乐",
    "430": "蛇身",
    "431": "蛇尾",
    "432": "灵蛇献瑞",
    "433": "大鸽",
    "434": "鸽来了",
    "435": "关我鸟事",
    "436": "跟鸽走",
    "437": "鸽鸽生气",
    "438": "可靠",
    "439": "鸽瞅瞅",
    "440": "鸽喜欢",
    "441": "相信鸽",
    "442": "鸽王",
    "443": "戳一下",
    "444": "超级6",
    "445": "比个心",
    "446": "超级心碎",
    "447": "太赞了",
    "448": "放大招",
    "449": "+1",
    "450": "撇嘴",
    "451": "色",
    "452": "微笑",
    "453": "发呆",
    "454": "得意",
    "455": "害羞",
    "456": "闭嘴",
    "457": "睡",
    "458": "我吗",
    "459": "优雅",
    "460": "硬撑",
    "461": "宕机",
    "462": "无语",
    "463": "新年快乐",
    "464": "马上到",
    "465": "拆红包",
    "466": "羞羞哒",
    "467": "摇花手",
    "468": "失眠",
    "469": "坚毅",
    "470": "马到成功",
    "471": "深情",
    "472": "心动",
    "473": "爱意",
    "474": "给你一拳",
    "475": "干饭",
    "476": "不是吧",
    "477": "你懂的",
    "478": "对的对的",
    "479": "不对不对",
    "480": "散味儿",
    "481": "学习",
    "482": "热化了",
    "483": "略",
    "484": "比爱心",
    "485": "开学啦",
    "486": "开学啦2",
    "487": "开学啦3",
    "488": "开学大吉",
    "489": "知识增加",
    "490": "能送我吗",
    "491": "自信学霸",
    "492": "让我细品",
    "493": "又是早八",
    "494": "举杯邀月",
    "495": "兔来",
    "496": "阴晴圆缺",
    "497": "休假了",
    "498": "中!",
    "499": "观月C位",
    "500": "秋秋赏月",
    "501": "秋秋之约",
    "502": "秋秋泛舟",
    "503": "秋愿达成",
    "504": "同你玩",
    "505": "送花花",
    "506": "捡到宝了",
    "507": "被发现了",
}

_DEFAULT_FACE_POOL: list[str] = [
    "5", "9", "10", "14", "18", "21", "23", "25", "27", "29", "32", "49", "53", "55", "59", "60", "63", "66", "74", "79", "89", "96", "99", "100", "105", "120", "123", "124", "129", "144", "147", "171", "175", "179", "182", "183", "201",
]

_FALLBACK_FACE_IDS: list[str] = [
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "18", "19", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33", "34", "35", "36", "37", "38", "39", "41", "42", "43", "46", "49", "53", "55", "56", "59", "60", "63", "64", "66", "67", "74", "75", "76", "77", "78", "79", "85", "86", "89", "96", "97", "98", "99", "100", "101", "102", "103", "104", "105", "106", "107", "108", "109", "110", "111", "112", "114", "116", "118", "119", "120", "121", "122", "123", "124", "125", "129", "137", "144", "146", "147", "148", "169", "171", "172", "173", "174", "175", "176", "177", "178", "179", "180", "181", "182", "183", "185", "187", "193", "194", "198", "200", "201", "202", "203", "204", "206", "210", "211", "212", "214", "215", "216", "217", "218", "219", "221", "222", "223", "224", "225", "226", "227", "229", "230", "231", "232", "233", "235", "237", "238", "239", "240", "241", "243", "244", "262", "263", "264", "265", "266", "267", "268", "269", "270", "271", "272", "273", "277", "278", "281", "282", "283", "284", "285", "286", "287", "288", "289", "290", "292", "293", "294", "295", "297", "298", "299", "300", "301", "302", "303", "305", "306", "307", "311", "312", "314", "317", "318", "319", "320", "322", "323", "324", "325", "326", "332", "333", "334", "336", "337", "338", "339", "341", "342", "343", "344", "345", "346", "347", "348", "349", "350", "351", "352", "353", "354", "355", "356", "357", "358", "359", "360", "361", "362", "363", "364", "365", "366", "367", "368", "369", "370", "371", "372", "373", "374", "375", "376", "377", "378", "379", "380", "381", "382", "383", "384", "385", "386", "387", "388", "389", "390", "391", "392", "393", "394", "395", "396", "397", "398", "399", "400", "401", "402", "403", "404", "405", "406", "407", "408", "409", "410", "411", "412", "413", "415", "416", "417", "418", "419", "420", "421", "422", "423", "424", "425", "426", "427", "428", "429", "430", "431", "432", "433", "434", "435", "436", "437", "438", "439", "440", "441", "442", "443", "444", "445", "446", "447", "448", "449", "450", "451", "452", "453", "454", "455", "456", "457", "458", "459", "460", "461", "462", "463", "464", "465", "466", "467", "468", "469", "470", "471", "472", "473", "474", "475", "476", "477", "478", "479", "480", "481", "482", "483", "484", "485", "486", "487", "488", "489", "490", "491", "492", "493", "494", "495", "496", "497", "498", "499", "500", "501", "502", "503", "504", "505", "506", "507",
]


class ReactMenuPlugin(Star):
    def __init__(self, context: Context, config: Any):
        super().__init__(context)
        self.context = context
        self.config = config
        self._migrate_option_groups()

        self.menu_header_image_url = str(self._option_get("menu_header_image_url", "") or "").strip()
        self.menu_divider_char = str(self._option_get("menu_divider_char", "─"))[:1] or "─"
        self.menu_divider_length = int(self._option_get("menu_divider_length", 28))
        self.menu_footer_text = str(
            self._option_get(
                "menu_footer_text",
                "👆 下方按顺序贴表情，第1个表情对应第1项，第2个表情对应第2项。也可直接回复序号或菜单内容触发。",
            )
            or ""
        )
        self.menu_timeout = int(self._option_get("menu_timeout_seconds", 60))
        self.debounce_seconds = int(self._option_get("debounce_seconds", 3))
        self.menu_max_reactions = int(self._option_get("menu_max_reactions", 20) or 0)
        self.menu_repeat_block = bool(self._option_get("menu_repeat_block", True))
        self.menu_repeat_reply = str(self._option_get("menu_repeat_reply", "当前菜单已经生效，正在冷却中，直接点表情或发序号/内容即可触发~"))
        self.face_pool = self._normalize_face_pool(self._option_get("face_pool", []))
        self._load_menu_profiles()
        self._active_menus: dict[tuple[str, str], dict[str, Any]] = {}
        self._recent_virtual_commands: dict[tuple[str, str, str, str], float] = {}
        self._debounce: dict[tuple[str, str, str, str], float] = {}
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        try:
            self._data_dir = StarTools.get_data_dir(PLUGIN_ID)
        except Exception:
            self._data_dir = None

        logger.info(
            f"[react_menu] 已加载，全局菜单={len(self.global_menus)} 会话配置={len(self.session_menus)} face_pool={len(self.face_pool)}"
        )

    def _migrate_option_groups(self) -> None:
        if self._config_get("_settings_grouped", False):
            return
        for group, keys in _OPTION_GROUPS.items():
            values = self._config_get(group, {})
            values = dict(values) if isinstance(values, dict) else {}
            for key in keys:
                legacy = self._config_get(key, None)
                if legacy is not None:
                    values[key] = legacy
                self.config[key] = None
            self.config[group] = values
        self.config["_settings_grouped"] = True
        if hasattr(self.config, "save_config"):
            try:
                self.config.save_config()
            except Exception as exc:
                logger.error(f"[react_menu] 设置分组迁移保存失败: {exc}")

    def _option_get(self, key: str, default: Any) -> Any:
        for group, keys in _OPTION_GROUPS.items():
            if key in keys:
                values = self._config_get(group, {})
                return values.get(key, default) if isinstance(values, dict) else default
        return default

    def _load_menu_profiles(self) -> None:
        settings = self._config_get("global_settings", {})
        settings = dict(settings) if isinstance(settings, dict) else {}
        changed = False
        if self._migrate_menu_item_lists(settings):
            changed = True
        defaults = self._normalize_menus(_DEFAULT_MENU_CONFIG)
        previous = self._normalize_menus(self._config_get("menus", []))
        legacy = self._legacy_menu()
        if not previous or (legacy and self._menu_signature(previous) == self._menu_signature(defaults)):
            previous = legacy
        if previous:
            current = self._normalize_menus(settings.get("menus", []))
            if "menus" not in settings or self._menu_signature(current) == self._menu_signature(defaults):
                settings["menus"] = [{"__template_key": "menu", **menu} for menu in previous]
            # Consume old fields once so clearing new cards never revives old menus.
            self.config["menus"] = []
            self.config["menu_items"] = []
            self.config["menu_keywords"] = []
            self.config["menu_title"] = ""
            changed = True

        old_settings = self._config_get("session_settings", {})
        old_sessions = old_settings.get("sessions", []) if isinstance(old_settings, dict) else []
        if isinstance(old_sessions, list) and old_sessions:
            if not settings.get("umo_menus"):
                flattened = []
                seen = set()
                for entry in old_sessions:
                    if not isinstance(entry, dict):
                        continue
                    umo = self._normalize_umo(entry.get("umo"))
                    if umo in seen:
                        continue
                    if umo:
                        seen.add(umo)
                    menus = entry.get("menus", [])
                    menus = [menu for menu in menus if isinstance(menu, dict)] if isinstance(menus, list) else []
                    # Empty old sessions remain registered with no usable menu.
                    for menu in menus or [{}]:
                        flattened.append({**menu, "__template_key": "menu", "umo": entry.get("umo", "")})
                settings["umo_menus"] = flattened
            self.config["session_settings"] = {"sessions": []}
            changed = True

        # The old nested session format is flattened above, so migrate its item
        # objects in the same load before persisting the new WebUI shape.
        if self._migrate_menu_item_lists(settings):
            changed = True

        if changed:
            self.config["global_settings"] = settings
            if hasattr(self.config, "save_config"):
                try:
                    self.config.save_config()
                except Exception as exc:
                    logger.error(f"[react_menu] 菜单迁移配置保存失败: {exc}")

        self.global_menus = self._normalize_menus(settings.get("menus", []))
        raw_entries = settings.get("umo_menus", [])
        # A nonempty list always enables strict UMO mode, even if a card is invalid.
        self._umo_mode = bool(raw_entries)
        grouped: dict[str, list[dict[str, Any]]] = {}
        if isinstance(raw_entries, list):
            for entry in raw_entries:
                umo = self._normalize_umo(entry.get("umo")) if isinstance(entry, dict) else ""
                if not umo:
                    logger.warning("[react_menu] UMO 菜单的会话标识无效，已忽略；全局菜单仍被停用")
                    continue
                grouped.setdefault(umo, []).append(entry)
        self.session_menus = {umo: self._normalize_menus(entries) for umo, entries in grouped.items()}

    def _migrate_menu_item_lists(self, settings: dict[str, Any]) -> bool:
        """Flatten object menu items before the WebUI's simple list editor sees them."""
        changed = False
        for menu_list_name in ("menus", "umo_menus"):
            entries = settings.get(menu_list_name)
            if not isinstance(entries, list):
                continue
            for menu in entries:
                if not isinstance(menu, dict) or not isinstance(menu.get("items"), list):
                    continue
                converted = []
                for item in menu["items"]:
                    text = self._menu_item_to_text(item)
                    if text:
                        converted.append(text)
                if converted != menu["items"]:
                    menu["items"] = converted
                    changed = True
        return changed

    def _legacy_menu(self) -> list[dict[str, Any]]:
        items = self._normalize_menu_items(self._config_get("menu_items", None))
        keywords = self._config_get("menu_keywords", ["菜单"])
        if isinstance(keywords, str):
            keywords = [keywords]
        if not isinstance(keywords, list):
            keywords = []
        keywords = [str(value).strip() for value in keywords if str(value).strip()]
        if not items:
            return []
        return [{
            "menu_id": "legacy",
            "name": "娱乐菜单",
            "keywords": keywords or ["菜单"],
            "title": str(self._config_get("menu_title", "🎮 菜单")),
            "items": items,
        }]

    def _normalize_menus(self, raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        menus: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        seen_keywords: set[str] = set()
        for index, value in enumerate(raw, start=1):
            if not isinstance(value, dict):
                continue
            keywords = value.get("keywords", [])
            if isinstance(keywords, str):
                keywords = [keywords]
            if not isinstance(keywords, list):
                continue
            clean_keywords: list[str] = []
            menu_keywords: set[str] = set()
            for raw_keyword in keywords:
                keyword = str(raw_keyword).strip().lstrip("/").strip()
                normalized = keyword.casefold()
                if keyword and normalized not in menu_keywords:
                    clean_keywords.append(keyword)
                    menu_keywords.add(normalized)
            clean_keywords = [
                keyword for keyword in clean_keywords
                if keyword.casefold() not in seen_keywords
            ]
            items = self._normalize_menu_items(value.get("items", []))
            if not clean_keywords or not items:
                continue
            menu_id = str(value.get("menu_id") or clean_keywords[0].casefold()).strip()
            if menu_id in seen_ids:
                menu_id = f"{menu_id}:{index}"
            seen_ids.add(menu_id)
            seen_keywords.update(keyword.casefold() for keyword in clean_keywords)
            menus.append({
                "menu_id": menu_id,
                "name": str(value.get("name") or f"菜单 {index}").strip(),
                "keywords": clean_keywords,
                "title": str(value.get("title") or value.get("name") or "互动菜单"),
                "items": items,
            })
        return menus

    @staticmethod
    def _normalize_umo(raw: Any) -> str:
        value = str(raw or "").strip()
        parts = value.split(":", 2)
        if len(parts) != 3 or not all(part.strip() for part in parts):
            return ""
        return f"{parts[0].strip()}:{parts[1].strip()}:{parts[2].strip()}"

    def _menus_for_session(self, session_id: str) -> list[dict[str, Any]] | None:
        if not self._umo_mode:
            return self.global_menus
        return self.session_menus.get(session_id)

    def _menu_for_session_keyword(
        self, session_id: str, keyword: str
    ) -> dict[str, Any] | None:
        menus = self._menus_for_session(session_id)
        if not menus:
            return None
        normalized = (keyword or "").strip().lstrip("/").casefold()
        return next(
            (menu for menu in menus if normalized in {value.casefold() for value in menu["keywords"]}),
            None,
        )

    @staticmethod
    def _menu_signature(menus: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
        return [
            (
                tuple(keyword.casefold() for keyword in menu["keywords"]),
                menu["title"],
                tuple((item["label"], item["command"], item["face_id"]) for item in menu["items"]),
            )
            for menu in menus
        ]

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
        return list(_DEFAULT_FACE_POOL)

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
                label, command, face_id = self._split_menu_item_text(text)
                if not label or not command:
                    continue
                items.append({"label": label, "command": command, "face_id": face_id})
                continue

        return items

    @staticmethod
    def _menu_item_to_text(raw_value: Any) -> str:
        if isinstance(raw_value, str):
            return raw_value.strip()
        if not isinstance(raw_value, dict):
            return ""

        label = str(raw_value.get("label", "")).strip()
        command = str(raw_value.get("command", label or raw_value.get("desc", ""))).strip()
        face_id = str(raw_value.get("face_id", "")).strip()
        if not label and command:
            label = command.lstrip("/")
        if not command and label:
            command = label
        if not label or not command:
            return ""
        if label == command and not face_id:
            return label
        return ",".join(value for value in (label, command, face_id) if value)

    @staticmethod
    def _split_menu_item_text(text: str) -> tuple[str, str, str]:
        text = (text or "").strip()
        if not text:
            return "", "", ""

        # 优先按逗号分隔
        for sep in (",", "，"):
            if sep in text:
                parts = text.split(sep, 2)
                left = parts[0]
                right = parts[1]
                face_id = parts[2].strip() if len(parts) == 3 else ""
                label = left.strip().lstrip("/")
                command = right.strip()
                if not label:
                    label = command.lstrip("/")
                if not command:
                    command = label
                return label, command, face_id

        # 支持 `显示 / 指令` 或 `显示/指令`
        if "/" in text and text.find("/") > 0:
            left, right = text.split("/", 1)
            label = left.strip()
            command = right.strip()
            if not label:
                label = command.lstrip("/")
            if not command:
                command = label
            return label, command, ""

        # 最后按第一个空格分隔为 label 和 command
        if " " in text:
            left, right = text.split(" ", 1)
            label = left.strip()
            command = right.strip()
            if not label:
                label = command.lstrip("/")
            if not command:
                command = label
            return label, command, ""

        return text, text, ""

    @staticmethod
    def _normalize_command(command: str) -> str:
        command = (command or "").strip()
        if not command:
            return ""
        if not command.startswith("/"):
            return "/" + command
        return command

    @staticmethod
    def _face_name(face_id: str) -> str | None:
        # Canonical QQ emoji name for a face_id. Returns None when the id is not
        # a verified-present QQ system emoji (e.g. the deprecated ids 128/151
        # that collapse to a placeholder/default emoji and cause duplicate
        # reactions on modern QQ clients).
        if face_id is None:
            return None
        return _QQ_FACE_NAMES.get(str(face_id).strip())

    @staticmethod
    def _face_identity(face_id: str) -> str:
        # Canonical key to detect visually-identical emojis: two face_ids that
        # render the same emoji share the same name (e.g. 1 and 450 are both
        # "撇嘴"). Unknown ids fall back to their own string so that exact
        # numeric duplicates are still de-duplicated.
        name = ReactMenuPlugin._face_name(face_id)
        return name if name is not None else str(face_id).strip()

    def _assign_face_ids(self, items: list[dict[str, str]]) -> list[dict[str, str]]:
        items = [dict(item) for item in items]

        # Canonical identities already bound by explicitly-configured face_ids,
        # so auto-assigned ids never collide with them (visual duplicates).
        used_identities = {
            self._face_identity(item["face_id"])
            for item in items
            if item.get("face_id")
        }

        unassigned = [item for item in items if not item.get("face_id")]
        if not unassigned:
            return items

        # Build the candidate pool: configured face_pool first, then the verified
        # fallback ids. Only ids whose visual emoji is NOT already in use are
        # kept, guaranteeing every reaction on the menu renders a distinct emoji.
        available: list[str] = []
        for fid in list(self.face_pool) + list(_FALLBACK_FACE_IDS):
            name = self._face_name(fid)
            if name is None:
                # Deprecated/invalid face_id -> would render a duplicate or
                # placeholder emoji on modern QQ. Never auto-assign it.
                continue
            identity = name
            if identity in used_identities:
                continue
            used_identities.add(identity)
            available.append(str(fid))

        if len(available) < len(unassigned):
            logger.warning(
                f"[react_menu] face_pool 可用 face_id 不足，可能出现重复ID映射或部分菜单无法贴表情："
                f"需要={len(unassigned)} 可用={len(available)}"
            )

        random.shuffle(available)
        for item in unassigned:
            if not available:
                item["face_id"] = "0"
            else:
                item["face_id"] = str(available.pop())

        return items

    def _find_active_menu_for_group(
        self, group_id: str, session_id: str | None = None, menu_id: str | None = None
    ) -> dict[str, Any] | None:
        now = time.time()
        active = [
            data for data in self._active_menus.values()
            if data.get("group_id") == group_id
            and (session_id is None or data.get("session_id") == session_id)
            and (menu_id is None or data.get("menu_id") == menu_id)
            and now - data["created_at"] <= data.get("timeout", self.menu_timeout)
        ]
        if not active:
            return None
        return max(active, key=lambda data: data["created_at"])

    def _find_active_menu_for_selection(
        self, group_id: str, session_id: str, text: str
    ) -> dict[str, Any] | None:
        now = time.time()
        active = [
            data for data in self._active_menus.values()
            if data.get("group_id") == group_id
            and data.get("session_id") == session_id
            and now - data["created_at"] <= data.get("timeout", self.menu_timeout)
        ]
        if not active:
            return None
        latest = max(active, key=lambda data: data["created_at"])
        return latest if self._match_menu_item(text, latest.get("items", [])) else None

    def _has_active_menu_in_group(
        self, group_id: str, session_id: str | None = None, menu_id: str | None = None
    ) -> bool:
        return self._find_active_menu_for_group(group_id, session_id, menu_id) is not None

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
            expired = [
                key for key, data in self._active_menus.items()
                if now - data["created_at"] > data.get("timeout", self.menu_timeout)
            ]
            for key in expired:
                self._active_menus.pop(key, None)
                logger.debug(f"[react_menu] 清理过期菜单: message_id={key[1]}")

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

    def _build_text_menu(self, menu: dict[str, Any]) -> str:
        lines = []
        if self.menu_header_image_url:
            lines.append(f"[CQ:image,file={self.menu_header_image_url}]")
            lines.append("")
        lines.append(menu["title"])
        lines.append(self.menu_divider_char * self.menu_divider_length)
        for index, item in enumerate(menu["items"], start=1):
            lines.append(f"  {index}. {item['label']}")
        lines.append(self.menu_divider_char * self.menu_divider_length)
        if self.menu_footer_text:
            lines.append(self.menu_footer_text)
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

    async def _send_menu(self, event: AstrMessageEvent, menu: dict[str, Any]) -> bool:
        bot = self._get_bot(event)
        if bot is None:
            return False

        try:
            response = await bot.send_group_msg(
                group_id=int(event.get_group_id()),
                message=self._build_text_menu(menu),
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

        items = self._assign_face_ids(menu["items"])
        if self.menu_max_reactions > 0:
            emoji_items = [item for item in items if item.get("face_id")][: self.menu_max_reactions]
        else:
            emoji_items = [item for item in items if item.get("face_id")]
        emoji_map = {
            item["face_id"]: {"command": item["command"], "label": item["label"]}
            for item in emoji_items
        }
        session_id = self._resolve_session_identity(event, str(event.get_group_id()))
        active_key = (session_id, message_id)
        self._active_menus[active_key] = {
            "group_id": str(event.get_group_id()),
            "session_id": session_id,
            "menu_id": menu["menu_id"],
            "created_at": time.time(),
            "timeout": self.menu_timeout,
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

    async def _open_menu(
        self, event: AstrMessageEvent, menu: dict[str, Any], group_id: str
    ) -> str | None:
        """Open a menu, returning any cooldown or plain-text fallback reply."""
        session_id = self._resolve_session_identity(event, group_id)
        if self.menu_repeat_block and self._has_active_menu_in_group(
            group_id, session_id, menu["menu_id"]
        ):
            logger.info(f"[react_menu] 菜单冷却阻断: group={group_id}")
            self._stop_event(event)
            return self.menu_repeat_reply

        if not await self._send_menu(event, menu):
            return self._build_text_menu(menu)
        return None

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        if not event.get_group_id():
            return
        session_id = self._resolve_session_identity(event, str(event.get_group_id()))

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
            recent_key = (
                session_id,
                str(event.get_group_id()),
                str(event.get_sender_id() or ""),
                str(event.message_str or ""),
            )
            if recent_key in self._recent_virtual_commands:
                logger.debug("[react_menu] 跳过最近记录的虚拟命令，防止回环")
                return
        except Exception:
            pass

        text = (event.message_str or "").strip()
        if not text:
            return

        configured_menus = self._menus_for_session(session_id)
        if not configured_menus:
            return
        menu = self._menu_for_session_keyword(session_id, text)
        if menu is None:
            menu_data = self._find_active_menu_for_selection(
                str(event.get_group_id()), session_id, text
            )
            if menu_data and await self._handle_menu_selection(event, text, menu_data):
                return
            return

        group_id = str(event.get_group_id())
        logger.info(f"[react_menu] 纯文本菜单触发: text={text} user={event.get_sender_id()} group={group_id}")
        reply = await self._open_menu(event, menu, group_id)
        if reply is not None:
            yield event.plain_result(reply)

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

        session_id = self._resolve_session_identity(event, str(group_id))
        if not self._menus_for_session(session_id):
            return
        menu_data = self._active_menus.get((session_id, message_id))
        if menu_data is None:
            return

        # 忽略过期菜单
        if time.time() - menu_data["created_at"] > menu_data.get("timeout", self.menu_timeout):
            self._active_menus.pop((session_id, message_id), None)
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

        debounce_key = (session_id, message_id, clicker_id, face_id)
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
        platform_id = None
        if hasattr(event, "get_platform_id"):
            try:
                platform_id = event.get_platform_id()
            except Exception:
                platform_id = None
        if platform_id:
            return f"{platform_id!s}:GroupMessage:{group_id}"

        session = getattr(event, "unified_msg_origin", None) or getattr(event, "session_id", None)
        expected_suffix = f":GroupMessage:{group_id}"
        if session and str(session).endswith(expected_suffix):
            return str(session)

        platform_id = getattr(event, "platform_id", None)
        if platform_id:
            return f"{platform_id!s}:GroupMessage:{group_id}"

        return f"aiocqhttp:GroupMessage:{group_id}"

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
        session_id = self._resolve_session_identity(event, group_id)
        menu = self._menu_for_session_keyword(session_id, command)
        if menu is not None:
            # Opening a menu does not execute its items. Handle navigation here
            # before creating a virtual event, which our loop guard would ignore.
            logger.info(f"[react_menu] 菜单项打开菜单: user={user_id} group={group_id} command={command}")
            reply = await self._open_menu(event, menu, group_id)
            if reply is not None:
                await event.send(event.plain_result(reply))
            self._stop_event(event)
            return

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
                    key = (session_id, str(group_id), str(user_id), str(command))
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
            await self.context.send_message(
                session=session_id,
                message_chain=MessageChain([Plain(command)]),
            )
            logger.info(f"[react_menu] fallback 发送指令文本: session={session_id} cmd={command}")
        except Exception as exc:
            logger.error(f"[react_menu] 触发目标命令失败: {exc}")
