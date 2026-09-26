---
type: Runbook
title: xiaozhi-server の起動と疎通確認
description: .env を用意して docker compose で xiaozhi-server（最小構成）を起動し、OTA と WebSocket の疎通を確認する手順。
tags: [runbook, docker, xiaozhi]
status: stable
stale_after: 2026-12-26T00:00:00Z
generated: { by: claude-code/opus-5.5, at: 2026-09-26T08:15:00Z }
sources:
  - id: deploy
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/docs/Deployment.md
    title: xiaozhi-esp32-server docs/Deployment.md
  - id: run-0926
    resource: process:claude-code-session-2026-09-26
    title: 2026-09-26 MacBook Air（arm64、Docker 28.1.1、VM メモリ 8GB）での実行結果
---

# 前提

- Docker Desktop（arm64 / amd64 どちらでも可）。イメージ約 3GB、ASR モデル約 900MB。
- 設定の意味は [xiaozhi-esp32-server](/services/xiaozhi-esp32-server.md)。

# 手順

1. `.env` を作る: `cp .env.example .env` し、`SERVER_LAN_IP`（`ipconfig getifaddr en0`）と `AI_GATEWAY_API_KEY`（Vercel AI Gateway のキー）を書く。
2. ASR モデルを取得（初回のみ）:
   ```bash
   mkdir -p models/SenseVoiceSmall
   curl -fL -o models/SenseVoiceSmall/model.pt https://modelscope.cn/models/iic/SenseVoiceSmall/resolve/master/model.pt
   ```
   2026-09-26 取得分: 936,291,369 bytes、sha256 `833ca2dcfdf8ec91bd4f31cfac36d6124e0c459074d5e909aec9cabe6204a3ea`。[^run-0926]
3. 起動: `docker compose up -d`。先に [llm-proxy](/services/llm-proxy.md) が healthy になってから xiaozhi-server が起動する。コンテナ起動時に `config/xiaozhi/render_config.py` が `config/xiaozhi/config.template.yaml` を展開して `data/xiaozhi/.config.yaml`（パーミッション 600）を書き、その後 `python app.py` が走る。
4. 確認:
   - `docker compose ps` で `llm-proxy` と `xiaozhi-esp32-server` が両方 `healthy`（ASR ロード込みで約 15〜30 秒）。
   - `docker logs xiaozhi-esp32-server` に `初始化组件: llm成功 GatewayLLM`、`asr成功 FunASR`、`OTA接口是` が出る。ログ中の `172.x` の IP はコンテナ内のもので無視してよい。[^deploy]
   - `curl http://<LAN IP>:8003/xiaozhi/ota/` → `OTA接口运行正常，向设备发送的websocket地址是：ws://<LAN IP>:8000/xiaozhi/v1/`
   - 疑似デバイスで一往復: [疑似デバイス](/runbooks/simulator.md)

# 2026-09-26 の実行結果

- 上記 1〜4 がすべて通った。OTA の POST 応答は `websocket.url = ws://192.168.3.18:8000/xiaozhi/v1/`、`token = ""`、`timezone_offset = 540`。[^run-0926]
- （Anthropic 直の構成で）`ANTHROPIC_API_KEY` がダミーの状態で、LLM 呼び出しは 401、`system_error_response` の日本語定型文が EdgeTTS（ja-JP-NanamiNeural）で返ることを確認。[^run-0926]
- Gateway 構成に切り替え後、`AI_GATEWAY_API_KEY` がダミーの状態で同じテストを行い、Gateway の 401 → 日本語定型文、を確認。`docker logs llm-proxy` に `reasoning_effort=none tools=8` が出る。[^run-0926]

- 有料クレジット投入後、同じテストで GPT-6 Luna から日本語の応答が返ることを確認（M1）。[^run-0926]

# よくある失敗

- `render_config: missing env vars: ...` で再起動ループ → `.env` の該当変数が空。
- `docker compose` が `SERVER_LAN_IP を .env に設定してください` / `AI_GATEWAY_API_KEY を .env に設定してください` で止まる → `.env` が無いか、値が空。
- LLM が定型文しか返さない → `docker logs llm-proxy` で上流のステータスを見る（401 ならキー、403 `RestrictedModelsError` なら Vercel の無料枠で使えないモデル＝有料クレジットが必要、429 ならレート制限）。
- 設定を変えたら `docker compose up -d --force-recreate`（`.config.yaml` は起動時に再生成される）。

[^deploy]: docs/Deployment.md
[^run-0926]: 2026-09-26 の実行結果
