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
- 支持接入 [CS2开箱模拟](https://github.com/luooka/astrbot_plugin_openweaponscase) 插件，由本插件接管开箱命令并生成互动菜单

**开箱模拟联动效果预览：**

<img width="400" height="960" alt="gif_preview" src="https://github.com/user-attachments/assets/0ca0629b-1cf4-4fd4-bf2d-7d40649e370f" />

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

### CS2 开箱 API 菜单

在全局菜单或 UMO 菜单中新增 “CS2开箱模拟 API 菜单” 模板即可，默认关键词为 `开箱` ，打开后显示群成员共同使用的主菜单，按钮依次为“快速开箱”“查看库存”“开箱帮助”“武器箱一览”“清空库存记录（个人）”“更新武器箱数据（管理员）”和“清理本地图片缓存（管理员）”；主菜单选择后不会撤回；进入快速开箱后，后续选择只允许发起该流程的用户操作；使用前需安装并启用 [CS2开箱模拟](https://github.com/luooka/astrbot_plugin_openweaponscase)，并在其配置中开启 `enable_react_menu_api`（启用互动菜单 API）

CS2 卡片按页面分成四组。各组的“菜单选项”和普通菜单用法一致，每行填写 `文案,指令`，可选第三列 `表情ID`；显示顺序与列表一致。在 WebUI 中可以逐项增删，也可以通过批量导入按所需顺序填写。

| 设置分组 | 可以配置的内容 | 选项示例 |
| --- | --- | --- |
| 主菜单 | 标题、快速开箱入口、原生指令或其他菜单入口 | `快速开箱,api:home:self_open`、`查看库存,库存` |
| 种类选择菜单 | 标题、种类选项和数量格式、取消提示 | `武器箱,api:category:case`、`取消选择,api:nav:cancel` |
| 箱子列表菜单 | 标题、页码、当页物品的位置、翻页和返回选项 | `{item},api:items`、`下一页,api:nav:next`、`返回种类选择,api:nav:back` |
| 数量选择菜单 | 标题、开箱数量及其文案、返回和取消选项 | `开 3 个,api:quantity:3`、`返回箱子选择,api:nav:back` |

- 默认只提供武器箱、纪念包和收藏品。胶囊、涂鸦、布章不出现在默认选项里；开箱插件的 API 接口保留，后续有实际支持时再添加对应选项。
- `api:` 选项只在开箱插件返回该动作时显示。例如，第一页不会显示“上一页”，超过插件单次上限的数量也不会显示。`{item},api:items` 会在该行位置展开当页的物品，不需要逐个填写名称；展开项的表情自动分配。
- 新增普通功能时，直接在对应分组加一行 `我的功能,指令`，无需改代码。没有 `api:` 前缀的指令与普通菜单一致：若匹配同一会话范围内的菜单关键词，则打开该菜单；否则以点击者身份执行原生指令。开箱帮助、库存、武器箱列表和管理员操作仍由开箱插件处理。
- 选择开箱数量后，数量菜单不会撤回。旧卡片的自定义标题、文案和数量会在插件加载时迁移到对应分组，无需重新添加卡片。

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
- `🍚 显示内容,触发指令`：项目开头可填写 NapCat 支持的 Unicode 表情；该表情会保留在菜单文本中，并转换为对应的 OneBot `emoji_id`（例如 `🍚` -> `127834`）
- 只有字符串时，默认 `label` 和 `command` 相同；例如 `"每日老婆"` 将显示为“每日老婆”，触发命令同样为 `每日老婆`
- 旧版保存的 `{ "label": ..., "command": ..., "face_id": ... }` 对象会在插件首次加载时自动转换为上述字符串格式
- 如果未指定 `face_id`，插件会从 `face_pool` 中随机分配一个可用 ID
- `face_pool` 也支持直接填写 NapCat 支持的 Unicode 表情，插件会自动转换为对应的数字 `emoji_id`
- 显式指定的 Unicode 表情优先按菜单项目顺序贴出；没有显式表情的项目才从 `face_pool` 和内置备用池随机补充
- Unicode 表情支持集按 NapCat `face_config.json` 的 `emoji` 表维护；不在支持集内的字符会保留为普通菜单文本，并继续使用随机备用表情
- 分配时会自动过滤已弃用/重复的 QQ 表情 ID，并按表情本身去重，保证一个菜单内贴出的表情互不相同
- `menu_max_reactions` 控制每张菜单自动贴表情的数量；如果菜单项更多，超出部分仍可通过序号或文本内容触发
- `menu_header_image_url` 支持配置菜单头图链接；当配置后菜单将显示头图
- `menu_divider_char` 与 `menu_divider_length` 用于控制菜单顶部/底部分割线样式
- 菜单项目只需填写不带唤醒词的指令本体，插件会按目标 UMO 的 AstrBot 配置自动添加唤醒词；唤醒词列表为空时使用虚拟 @ 唤醒
- 菜单项可以打开当前会话的其他菜单：例如目标菜单的触发词为 `工具`，项目填写 `更多功能,工具` 即可；文字选择和表情点击均支持，目标菜单仍遵守菜单冷却设置

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

## 🔧 API 菜单接入规范

在现有插件中增加 API 菜单时，目标插件提供页面和选项数据，表情互动菜单负责渲染、翻页、会话以及按操作者身份触发原生指令；CS2 开箱是仓库中的接入示例

1. 在目标插件公开 `get_interactive_menu_api_info()`、`get_interactive_menu_page(state=None, display_options=None)` 和 `handle_interactive_menu_action(state, action_id, display_options=None)` ；元信息包含 `provider_id`、`api_version`、`enabled` 和 `supported_platforms` ；页面包含 `title`、`state` 和 `items`，每项提供 `label` 和 `action_id`
2. 在 `api_menus/providers/<provider_id>/` 添加 `ProviderSpec` 和 `schema.json` ；适配器声明目标插件 ID、兼容 API 版本和平台，schema 声明触发词和可配置字段，将适配器加入 `api_menus/registry.py`
3. 在插件根目录运行 `python tools/sync_menu_schema.py`，将模板同步到全局菜单与 UMO 菜单，提交前可用 `python tools/sync_menu_schema.py --check` 检查同步状态

完整的返回格式、共享页与个人页约定、配置字段和接入示例见 [API 菜单开发者指南](docs/api-menu-provider-design.md)

## ❤️ 贡献者 | Contributors

<a href="https://github.com/DearCrazyLeaf/astrbot_plugin_react_menu/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=DearCrazyLeaf/astrbot_plugin_react_menu&max=300&columns=15" alt="Contributors" />
</a>


## 📜 许可证 | License

[![GPL-3.0 License](https://img.shields.io/badge/License-GPL--3.0-orange?style=for-the-badge)](https://www.gnu.org/licenses/gpl-3.0.txt)

---

> Made for AstrBot ❤️
