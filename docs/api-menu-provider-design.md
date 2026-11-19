# API 菜单开发者指南

表情互动菜单的 API 接入由两部分组成，不能只添加其中一部分

1. 目标插件提供稳定的 API 方法，返回页面、动作和原生指令
2. 表情互动菜单插件添加对应的 Provider 适配器和 API 菜单模板，负责发现目标插件、校验返回值、管理菜单会话、渲染表情和序号、派发指令

目标插件不需要依赖互动菜单插件的 Python 模块，也不需要新增 HTTP 服务。两个插件通过 AstrBot 已加载的插件实例互相发现和调用。CS2 开箱 API v1 是当前仓库的接入示例。

## 目录结构

~~~text
astrbot_plugin_react_menu/
├── api_menus/
│   ├── contract.py                      # ProviderSpec 和保留字段定义
│   ├── registry.py                      # 已注册的 Provider
│   ├── runtime.py                       # 依赖发现、页面校验、会话和动作处理
│   └── providers/
│       └── <provider_id>/
│           ├── __init__.py              # ProviderSpec 实例和适配器逻辑
│           └── schema.json              # API 菜单卡片模板
├── docs/
│   └── api-menu-provider-design.md      # 本规范
├── tools/
│   ├── sync_menu_schema.py              # 生成并检查 AstrBot 根 Schema
│   └── validate_api_menus.py            # 校验 Provider、模板和注册关系
└── _conf_schema.json                    # 提交给 AstrBot 加载的生成结果
~~~

main.py 处理普通菜单和 AstrBot 事件，api_menus/runtime.py 调用目标插件 API。目标插件只负责业务页面和动作解释，互动菜单插件负责消息、表情、序号、有效期、作用范围和操作者身份。

## 1. 接口身份和命名

每个 API 接入必须拥有一个稳定且唯一的 provider_id。它是菜单插件内部的 API 身份，不等同于插件版本号、显示名称或目录名称。

| 字段 | 要求 |
| --- | --- |
| provider_id | 只能使用小写字母、数字、下划线和连字符，且必须以小写字母或数字开头，例如 cs2_openweaponscase |
| plugin_id | 必须使用 AstrBot 运行时实际返回的插件标识，通常是 author/name 形式，不能填写显示名称 |
| api_version | 正整数，表示 API 返回结构和行为的兼容版本，与目标插件版本号独立 |
| platforms | Provider 适配器声明支持的平台标识，例如 aiocqhttp，应使用小写形式 |
| supported_platforms | 目标插件 API 元信息返回的平台列表，必须覆盖实际会话平台 |

命名约束如下

- provider_id 在 api_menus/registry.py 中必须唯一，大小写不同也视为重复
- schema.json 中的 items.provider_id.default 必须与 Provider 的 provider_id 完全一致
- Provider 注册表键、Provider 的 provider_id 和模板默认值必须一致
- 新 API 不得复用已有 provider_id，建议使用目标插件和功能组成的稳定名称
- 修改返回结构或动作语义时，应提升 api_version，不要用目标插件版本号代替 API 版本

## 2. 目标插件 API

### 2.1 公开方法

以下方法可以实现为同步函数，也可以实现为 async 异步函数，互动菜单插件会自动处理两种返回形式

| 方法 | 参数 | 返回值 |
| --- | --- | --- |
| get_interactive_menu_api_info() | 无 | API 元信息字典 |
| get_interactive_menu_page(state=None, display_options=None) | 页面状态和菜单配置 | page 或 error |
| handle_interactive_menu_action(state, action_id, display_options=None) | 页面状态、动作 ID 和菜单配置 | page、command、cancel 或 error |

目标插件应在插件实例上直接公开这些方法，不要依赖互动菜单插件的内部类或导入路径。

### 2.2 API 元信息

get_interactive_menu_api_info() 应返回以下结构

~~~json
{
  "provider_id": "example_plugin",
  "api_version": 1,
  "enabled": true,
  "supported_platforms": ["aiocqhttp"]
}
~~~

字段说明

- provider_id 必须与互动菜单侧 ProviderSpec 完全一致
- api_version 必须是正整数
- enabled 为 false 时，互动菜单不会继续渲染该 API 菜单
- supported_platforms 必须是平台标识字符串列表
- 目标插件应在每次调用时根据当前配置返回 enabled，不要在插件加载时永久缓存开关状态

### 2.3 页面返回值

页面必须返回以下结构

~~~json
{
  "kind": "page",
  "page": {
    "title": "示例菜单",
    "scope": "shared",
    "state": {"step": "start"},
    "items": [
      {"label": "查看记录", "action_id": "history"}
    ]
  }
}
~~~

字段约束

| 字段 | 要求 |
| --- | --- |
| kind | 必须是 page |
| page.title | 页面标题字符串，可以为空，由菜单侧使用卡片标题或 Provider 默认标题兜底 |
| page.scope | shared 表示当前作用范围内共同使用，user 表示只允许发起者使用，省略时按 user 处理 |
| page.state | 由目标插件定义的可序列化对象，下一次请求会原样传回，必须由目标插件自行校验 |
| page.items | 非空列表 |
| items[].label | 非空显示文案 |
| items[].action_id | 非空字符串，同一页面内必须唯一，不能把显示文案作为唯一标识的唯一依据 |
| page.page_info | 可选对象，推荐包含正整数 current 和 total，用于显示分页标题 |

菜单侧只依赖 label 和 action_id，其他项目字段不会自动成为业务协议。页面不能返回空选项列表，否则会被视为无效页面。

state 应保持精简，不要放入密码、Token 或不必要的用户隐私。动作 ID 和状态都属于不可信输入，目标插件必须在动作处理时重新验证当前状态、动作归属和业务权限。

### 2.4 动作返回值

#### 返回下一页

~~~json
{
  "kind": "page",
  "page": {
    "title": "下一步",
    "scope": "user",
    "state": {"step": "next"},
    "items": [
      {"label": "确认", "action_id": "confirm"}
    ]
  }
}
~~~

#### 派发原生指令

~~~json
{
  "kind": "command",
  "command": "查询记录",
  "keep_menu": true
}
~~~

command 会通过 AstrBot 的原生指令派发流程执行，执行身份是实际点击或回复选择的用户。目标插件仍必须在原生指令中重新检查权限、额度和业务状态。

- keep_menu 为 true 时保留当前菜单，适合可重复执行的操作
- keep_menu 省略或为 false 时结束当前菜单流程
- 可能产生副作用的操作不应无理由设置 keep_menu=true

#### 取消和错误

~~~json
{
  "kind": "cancel",
  "message": "已取消当前操作"
}
~~~

~~~json
{
  "kind": "error",
  "message": "当前操作已失效，请重新打开菜单"
}
~~~

message 会直接显示给用户，不应包含堆栈、Token、内部路径或其他敏感信息。目标插件可以返回业务错误，不应依赖抛出异常来完成正常的用户提示。

### 2.5 display_options 约定

display_options 来自用户配置的 API 菜单卡片。它不是权限参数，也不是可信业务输入

- 目标插件必须为每个选项提供默认值和类型容错
- 目标插件不得因为缺少某个展示字段而使原生功能失效
- 互动菜单侧的页面布局配置可以由 Provider 的 layout_for_card() 消化
- 只有 options_for_card() 返回的字段才会传给目标插件 API
- 目标插件必须继续自行校验数量、权限、每日额度、资源是否存在等业务规则

## 3. 互动菜单侧 Provider 适配器

### 3.1 最小 Provider

在 api_menus/providers/<provider_id>/__init__.py 中创建 ProviderSpec 实例

~~~python
from pathlib import Path

from ...contract import ProviderSpec


SPEC = ProviderSpec(
    provider_id="example_plugin",
    plugin_id="author/target_plugin",
    display_name="示例插件",
    api_versions=(1,),
    platforms=("aiocqhttp",),
    schema_path=Path(__file__).with_name("schema.json"),
    unconfigured_keywords=("示例",),
)
~~~

不需要自定义页面布局时，直接使用 ProviderSpec 即可。需要处理旧配置、页面分组、共享页转个人页或并发限制时，继承 ProviderSpec 并实现相应钩子。

### 3.2 ProviderSpec 钩子

| 方法 | 作用 | 默认行为 |
| --- | --- | --- |
| migrate_card(card) | 将旧版本卡片迁移到当前结构 | 不迁移 |
| layout_for_card(card, normalize_items) | 读取 Provider 专用布局配置 | 返回空布局 |
| options_for_card(card, layout) | 生成传给目标插件的 display_options | 传递模板中除保留字段外的配置 |
| present_page(page, title, items, layout) | 过滤、排序、重命名 API 动作或添加普通指令 | 原样返回 |
| page_scope(page) | 决定当前页面是 shared 还是 user | 使用页面字段，省略时为 user |
| starts_user_flow(state, action_id) | 判断共享页动作是否开启个人流程 | 不切换 |
| max_concurrent_user_flows(layout) | 返回当前作用范围内个人流程的数量上限 | 不限制 |
| mentions_owner(page) | 决定是否在页面开头 @ 发起者 | 不 @ |

CS2 适配器使用这些钩子实现主菜单共享、快速开箱个人化、发起者提醒和群内并发限制。

present_page() 接收的 items 已由运行时转换为内部项目，API 动作通常带有 api_action_id。如果保留 API 动作，必须保留对应的 api_action_id；如果添加普通菜单指令，应使用 command 字段，不要伪造 API 动作 ID。

适配器可以根据当前 API 返回的动作筛选配置项，但不得显示目标插件当前页面没有返回的 API 动作。配置中的 api: 前缀是 CS2 适配器的引用写法，不是目标插件 API 的通用字段。

### 3.3 适配器注册

在 api_menus/registry.py 中导入并注册 SPEC

~~~python
from .providers.example_plugin import SPEC as EXAMPLE_SPEC

PROVIDERS = _build_registry((CS2_SPEC, EXAMPLE_SPEC))
~~~

注册表键、SPEC.provider_id 和模板中的 items.provider_id.default 必须完全一致。注册表会拒绝重复的 API 标识，校验脚本还会拒绝大小写不同但实际相同的标识。

## 4. API 菜单模板

### 4.1 最小 schema.json

模板是 AstrBot template_list 使用的单卡片定义，必须包含顶层 name、display_item 和 items

~~~json
{
  "name": "示例插件 API 菜单",
  "display_item": "name",
  "items": {
    "menu_id": {
      "type": "string",
      "default": "example_plugin",
      "invisible": true
    },
    "name": {
      "type": "string",
      "description": "菜单名称",
      "default": "示例插件 API 菜单"
    },
    "keywords": {
      "type": "list",
      "description": "触发关键词",
      "default": ["示例"],
      "items": {"type": "string"}
    },
    "provider_id": {
      "type": "string",
      "default": "example_plugin",
      "invisible": true
    }
  }
}
~~~

模板规则

- items.menu_id 和 items.provider_id 必须是隐藏字符串字段，默认值与 provider_id 一致
- items.name 必须是字符串字段，display_item 应引用它
- items.keywords 必须是字符串列表，用于从关键词直接打开 API 菜单
- Provider 专用配置使用其他字段名，例如 home_menu、page_size、display_options
- menu_id、provider_id、name、keywords、title、items、umo 是保留字段，不要用作 Provider 专用配置名
- 源模板不得声明 items.umo，UMO 字段由同步脚本自动添加
- 不要在 schema.json 中写入运行时生成的页面项目，页面项目来自目标插件 API

### 4.2 菜单项目字符串

如果模板需要让用户配置菜单项目，统一使用以下格式

~~~text
显示文案,指令
显示文案,指令,表情ID
🍚 显示文案,指令
~~~

“可选表情 ID”只是说明字段可省略，不是要求在配置中输入方括号。实际格式只有“文案,指令”或“文案,指令,表情ID”。第三段可以省略；文案开头的第一个支持的 Unicode Emoji 会自动转换为按钮表情并保留在显示文案中。没有显式表情 ID 或开头 Emoji 时，菜单插件才从全局表情池补充表情。

### 4.3 分组页面模板

需要让用户自定义不同页面时，可以在 items 下增加 object 分组，例如 home_menu、list_menu 和 quantity_menu。Provider 在 layout_for_card() 中读取分组，在 options_for_card() 中只提取目标插件真正需要的字段，在 present_page() 中把 API 动作映射为用户配置的显示顺序。

页面布局字段属于互动菜单侧，目标插件 API 不需要为了适配 WebUI 结构而理解这些字段。目标插件只接收稳定的业务展示选项。

## 5. 注册、同步和校验流程

1. 目标插件实现三组 API 方法，返回稳定的 provider_id、API 版本、平台和页面动作
2. 在互动菜单插件创建 Provider 目录、__init__.py 和 schema.json
3. 在 api_menus/registry.py 注册 Provider
4. 运行 python tools/validate_api_menus.py，检查命名、注册关系、目标插件标识、Schema 必填字段和孤立模板
5. 运行 python tools/sync_menu_schema.py，生成根目录 _conf_schema.json
6. 运行 python tools/validate_api_menus.py --check-sync 和 python tools/sync_menu_schema.py --check
7. 运行测试，覆盖直接关键词、普通菜单入口、表情、序号、过期、平台不匹配、依赖缺失、版本不匹配、动作权限和原生指令身份

校验脚本只能验证本仓库内的 Provider 和模板，不能代替实际加载目标插件，也不能证明外部第三方插件没有使用相同的 provider_id。发布前仍需在 AstrBot 环境中验证目标插件实例发现和实际消息链路。

## 6. sync_menu_schema.py 的作用

tools/sync_menu_schema.py 是开发期的 Schema 生成和一致性检查工具，不是 AstrBot 运行时插件接口，也不会被 main.py 导入

它执行以下操作

- 从 api_menus.registry.PROVIDERS 读取已注册 Provider
- 读取每个 Provider 目录中的 schema.json
- 将 Provider 模板写入根 Schema 的全局菜单和 UMO 菜单模板集合
- 保留非 API 的手工菜单模板
- 为 UMO 模板自动补充现有的 umo 字段
- 检查模板中的 provider_id 默认值是否与注册表一致
- 拒绝 Provider 源模板自行声明 umo
- 使用 --check 时只比较结果，不写入文件

AstrBot 实际加载的是提交到仓库中的 _conf_schema.json，而不是运行 sync_menu_schema.py。发布或提交 PR 时必须同时提交同步后的 _conf_schema.json，不能要求用户在安装插件后运行该脚本。

这种设计不会给生产运行时增加脚本依赖、网络请求或额外启动步骤。官方审核时应重点确认以下内容

- metadata.yaml、main.py 和 _conf_schema.json 可以直接被 AstrBot 加载
- 运行时不依赖 tools 目录
- Provider API 缺失、版本不匹配、平台不支持和插件未启用时有明确降级行为
- Schema 已同步且 python tools/sync_menu_schema.py --check 通过
- 开发期脚本使用标准库，不修改 AstrBot 框架源码，不写入用户数据目录

## 7. 运行时和安全要求

- 目标插件必须在每次动作处理时重新验证 state 和 action_id
- 不得仅根据客户端传入的数量、名称或权限字段执行敏感操作
- 原生指令必须由目标插件再次执行权限、额度和业务状态校验
- shared 页面中的普通指令仍以实际点击者身份执行
- 需要个人操作的流程应返回 scope: user，或由 Provider 适配器将共享页动作转换为个人流程
- 旧页面、旧动作和已经变化的业务数据应返回 error，而不是执行过期操作
- 页面展示失败、目标插件关闭或依赖消失时，菜单侧会结束对应会话并提示重新打开

## 8. 最低验证清单

新增 Provider 后至少验证以下场景

- API 开关关闭时，目标插件原生指令仍正常工作
- 目标插件未加载时，菜单侧能提示依赖缺失
- 目标插件已加载但 API 未启用时，不生成 API 菜单
- API 版本不匹配和平台不支持时被拒绝
- 直接关键词和普通菜单入口都能找到同一张 API 卡片
- shared 页面能被作用范围内用户使用，user 页面只允许发起者操作
- 过期页面、旧消息、旧序号和旧表情不能触发动作
- API 返回的每个 action_id 都能进入正确状态转换
- 原生指令以实际操作者身份执行，并保留目标插件权限校验
- keep_menu=true 的动作不会意外结束菜单，默认动作会正确结束菜单
- python tools/validate_api_menus.py --check-sync 通过
- python tools/sync_menu_schema.py --check 通过

完整接入示例参见 [CS2 Provider](../api_menus/providers/cs2_openweaponscase/__init__.py) 和 [CS2 菜单模板](../api_menus/providers/cs2_openweaponscase/schema.json)。

