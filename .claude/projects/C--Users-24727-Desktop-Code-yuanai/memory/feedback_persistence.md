---
name: feedback-persistence
description: 修改消息数据结构时必须同步更新 encodeMsg/loadMessages 的保存和恢复逻辑
metadata:
  type: feedback
---

每次给消息（ChatMessage）添加新字段时，必须同步检查三个环节：

1. **encodeMsg** (`frontend/src/components/chat/helpers.tsx`) — 保存时把字段序列化进 META 头
2. **handleSelectSession** (`frontend/src/components/ChatPage.tsx`) — 加载时从 META 头还原字段
3. **后端 save_messages** (`api/v1/chat/router.py`) — 确认字段能正确持久化

**Why:** 两次出现同样的 bug：图片和思考内容都因为只改了显示逻辑、没改持久化逻辑，导致切换页面后数据丢失。

**How to apply:** 改 ChatMessage 类型或消息相关代码时，自问：这个数据切走再回来还在吗？如果不在，补 encodeMsg + handleSelectSession。
