---
type: Decision
title: "003: LAN 内で閉じる"
description: サーバー群はインターネットに露出させず、TLS・認証もスコープ外とする。
tags: [decision, adr]
status: stable
generated: { by: claude-code/opus-5.5, at: 2026-09-26T08:00:00Z }
sources:
  - id: kickoff
    resource: ../../docs/KICKOFF.md
    title: stackchan-brain キックオフ指示書（human:shingo 作成）
    author: human:shingo
  - id: readme
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/README.md
    title: xiaozhi-esp32-server README（警告節）
---

# 決定
xiaozhi-server・brain・mcp-bridge は LAN 内だけで使う。インターネット露出、TLS、認証はスコープ外。

# 理由
- xiaozhi-esp32-server の README が「機能未完成、ネットワークセキュリティ評価未了、本番で使うな」と明記している。[^readme]
- コストを最小にする。

# 帰結
- `server.auth.enabled: false` のまま運用する。ポート 8000 / 8003 をルーターで転送しない。

[^readme]: xiaozhi-esp32-server README
