# 表情回应菜单

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![AstrBot](https://img.shields.io/badge/AstrBot-v4.12%2B-brightgreen)
![License](https://img.shields.io/badge/License-GPL--3.0-orange)

![views](https://count.getloli.com/get/@astrbotchuanhuatong?theme=booru-jaypee)

---

## ✅ 简介

`astrbot_plugin_react_menu` 是一款 AstrBot 插件：群内发送 `菜单` 关键词后，插件会生成一条带 emoji 的互动菜单，群员点击 emoji 即可触发对应的娱乐插件指令。

本插件基于 aiocqhttp / NapCat `group_msg_reaction` 通知机制构建，支持从 `raw_message` 解析 reaction 事件。

[![Release](https://img.shields.io/github/v/release/DearCrazyLeaf/astrbot_plugin_react_menu?include_prereleases&color=blueviolet&label=最新版本)](https://github.com/DearCrazyLeaf/astrbot_plugin_react_menu/releases/latest)
[![License](https://img.shields.io/badge/许可证-GPL%203.0-orange)](https://www.gnu.org/licenses/gpl-3.0.txt)
[![Issues](https://img.shields.io/github/issues/DearCrazyLeaf/astrbot_plugin_react_menu?color=darkgreen&label=反馈)](https://github.com/DearCrazyLeaf/astrbot_plugin_react_menu/issues)
[![Pull Requests](https://img.shields.io/github/issues-pr/DearCrazyLeaf/astrbot_plugin_react_menu?color=blue&label=请求)](https://github.com/DearCrazyLeaf/astrbot_plugin_react_menu/pulls)
[![GitHub Stars](https://img.shields.io/github/stars/DearCrazyLeaf/astrbot_plugin_react_menu?color=yellow&label=标星)](https://github.com/DearCrazyLeaf/astrbot_plugin_react_menu/stargazers)

---

## ✅ 功能

- 监听群聊中的 `菜单` 关键词
- 发送带 emoji 的互动菜单文本
- 解析 `group_msg_reaction` 事件的 `raw_message`
- 校验 `message_id` 仅处理本插件发送的菜单消息
- 支持点击防抖与菜单过期
- 以点击者身份触发目标插件指令
- 失败时 fallback 发送等价指令文本

---

## 📦 安装

1. 将本插件目录放入 AstrBot 的 `data/plugins/` 下：
   ```bash
   AstrBot/data/plugins/astrbot_plugin_react_menu
   ```
2. 启动或重启 AstrBot。
3. 在插件管理界面启用 `表情回应菜单`。

---

## ⚙️ 配置

本插件通过 `config.json` 配置核心行为。推荐通过 AstrBot WebUI 插件配置界面修改，或直接编辑 `config.json`。

### 配置项说明

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `menu_keywords` | array | `["菜单"]` | 菜单触发关键词列表，支持多个关键词 |
| `menu_title` | string | `"🎮 娱乐菜单"` | 菜单标题文本 |
| `menu_timeout_seconds` | int | `600` | 菜单有效期，单位秒 |
| `debounce_seconds` | int | `3` | 同一用户对同一 emoji 的冷却时间，单位秒 |
| `emoji_mapping` | object | `见示例` | emoji ID 到指令的映射表 |

### 示例配置

```json
{
  "menu_keywords": ["菜单"],
  "menu_title": "🎮 娱乐菜单",
  "menu_timeout_seconds": 600,
  "debounce_seconds": 3,
  "emoji_mapping": {
    "128": { "command": "每日老婆", "desc": "🐷 每日老婆" },
    "129": { "command": "每日小猪", "desc": "🐗 每日小猪" },
    "151": { "command": "随机VTB", "desc": "🎲 随机VTB" },
    "144": { "command": "CS开箱", "desc": "🎁 CS开箱" }
  }
}
```

---

## 🧪 使用

1. 群内发送 `菜单`
2. 插件会发送菜单文本并自动贴上 emoji
3. 点击菜单中的 emoji 即可触发对应指令

### 推荐流程

- 推荐在菜单中使用常用娱乐指令，如 `每日老婆`、`每日小猪`、`随机VTB`、`CS开箱`
- 请确保目标插件已经启用，并且对应命令在当前 AstrBot 中可用

---

## 🎯 常见验证

- 发送 `菜单` 后能否得到菜单文本
- 菜单是否成功贴上 emoji
- 点击 emoji 是否触发对应功能
- 取消点击后是否不会重复触发
- 菜单过期后点击是否不再触发

---

## ⚠️ 注意事项

- 本插件仅支持群聊场景
- `group_msg_reaction` 事件解析依赖 `raw_message`
- `event.message_str` 对 reaction 事件通常为空，因此必须从 `raw_message` 解析
- `operation=1` 表示添加表情，`operation=2` 表示取消表情，默认忽略取消事件
- `target_id` 通常为点击者，请根据实际 raw_message 输出确认字段含义

---

## 📄 许可证

本项目采用 **GNU GPL v3.0** 许可证。

---

> Made for AstrBot ❤️