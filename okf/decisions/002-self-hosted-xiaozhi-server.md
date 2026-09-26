---
type: Decision
title: "002: 自前の xiaozhi-esp32-server を使う"
description: XiaoZhi クラウド＋MCP 接続点ではなく、LAN 内に自前サーバーを立てる。
tags: [decision, adr]
status: stable
generated: { by: claude-code/opus-5.5, at: 2026-09-26T08:00:00Z }
sources:
  - id: kickoff
    resource: ../../docs/KICKOFF.md
    title: stackchan-brain キックオフ指示書（human:shingo 作成）
    author: human:shingo
  - id: srv-http
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/main/xiaozhi-server/core/http_server.py
    title: xiaozhi-esp32-server core/http_server.py
---

# 決定
XiaoZhi クラウド（`api.tenclass.net`）＋ MCP 接続点ではなく、[xiaozhi-esp32-server](/services/xiaozhi-esp32-server.md) を自前で動かす。

# 理由
- 自律発話にはサーバー側の会話ループへの介入が必要。クラウドでは MCP ツールを足すことしかできない。
- LLM を Anthropic に差し替えられる。

# 補足（2026-09-26 確認）
- 自前サーバーにも「外部から発話を押し込む API」は無い。介入の具体的な経路は [決定 007](/decisions/007-proactive-speech-path.md) で決める。
