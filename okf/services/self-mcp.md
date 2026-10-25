---
type: Service
title: self-mcp（自分のことを答える MCP サーバー）
description: xiaozhi-server のサーバー側 MCP から streamable-http で呼ばれ、okf と brain の記録を読んで、仕組み・調子・記憶・判断の理由・最近の変化を返す。
tags: [service, mcp, self-knowledge]
status: stable
generated: { by: claude-code/opus-5.5, at: 2026-09-29T00:00:00Z }
sources:
  - id: code
    resource: ../../mcp/self/server.py
    title: mcp/self/server.py
  - id: decision
    resource: /decisions/013-self-knowledge-mcp.md
    title: 決定 013
  - id: run-1025
    resource: process:claude-code-session-2026-10-25
    title: 2026-10-25 xiaozhi-server 0.9.8 への更新時の疑似端末試験
---

# 動作

- `http://self-mcp:8020/mcp`（streamable-http、stateless）。ポートはホストに公開しない。Host ヘッダは `self-mcp:8020` / `localhost:8020` / `127.0.0.1:8020` だけ受け付ける（DNS リバインディング対策）。[^code]
- xiaozhi-server の `data/.mcp_server_settings.json`（`config/xiaozhi/mcp_server_settings.template.json` から `render_config.py` が書く）で `stackchan-self` として登録。[^decision]
- マウント（すべて読み取り専用）: `./okf` → `/okf`、`./data/brain` → `/data/brain`、`./data/llm-proxy/gate` → `/data/gate`。brain の `/sessions` を HTTP で読む。

| ツール | 使う場面 | 材料 |
|---|---|---|
| `about_me(topic)` | 仕組みを聞かれた | [スタックチャン自身の説明](/design/self-profile.md) の話題に合う節（最大 3 つ）＋ bigram で選んだ詳しい概念 1 つ（deprecated は除く、draft は「未確認を含む」と添える） |
| `my_status()` | 調子を聞かれた | 使っている LLM、接続中のセッション、今日のセッション数・自発発話・ゲートの通過/聞き流し・Jev の回答数 |
| `what_i_remember()` | 覚えていることを聞かれた | `data/brain/memory/*.json` |
| `why(kind)` | 判断の理由を聞かれた | `spoke` / `quiet`: 直近の判定（状況の分類を平易に、確率と閾値、顔の数）。`ignored`: 直近 3 件のゲートの判断（**発話の本文は返さない**） |
| `recent_changes(days)` | 最近の変化を聞かれた | `okf/log.md`（git はイメージに無いので使わない） |

# 確認

- 2026-09-29、疑似端末で `evals/self_run.py` 5/5。最初の文まで 3.3〜4.3 秒（1 回 10.7 秒）。
- 試験中に見つかったこと: 名前で呼んだ「今日の調子はどう？」が宛先ゲートでロボット宛て 0.79 として止まった → 名前が入っていれば閾値を 0.5 に下げる（→ [宛先ゲート](/design/addressee-gate.md)）。
- **2026-10-25、xiaozhi-server 0.9.8 では使えない。** 0.9.8 の MCP クライアントがツール登録で失敗する（`'Tool' object has no attribute 'inputSchema'`、上流のバグ。→ [xiaozhi-esp32-server](/services/xiaozhi-esp32-server.md) の「0.9.8 の既知の問題」）。self-mcp 自体は接続・ツール一覧の応答まで正常。[^run-1025]
- self-mcp は 0.9.6 のイメージ（mcp 1.22.0）で動かしている。0.9.8 のイメージ（mcp 2.3.0）では `mcp.server.fastmcp` が無く（`MCPServer` に改名）起動しない。0.9.8 に揃えるには server.py を mcp 2.x に移行する必要がある（未着手）。[^run-1025]

[^code]: mcp/self/server.py
[^decision]: 決定 013
[^run-1025]: 2026-10-25 xiaozhi-server 0.9.8 への更新時の疑似端末試験
