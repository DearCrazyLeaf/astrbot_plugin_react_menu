# 版本说明

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