# Update Log

## 2026-09-26
* **Verification**: human:shingo が首（右向き）と LED（青）の物理動作を確認。[端末MCPツール](/firmware/device-mcp-tools.md)、[ファーム書き込み](/runbooks/firmware-flash.md) に `verified` を記録。
* **Decision**: [決定 007](/decisions/007-proactive-speech-path.md) を案 A（brain の WebSocket 中継）で確定し `stable` に。
* **Milestone**: M2 達成（エージェント確認、`verified` は人間待ち）。ESP-IDF v5.5.4 を導入し、`OTA_URL` だけを `sdkconfig.defaults.local` で変えたファームを書き込み（事前に Flash 16MB をバックアップ）。実機が自前サーバーに接続し日本語で会話、首（`set_head_angles`）と LED（`set_led_color`）を LLM から操作できた。[ファーム書き込み](/runbooks/firmware-flash.md) を `stable` に。
* **Correction**: 実機はウェイクワード検出時に `listen`/`detect` を送らない（`listen`/`start` のみ）。中国語「嘿，你好呀」の注入は実機では起きない。[公式ファーム](/firmware/official-firmware.md)、[xiaozhi-esp32-server](/services/xiaozhi-esp32-server.md) を訂正。
* **Update**: [端末MCPツール](/firmware/device-mcp-tools.md) に実機の 11 ツールと呼び出し結果、[XiaoZhi プロトコル](/protocol/xiaozhi-protocol.md) に実機のセッションの流れを追記。
* **Update**: 中国向けのデフォルト設定を整理。サーバープラグインを `functions: []`、`wakeup_words` を `HiStackChan` ほか、ウェイクワード応答キャッシュ無効、`exit_commands` を日本語に。詳細と落とし穴は [xiaozhi-esp32-server](/services/xiaozhi-esp32-server.md)「日本語で使う際の落とし穴」。
* **Finding**: 本体が中国語の few-shot と「嘿，你好呀」を LLM に渡すため、Luna がウェイクワードに 5 回中 3 回中国語で返答。[llm-proxy](/services/llm-proxy.md) に完全一致の日本語置換を追加し 5/5 日本語に。
* **Update**: [公式ファーム](/firmware/official-firmware.md) にウェイクワード（`wn9_histackchan_tts3`、`Hi,Stack Chan`）を追記。[GPT-6 Luna](/external/openai-gpt-6-luna.md) に function calling の実測を追記。
* **Milestone**: M1 達成。有料クレジット投入後、疑似デバイス → xiaozhi-server → llm-proxy → Gateway → GPT-6 Luna で日本語の一往復（「こんにちは。また会えてうれしいよ」、約 3 秒）。[GPT-6 Luna](/external/openai-gpt-6-luna.md) を `stable` に。
* **Update**: 実キーで疎通。[GPT-6 Luna](/external/openai-gpt-6-luna.md) は Vercel 無料枠で 403（有料クレジットが必要）。[Jev](/external/jev.md) は無料枠で 200（確率 0.59、約 160ms）。[Vercel AI Gateway](/external/vercel-ai-gateway.md) に無料枠の制限を追記。
* **Decision**: [決定 008](/decisions/008-llm-via-vercel-gateway.md)。ユーザー指示によりランタイム LLM を GPT-6 Luna（`openai/gpt-6-luna`）に変更し、LLM と Jev を Vercel AI Gateway の 1 本のキーに統一。
* **Creation**: [Vercel AI Gateway](/external/vercel-ai-gateway.md)、[GPT-6 Luna](/external/openai-gpt-6-luna.md)（draft）、[llm-proxy](/services/llm-proxy.md)。Luna は Chat Completions の function calling に `reasoning_effort: none` が必須で、xiaozhi-server はそれを送れないため中継を追加。
* **Deprecation**: [Anthropic API](/external/anthropic-api.md)、[決定 004](/decisions/004-no-bedrock.md)。後継は決定 008。
* **Update**: [3層アーキテクチャ](/design/three-layer-architecture.md) の熟考層を Luna に。[Jev](/external/jev.md) に Gateway カタログ上 `zdr: none` であることを追記。[起動手順](/runbooks/server-startup.md) を Gateway 構成に更新。
* **Initialization**: OKF v0.2 バンドルを作成。キックオフ指示書 §3 の内容を概念ファイルに転記（hardware / firmware / services / external / design / decisions 001〜006）。
* **Update**: [xiaozhi-esp32-server](/services/xiaozhi-esp32-server.md) を一次情報（v0.9.6 / commit 788f530）で確認し `stable` に。最小構成の起動方法・設定キー・OTA エンドポイントの存在を記録。
* **Correction**: 公式 Docker イメージは arm64 も提供されている（Deployment.md の「0.8.2 以降 x86 のみ」は古い記述）。
* **Correction**: Jev の確率は Vercel Gateway ではレスポンスの `answers` に入る（キックオフの「providerMetadata で返る」は不正確）。モデル ID は `typesafe-ai/jev`。[Jev](/external/jev.md)、[決定 005](/decisions/005-jev-via-vercel-gateway.md) に反映。
* **Creation**: [XiaoZhi プロトコル](/protocol/xiaozhi-protocol.md)（draft）。xiaozhi-server に発話押し込み API は無く、WebSocket 端末は idle 中に到達不能と判明。
* **Creation**: [決定 007（draft）](/decisions/007-proactive-speech-path.md)。brain を WebSocket 中継にして `listen/detect`（`[device_call]` 付きは直接読み上げ）を注入する案を推奨。疑似デバイスで直接読み上げを確認。
* **Update**: [Anthropic API](/external/anthropic-api.md) の最新 Haiku を `claude-haiku-4-5-20251001` と確認。
* **Creation**: runbooks（[起動](/runbooks/server-startup.md)、[疑似デバイス](/runbooks/simulator.md)、[ファーム書き込み](/runbooks/firmware-flash.md)）。
* **Verification（エージェント実行、`verified` は付けない）**: `docker compose up` で xiaozhi-server が healthy、OTA 応答と疑似デバイスでの一往復（ダミーキーのため LLM は 401 → 定型文 TTS）を確認。
