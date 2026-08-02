# 版本说明

## v1.0.1

### 变更摘要

- 新增头图配置项 `menu_header_image_url`，可配置图床
- 新增聊天气泡最大表情数量配置项 `menu_max_reactions`，默认值为 20
- 新增菜单分割线配置项 `menu_divider_char` 和 `menu_divider_length`

<details>
<summary>历史版本（点击展开）</summary>

## v1.0.0

### 变更摘要

- `menu_items` 字符串支持 `label/command`、`label,command`、`label command` 分隔形式。
- 增强回环保护与防抖逻辑以提升稳定性。
- 初始版本：表情回应菜单插件
- 支持 `菜单` 关键词触发
- 支持 `group_msg_reaction` 事件解析
- 支持 emoji 映射到目标指令
- 支持点击者身份注入触发
- 支持菜单过期与防抖机制