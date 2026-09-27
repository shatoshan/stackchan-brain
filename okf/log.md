# Update Log

## 2026-09-27
* **Fix**: 宛先ゲートが brain 自身の LLM 代替判定の依頼までゲートにかけていたのを除外（`X-StackChan-Source: brain`）。実機試験の記録を [宛先ゲート](/design/addressee-gate.md) に。
* **Update**: human:shingo が Vercel で TypeSafe のキーを BYOK 登録。Jev の成功率 5% → 70%、平均 0.44 秒。llm-proxy に 429 / 529 の短い再試行。初めて Jev で evals を評価: 判定ループ jev 8/8、宛先ゲートは判定規則を「ロボット宛ての確率 < 0.5 で止める」に変えて jev 14/14。[Jev](/external/jev.md)、[宛先ゲート](/design/addressee-gate.md)、[直感層の質問設計](/design/jev-questions.md)。
* **Creation**: [宛先ゲート](/design/addressee-gate.md)（draft、GitHub #2）。llm-proxy で、ユーザー発話を Jev で分類し、LLM を呼ばずに相槌・無応答で返す。Jev が使えない時は LLM へ渡す。evals（`gate_cases.jsonl`、`gate_run.py`、rule 10/14）。
* **Update**: [Jev](/external/jev.md)。Vercel 経由の 429 が継続（20 回中成功 1）。TypeSafe 直接 API と Vercel BYOK を調査し、llm-proxy で呼び先を切り替え可能に（`JEV_BACKEND`）。brain も llm-proxy 経由に。
* **Update**: evals にルールのみのベースライン判定器（rule 6/8、llm 8/8）。LLM 代替判定の JSON パースを頑健化（JSON の後ろの余分な文字で落ちていた）。
* **Update**: [決定 003](/decisions/003-lan-only.md) と [xiaozhi-esp32-server](/services/xiaozhi-esp32-server.md) に「ASR はローカル必須（セッション中はマイク音声が常時流れるため）」と、認識テキストは LLM 経由でクラウドに出ることを追記。
* **Update**: [llm-proxy](/services/llm-proxy.md) に置換対象の検査スクリプトと実行時の警告を追加（イメージ更新で中国語文言が変わると静かに壊れるため）。
* **Decision**: [決定 011](/decisions/011-usb-powered.md)。常時稼働は USB 給電前提、バッテリー・発熱は評価しない。
* **Update**: 実機の判定を写真付きで貯め、`evals/label.py` でラベル付けして evals にする仕組み。[直感層の質問設計](/design/jev-questions.md)。

## 2026-09-26
* **Decision**: [決定 010](/decisions/010-firmware-silent-shutter.md)。原則2に `firmware-patches/` の最小パッチの例外を設け（human:shingo）、撮影時のシャッター音を消すパッチを当てて書き込み。CLAUDE.md、[ファーム書き込み](/runbooks/firmware-flash.md)、[カメラで在席を知る](/design/camera-presence.md) を更新。
* **Update**: 撮影のたびに端末がシャッター音を鳴らす（ファーム固定）ため、会話中は撮らず、沈黙 30 秒以降と相手が離れた後だけ撮るように。`person_arrived` の話しかけは LLM 経由に（定型文だと戻ってきた文脈が履歴に残らない）。首の向きの符号は正しいことを確認。[カメラで在席を知る](/design/camera-presence.md)
* **Update**: カメラでの在席確認を実装（ファーム無改変）。中継で `take_photo` の送り先を brain に書き換え、YuNet で LAN 内顔検出。実機で顔の有無を検出でき、LLM の「何が見える？」も転送で動作。[カメラで在席を知る](/design/camera-presence.md)、[brain](/services/brain.md)、[状態ブロブ](/design/state-blob.md)、[直感層の質問設計](/design/jev-questions.md) を更新。
* **Finding**: xiaozhi-server の VLLM が「(请使用中文回复)」を固定で付け、結果をそのまま読み上げる。llm-proxy で部分置換して日本語に。[xiaozhi-esp32-server](/services/xiaozhi-esp32-server.md)、[llm-proxy](/services/llm-proxy.md)。
* **Deprecation**: [決定 009](/decisions/009-firmware-proximity-wake.md)。近接センサは数 cm しか検知できず不採用（human:shingo）。原則2を元に戻し、端末もパッチなしに戻す。
* **Creation**: [カメラで在席を知る](/design/camera-presence.md)（draft）。共有レポートの経路 1（`/stackChan/ws`）は Avatar アプリ専用で AI Agent と同時に動かないと判明。経路 2（`take_photo`）は送り先を brain に書き換えればファーム無改変で使える。
* **Decision**: [決定 009](/decisions/009-firmware-proximity-wake.md)。設計原則2を改訂し、`firmware-patches/` の最小パッチを許す。最初のパッチは近接センサ（LTR-553）で待機中に会話を開くもの。CLAUDE.md も改訂。
* **Milestone**: M3 達成。brain が端末 MCP を直接呼んで首を動かす（話す時は正面、沈黙が続くとよそ見）。人間が実機で、話しかけ・首振り・見回しを確認。[brain](/services/brain.md)、[直感層の質問設計](/design/jev-questions.md) を更新。
* **Creation**: [直感層の質問設計](/design/jev-questions.md)（draft）。M3 ステップ3 の判定ループ（`brain/judge.py`）と evals（`evals/cases.jsonl`、`evals/run.py`）。「話すべき確率」ではなく状況を分類させる方式に。実機で、沈黙時は話題の続きを自分から話し、「出かけてくる」の後は黙ることを人間が確認。
* **Finding**: Jev が混雑で 429 を頻発。[Jev](/external/jev.md) に記録。brain は Jev を一時停止して LLM 分類で代替する。
* **Update**: [brain](/services/brain.md)、[状態ブロブ](/design/state-blob.md) を実装に合わせて更新。
* **Decision**: 無音タイムアウトの既定を 600 秒に（human:shingo）。差し込み時の実機画面に問題がないことを human:shingo が確認。
* **Update**: [brain](/services/brain.md) に発話の差し込み（M3 ステップ2、操作 API `127.0.0.1:8011` の `/sessions`・`/say`）。実機で verbatim / llm の両方で自分から話しかけられることを確認。
* **Finding**: 無音タイムアウト 600 秒で、実機セッションは 649 秒維持されサーバー側で閉じた（端末からは切れない、閉じた後は再接続しない）。[決定 007](/decisions/007-proactive-speech-path.md) に前提の検証結果を記録。
* **Update**: xiaozhi-server の中国語 `end_prompt` を無効化し、無音タイムアウトを `.env` で設定可能に。
* **Creation**: [brain](/services/brain.md)（M3 ステップ1）。端末 ⇔ xiaozhi-server の WebSocket 透過中継とセッションログ。xiaozhi-server の `server.websocket` を brain（8010）に向け、実機で会話・ツール呼び出しが中継経由で動くことを確認。
* **Finding**: サーバーが切断すると端末は一度自動で再接続し、無音 150 秒ほどで再び切断される。[XiaoZhi プロトコル](/protocol/xiaozhi-protocol.md)、[決定 007](/decisions/007-proactive-speech-path.md) に追記。
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
