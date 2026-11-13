# Astrbot 表情互动菜单

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![AstrBot](https://img.shields.io/badge/AstrBot-v4.12%2B-brightgreen)
![License](https://img.shields.io/badge/License-GPL--3.0-orange)

![views](https://count.getloli.com/get/@astrbot_plugin_react_menu?theme=booru-jaypee)

---

## ✅ 简介 | Introduction

<table>
  <tr>
    <td width="190" align="center">
      <img width="170" alt="logo" src="logo.png" style="border-radius: 24px;" />
    </td>
    <td>
      <strong>AstrBot React Menu</strong><br />
       Emoji Reaction · Interactive Menu · Command Trigger<br />
      <sub>Turn emoji reactions into button-like commands in your AstrBot conversations.</sub>
    </td>
  </tr>
</table>

这是一个为 **AstrBot** 编写的插件：提供一个能**集中管理框架中所有指令**（`aiocqhttp`）的互动菜单，通过仿造官方机器人 `MarkDown` 按钮触发的形式，和可配置的指令列表，在发送关键词后生成一个贴有 `emoji` 表情的互动菜单，点击 `emoji` 即可触发配置的对应指令（模仿点击者来触发指令，支持大部分需要个人身份触发的情景）

> [!TIP]
> 基于 aiocqhttp / NapCat `group_msg_reaction` 通知机制构建，支持从 `raw_message` 解析 reaction 事件基于 aiocqhttp / NapCat `group_msg_reaction` 通知机制构建，支持从 `raw_message` 解析 reaction 事件

> [!NOTE]
> 本插件面向非 QQ 官方机器人，仿造官方机器人聊天按钮触发方式实现，通过 emoji reaction 交互实现按钮式命令调用

[![Release](https://img.shields.io/github/v/release/DearCrazyLeaf/astrbot_plugin_react_menu?include_prereleases&color=blueviolet&label=最新版本)](https://github.com/DearCrazyLeaf/astrbot_plugin_react_menu/releases/latest)
[![License](https://img.shields.io/badge/许可证-GPL%203.0-orange)](https://www.gnu.org/licenses/gpl-3.0.txt)
[![Issues](https://img.shields.io/github/issues/DearCrazyLeaf/astrbot_plugin_react_menu?color=darkgreen&label=反馈)](https://github.com/DearCrazyLeaf/astrbot_plugin_react_menu/issues)
[![Pull Requests](https://img.shields.io/github/issues-pr/DearCrazyLeaf/astrbot_plugin_react_menu?color=blue&label=请求)](https://github.com/DearCrazyLeaf/astrbot_plugin_react_menu/pulls)
[![QQ Group](https://img.shields.io/badge/点击加入QQ群-12B7F5?logo=tencentqq&logoColor=white&label=问题反馈和建议)](https://qm.qq.com/q/H3uUCEZKgg)
[![GitHub Stars](https://img.shields.io/github/stars/DearCrazyLeaf/astrbot_plugin_react_menu?color=yellow&label=标星)](https://github.com/DearCrazyLeaf/astrbot_plugin_react_menu/stargazers)

---

## ✅ 功能 | Features

<img width="600" alt="预览效果图" src="https://github.com/user-attachments/assets/06758a41-a431-46c1-95e1-525169fc1a2a" />

- 支持配置菜单内容，包括显示文本、触发指令和可选表情ID
- 支持通过多张菜单卡片配置不同的触发关键词和菜单项目
- 发送带 emoji 的互动菜单文本
- 自动分配互不相同的 QQ 表情，避免重复表情导致的菜单项无法点击触发
- 解析 `group_msg_reaction` 事件的 `raw_message`
- 校验 `message_id` 仅处理本插件发送的菜单消息
- 支持点击防抖与菜单过期
- 以点击者身份触发目标插件指令
- 失败时 fallback 发送等价指令文本

---

## 📦 安装 | Installation

1. 将本插件目录放入 AstrBot 的 `data/plugins/` 下：
   ```bash
   AstrBot/data/plugins/astrbot_plugin_react_menu
   ```
2. 启动或重启 AstrBot。
3. 在插件管理界面启用 `表情互动菜单`

---

## ⚙️ 配置 | Configuration

本插件通过 `config.json` 配置核心行为。推荐通过 AstrBot WebUI 插件配置界面修改，或直接编辑 `config.json`

### 配置项说明

> [!NOTE]
> WebUI 中按以下分组显示：全局菜单设置、交互与有效期、菜单外观、表情设置；后三组设置同时适用于全局与 UMO 菜单；旧版散列选项会在首次加载时自动迁移并保留原值

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `global_settings.menus` | template_list | 见示例 | 全局菜单卡片列表；未配置 UMO 卡片时作为所有会话的菜单 |
| `global_settings.umo_menus` | template_list | `[]` | UMO 菜单卡片列表；每张卡片直接填写 UMO 和菜单，非空时忽略全局菜单 |
| `interaction_settings.menu_timeout_seconds` | int | `60` | 菜单有效期，单位秒 |
| `interaction_settings.debounce_seconds` | int | `3` | 同一用户对同一 emoji 的冷却时间，单位秒 |
| `interaction_settings.menu_repeat_block` | bool | `true` | 是否启用菜单冷却阻断 |
| `interaction_settings.menu_repeat_reply` | string | `"当前菜单已经生效，正在冷却中，直接点表情或发序号/内容即可触发~"` | 菜单冷却时的提示文本 |
| `reaction_settings.face_pool` | array | `["5", "9", "10", "14", "18", "21", "23", "25", "27", "29", "32", "49", "53", "55", "59", "60", "63", "66", "74", "79", "89", "96", "99", "100", "105", "120", "123", "124", "129", "144", "147", "171", "175", "179", "182", "183", "201"]` | 未指定 face_id 时的备用随机 face_id 池。仅包含当前 QQ 有效且互不相同的表情 ID，已弃用/重复的 ID（如旧表库中的 128、151）会被自动过滤，避免贴出重复表情 |
| `reaction_settings.menu_max_reactions` | int | `20` | 自动贴表情的最大数量，超过部分仍可通过序号/文本触发 |
| `appearance_settings.menu_header_image_url` | string | `""` | 菜单头图 URL，支持可配置图床链接 |
| `appearance_settings.menu_divider_char` | string | `"─"` | 菜单分割线字符，用于美化菜单样式 |
| `appearance_settings.menu_divider_length` | int | `28` | 菜单分割线长度 |
| `appearance_settings.menu_footer_text` | string | `"👆 下方按顺序贴表情，第1个表情对应第1项，第2个表情对应第2项。也可直接回复序号或菜单内容触发。"` | 菜单最下方的说明文案；留空则隐藏 |
| `menu_keywords`、`menu_title`、`menu_items`、顶层 `menus` | 兼容字段 | 隐藏 | 用于迁移旧版菜单配置；新配置请使用全局菜单设置分区 |

### 示例配置

```json
{
  "global_settings": {
    "menus": [
      {
        "__template_key": "menu",
        "menu_id": "entertainment",
        "name": "娱乐菜单",
        "keywords": [
          "菜单",
          "娱乐"
        ],
        "title": "🎮 娱乐菜单",
        "items": [
          "每日老婆,抽老婆",
          "今日小猪",
          "随机VTB,dd"
        ]
      },
      {
        "__template_key": "menu",
        "menu_id": "tools",
        "name": "工具菜单",
        "keywords": [
          "工具"
        ],
        "title": "🧰 工具菜单",
        "items": [
          "查询帮助,帮助"
        ]
      }
    ],
    "umo_menus": [
      {
        "__template_key": "menu",
        "umo": "aiocqhttp:GroupMessage:123456",
        "menu_id": "group-tools",
        "name": "群专属工具菜单",
        "keywords": [
          "工具"
        ],
        "title": "🧰 工具菜单",
        "items": [
          "查询帮助,帮助"
        ]
      }
    ]
  },
  "interaction_settings": {
    "menu_timeout_seconds": 60,
    "debounce_seconds": 3,
    "menu_repeat_block": true,
    "menu_repeat_reply": "当前菜单已经生效，正在冷却中，直接点表情或发序号/内容即可触发~"
  },
  "appearance_settings": {
    "menu_header_image_url": "",
    "menu_divider_char": "─",
    "menu_divider_length": 28,
    "menu_footer_text": "点击下方对应表情，或回复序号/菜单名称触发查询"
  },
  "reaction_settings": {
    "menu_max_reactions": 20,
    "face_pool": [
      "5",
      "9",
      "10",
      "14",
      "18",
      "21",
      "23",
      "25",
      "27",
      "29",
      "32",
      "49",
      "53",
      "55",
      "59",
      "60",
      "63",
      "66",
      "74",
      "79",
      "89",
      "96",
      "99",
      "100",
      "105",
      "120",
      "123",
      "124",
      "129",
      "144",
      "147",
      "171",
      "175",
      "179",
      "182",
      "183",
      "201"
    ]
  },
  "menu_keywords": [],
  "menus": [],
  "menu_title": "",
  "menu_items": [],
  "_settings_grouped": true
}
```

### 菜单卡片说明

- 所有菜单放在“全局菜单设置”分区内，“全局菜单”和“UMO 菜单”是平级卡片列表，不存在会话卡片嵌套菜单卡片
- 每张卡片直接设置菜单名称、触发词、标题和项目；UMO 菜单卡片额外填写完整 `umo`，其值通过目标群内的 `/sid` 获取
- 为同一个 UMO 添加多个菜单时，添加多张 UMO 菜单卡片并填写相同的 UMO 即可
- `umo_menus` 为空时使用全局菜单；列表非空时忽略全局菜单，仅已登记 UMO 使用对应菜单，其他 UMO 不触发；上方示例启用了 UMO 模式，清空 `umo_menus` 即恢复全局模式
- 已登记 UMO 的卡片项目为空时不回退全局菜单；UMO 填写无效会记录警告并忽略卡片，列表仍按非空处理
- 同一菜单集合内的触发词应唯一；重复时第一张有效卡片优先。不同 UMO 可以使用相同触发词
- 旧版嵌套会话菜单会在加载时自动展开为 UMO 菜单卡片；保存迁移配置后，删除新卡片不会恢复旧卡片
- `items` 在 WebUI 中是简化字符串列表，每行填写一种菜单项目：
  - `显示内容`：显示内容和触发指令相同
  - `显示内容,触发指令`：前半部分作为菜单文本，后半部分作为实际命令
  - `显示内容,触发指令,face_id`：末尾可选指定表情 ID
- 只有字符串时，默认 `label` 和 `command` 相同；例如 `"每日老婆"` 将显示为“每日老婆”，触发命令同样为 `每日老婆`
- 旧版保存的 `{ "label": ..., "command": ..., "face_id": ... }` 对象会在插件首次加载时自动转换为上述字符串格式
- 如果未指定 `face_id`，插件会从 `face_pool` 中随机分配一个可用 ID
- 分配时会自动过滤已弃用/重复的 QQ 表情 ID，并按表情本身去重，保证一个菜单内贴出的表情互不相同
- `menu_max_reactions` 控制每张菜单自动贴表情的数量；如果菜单项更多，超出部分仍可通过序号或文本内容触发
- `menu_header_image_url` 支持配置菜单头图链接；当配置后菜单将显示头图
- `menu_divider_char` 与 `menu_divider_length` 用于控制菜单顶部/底部分割线样式
- 文本命令会自动补 `/` 前缀，因此 `每日老婆` 与 `/每日老婆` 效果一致
- 菜单项可以打开当前会话的其他菜单：例如目标菜单的触发词为 `工具`，项目填写 `更多功能,工具` 或 `更多功能,/工具` 即可；文字选择和表情点击均支持，目标菜单仍遵守菜单冷却设置

---

## 🧪 使用 | Usage

1. 群内发送某张菜单卡片配置的触发关键词，例如： `菜单`、`娱乐` 或 `工具`
2. 插件会发送菜单文本并自动贴上 `emoji`
3. 点击菜单中的 `emoji` 即可触发对应指令；也可发送序号或菜单项文本触发最近打开的菜单

---

## ⚠️ 注意事项 | Cautions

- 本插件仅支持群聊场景
- 未启用 UMO 分会话菜单时，全局菜单对所有会话可用；UMO 菜单列表非空时未登记的 UMO 不触发菜单
- 活动菜单状态按完整 UMO 隔离；同一 UMO 内可打开不同菜单，文字选择最近打开的菜单，reaction 始终绑定各自的菜单消息
- `group_msg_reaction` 事件解析依赖 `raw_message`
- `event.message_str` 对 reaction 事件通常为空，因此必须从 `raw_message` 解析
- `operation=1` 表示添加表情，`operation=2` 表示取消表情，默认忽略取消事件
- `target_id` 通常为点击者，请根据实际 `raw_message` 输出确认字段含义
- 贴表情时会自动过滤已弃用/重复的 QQ 表情 ID，并按表情本身去重，保证同一个菜单内的表情不重复，从而避免因重复表情导致的菜单项无法点击触发

---

## ❤️ 贡献者 | Contributors

<a href="https://github.com/DearCrazyLeaf/astrbot_plugin_react_menu/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=DearCrazyLeaf/astrbot_plugin_react_menu&max=300&columns=15" alt="Contributors" />
</a>


## 📜 许可证 | License

[![GPL-3.0 License](https://img.shields.io/badge/License-GPL--3.0-orange?style=for-the-badge)](https://www.gnu.org/licenses/gpl-3.0.txt)

---

> Made for AstrBot ❤️
