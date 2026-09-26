---
type: Service
title: llm-proxy（xiaozhi-server → Vercel AI Gateway 中継）
description: xiaozhi-server が送れない reasoning_effort を注入し、Gateway の API キーを付与する最小の中継サービス。
tags: [service, proxy, vercel, llm]
status: stable
generated: { by: claude-code/opus-5.5, at: 2026-09-26T07:45:00Z }
sources:
  - id: code
    resource: ../../llm-proxy/proxy.py
    title: llm-proxy/proxy.py
  - id: xz-openai
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/main/xiaozhi-server/core/providers/llm/openai/openai.py
    title: xiaozhi-esp32-server core/providers/llm/openai/openai.py（server_0.9.6 イメージ内でも同一を確認）
  - id: run-0926
    resource: process:claude-code-session-2026-09-26
    title: 2026-09-26 モック上流と実 Gateway（401）での動作確認
---

# なぜ必要か

- xiaozhi-server の `type: openai` プロバイダがリクエストに入れるのは `model`、`messages`、`stream`、`tools`（function call 時）と、設定にある `max_tokens` / `temperature` / `top_p` / `frequency_penalty` だけ。`extra_body` は特定ドメイン（aliyuncs.com 等）の思考無効化にしか使われない。[^xz-openai]
- GPT-6 Luna は Chat Completions で tools を使うのに `reasoning_effort: none` が必須（→ [GPT-6 Luna](/external/openai-gpt-6-luna.md)）。本体改変なしでこれを満たすため、中継で注入する（設計原則1）。
- ついでに Gateway の API キーを中継だけが持つ。xiaozhi-server の設定（`data/.config.yaml`）にはダミーキーしか入らない。

# 動作

- `POST */chat/completions`: JSON に `reasoning_effort` も `reasoning` も無ければ `LLM_REASONING_EFFORT`（既定 `none`）を足す。[^code]
- 全リクエストで `Authorization` を `Bearer $AI_GATEWAY_API_KEY` に差し替え、`https://ai-gateway.vercel.sh` に同じパスで転送。レスポンス（SSE 含む）はチャンク単位でそのまま返す。[^code]
- `GET /healthz` はヘルスチェック用。ポートはホストに公開しない（compose ネットワーク内の `http://llm-proxy:8080/v1`）。
- 追加ビルドを避けるため、aiohttp を同梱している xiaozhi-server イメージで `python /opt/llm-proxy/proxy.py` を実行している。

# 確認済み

- モック上流で: キーの差し替え、`reasoning_effort: none` の注入、SSE が 0.2 秒間隔で逐次届く（バッファされない）こと。[^run-0926]
- 実 Gateway で: xiaozhi-server から `tools=8`、`reasoning_effort=none` のリクエストが中継され、Gateway の 401（ダミーキー）がそのまま xiaozhi-server に返ること。[^run-0926]

[^code]: llm-proxy/proxy.py
[^xz-openai]: core/providers/llm/openai/openai.py
[^run-0926]: 2026-09-26 動作確認
