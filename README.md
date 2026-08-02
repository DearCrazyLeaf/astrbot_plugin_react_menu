# Astrbot 表情回应菜单

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![AstrBot](https://img.shields.io/badge/AstrBot-v4.12%2B-brightgreen)
![License](https://img.shields.io/badge/License-GPL--3.0-orange)

![views](https://count.getloli.com/get/@astrbotchuanhuatong?theme=booru-jaypee)

---

## ✅ 简介

`astrbot_plugin_react_menu` 是一款 AstrBot 插件：群内发送 `菜单` 关键词后，插件会生成一条带 emoji 的互动菜单，群员点击 emoji 即可触发对应的娱乐插件指令。

> [!NOTE]
> 本插件面向非 QQ 官方机器人，仿造官方机器人聊天按钮触发方式实现，通过 emoji reaction 交互实现按钮式命令调用。

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
| `menu_repeat_block` | bool | `true` | 是否启用菜单冷却阻断 |
| `menu_repeat_reply` | string | `"当前菜单已经生效，正在冷却中，直接点表情或发序号/内容即可触发~"` | 菜单冷却时的提示文本 |
| `face_pool` | array | `[
"128",
"129",
"151",
"144"
]` | 未指定 face_id 时的备用随机 face_id 池 |
| `menu_items` | array | `见示例` | 按顺序定义菜单项，支持字符串或对象形式 |

### 示例配置

```json
{
  "menu_keywords": ["菜单"],
  "menu_title": "🎮 娱乐菜单",
  "menu_timeout_seconds": 600,
  "debounce_seconds": 3,
  "menu_repeat_block": true,
  "menu_repeat_reply": "当前菜单已经生效，正在冷却中，直接点表情或发序号/内容即可触发~",
  "face_pool": ["128", "129", "151", "144"],
  "menu_items": [
    "每日老婆,抽老婆",
    "今日小猪",
    "随机VTB,dd"
  ]
}
```

### `menu_items` 说明

- `menu_items` 支持两种写法：
  - 字符串形式：`"显示内容"` 或 `"显示内容 触发指令"`
  - 对象形式：`{ "label": "显示内容", "command": "触发指令", "face_id": "可选表情ID" }`
- 只有字符串时，默认 `label` 和 `command` 相同；例如 `"每日老婆"` 将显示为“每日老婆”，触发命令同样为 `每日老婆`。
- 使用 `"显示内容 触发指令"` 时，前半部分作为菜单文本，后半部分作为实际命令；例如 `"每日小猪 今日小猪"` 会显示“每日小猪”，触发 `/今日小猪`。
- 如果未指定 `face_id`，插件会从 `face_pool` 中随机分配一个可用 ID。
- 文本命令会自动补 `/` 前缀，因此 `每日老婆` 与 `/每日老婆` 效果一致。
---
## 版本说明

- 版本：**v1.0.0**（首个稳定发布）。

### 变更摘要

- 只支持 `menu_items` 配置格式；请确保 `config.json` 使用最新格式。
- 增强回环保护与防抖逻辑以提升稳定性。

---

## 🧪 使用

1. 群内发送 `菜单`
2. 插件会发送菜单文本并自动贴上 emoji
3. 点击菜单中的 emoji 即可触发对应指令

### 推荐流程

- 推荐在菜单中使用常用娱乐指令，如 `每日老婆`、`每日小猪`、`随机VTB`
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