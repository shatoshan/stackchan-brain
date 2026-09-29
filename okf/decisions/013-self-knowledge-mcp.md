---
type: Decision
title: "013: 自分のことを答える self-mcp（サーバー側 MCP、読み取り専用）"
description: スタックチャンが自分の仕組み・調子・記憶・判断の理由・最近の変化を聞かれて答えられるよう、リポジトリの知識と記録を読む MCP サーバーを xiaozhi-server のサーバー側 MCP につなぐ。調べて後で折り返すエージェントは第2段階の候補。
tags: [decision, adr, mcp, self-knowledge]
status: stable
generated: { by: claude-code/opus-5.5, at: 2026-09-29T00:00:00Z }
sources:
  - id: approval
    resource: process:chat-2026-09-29
    title: 2026-09-29 のユーザー指示（「自身の構成を聞かれて答えられるようにしたい」、家族向け＋「詳しく」で開発者向け、第1段階から、MCP 方針で進める）
    author: human:shingo
  - id: mcp-manager
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/main/xiaozhi-server/core/providers/tools/server_mcp/mcp_manager.py
    title: server_mcp/mcp_manager.py（data/.mcp_server_settings.json を読む）
  - id: mcp-client
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/main/xiaozhi-server/core/providers/tools/server_mcp/mcp_client.py
    title: server_mcp/mcp_client.py（stdio / sse / streamable-http）
  - id: run-0929
    resource: process:claude-code-session-2026-09-29
    title: 2026-09-29 疑似端末での試験（evals/self_run.py 5/5）
---

# 背景

- 「きみはどうやって動いてるの」「さっきなんで返事しなかったの」に、スタックチャン自身が答えられるようにしたい。[^approval]
- 材料はリポジトリに揃っている: `okf/`（仕組み・決定・変更の記録）、`data/brain/`（判定・記憶・セッション）、`data/llm-proxy/gate/`（宛先ゲートの記録）、brain の操作 API（今の状態）。

# 決定

- **self-mcp**（`mcp/self/server.py`）を新設し、xiaozhi-server の**サーバー側 MCP クライアント**につなぐ。設定は `data/.mcp_server_settings.json` の `mcpServers`（`url` + `transport: streamable-http`）で、`render_config.py` がテンプレートから書く。本体は改変しない（原則1）。xiaozhi-server は接続ごとに MCP サーバーへつなぎ、ツールを LLM の関数一覧に足す。[^mcp-manager] [^mcp-client]
- ツールは**読み取り専用**の 5 つ: `about_me(topic)`、`my_status()`、`what_i_remember()`、`why(kind)`、`recent_changes(days)`。結果は 1500 字以内の資料で、LLM が言い換えて話す。
- 話し方: ふだんは子どもにも分かる言葉で一言か二言、「詳しく」と頼まれた時だけ仕組みの名前や数字まで（`prompt` に追記）。[^approval] `about_me` は家族向けの自己説明（[スタックチャン自身の説明](/design/self-profile.md)）を最優先で返し、詳しい資料を 1 つ添える。
- 家族の会話の本文は返さない。`why(ignored)` は分類と確率だけ（宛先ゲートで LLM に渡さなかったものをここから漏らさない）。
- 追加ビルドを避けるため、mcp ライブラリ（1.22）同梱の xiaozhi-server イメージで実行する（llm-proxy と同じ）。

# 考慮した代替

- **context_providers で毎回システムプロンプトに入れる**: 仕組みや記録を毎回入れるとプロンプトが長く遅くなる。聞かれた時だけ引く MCP にした。記憶は短いので context_providers のまま（→ [会話の記憶](/design/conversation-memory.md)）。
- **brain に MCP を載せる**: brain は会話の中継という重要な経路なので、機能と障害点を増やさない。`mcp/` は MCP サーバーの置き場として決めてある。
- **エージェント実行環境（OpenAI Agents SDK / codex app-server / Claude Agent SDK など）**: 何ステップも自分で調べるので、決まっていない調べものに強い。一方で数十秒〜数分かかり音声の同期応答に向かず、費用と危険（コードの読み書き・コマンド実行）が大きい。**第2段階の候補**として、「調べてみるね」→ 読み取り専用の道具だけのエージェントが調べる → 結果を brain の `/say`（自発発話の経路、[決定 007](/decisions/007-proactive-speech-path.md)）で折り返す形を想定する。導入前に、Vercel AI Gateway の 1 本のキーで動くか（[決定 008](/decisions/008-llm-via-vercel-gateway.md)）を確かめる（codex app-server・Claude Agent SDK は未確認）。

# 帰結

- ツールを 1 回挟むので、最初の文まで約 3.5〜4 秒（ツールなしより約 2 秒遅い）。1 回だけ 10.7 秒かかった。[^run-0929]
- xiaozhi-server は接続後にツールとシステムプロンプトを後から読み込む。接続直後に届いた発話にはツールが無い（疑似端末で確認）。実機は発話が接続の数秒後に届くので影響は小さい。
- ツールの結果は LLM と一緒にクラウドへ送られる。okf には秘密情報を書かない決まり（原則6）なので許容する。
- option-quants（M4）も同じサーバー側 MCP の口でつなげる。

# 段階

1. 読むだけ（この決定）。`evals/self_run.py` で 5/5（2026-09-29）。
2. 自分から話す: 新しい機能が入った後の成長の報告、Claude Code のフックから `/say` で作業完了を知らせる。調べて折り返すエージェント（上記、要確認）。
3. 書き込み（要検討）: 声で「メモしておいて」→ GitHub issue など。確認の手順を挟む。声からコードを変える作業をさせるのはスコープ外。

[^approval]: 2026-09-29 のユーザー指示
[^mcp-manager]: server_mcp/mcp_manager.py
[^mcp-client]: server_mcp/mcp_client.py
[^run-0929]: 2026-09-29 疑似端末での試験
