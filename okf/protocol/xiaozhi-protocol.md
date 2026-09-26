---
type: Protocol
title: XiaoZhi 通信プロトコル（WebSocket / MQTT+UDP）の要点
description: 端末（xiaozhi-esp32 v2.2.4）とサーバー間のメッセージ種別と、音声チャネルの開閉条件。自律発話設計の前提。
tags: [protocol, websocket, mqtt, xiaozhi]
status: draft
stale_after: 2026-12-26T00:00:00Z
generated: { by: claude-code/opus-5.5, at: 2026-09-26T07:00:00Z }
sources:
  - id: xz-app-224
    resource: https://github.com/78/xiaozhi-esp32/blob/v2.2.4/main/application.cc
    title: 78/xiaozhi-esp32 v2.2.4 main/application.cc
  - id: xz-ws-224
    resource: https://github.com/78/xiaozhi-esp32/blob/v2.2.4/main/protocols/websocket_protocol.cc
    title: 78/xiaozhi-esp32 v2.2.4 main/protocols/websocket_protocol.cc
  - id: srv-listen
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/main/xiaozhi-server/core/handle/textHandler/listenMessageHandler.py
    title: xiaozhi-esp32-server listenMessageHandler.py
  - id: srv-types
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/main/xiaozhi-server/core/handle/textMessageType.py
    title: xiaozhi-esp32-server textMessageType.py
  - id: srv-config
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/main/xiaozhi-server/config.yaml
    title: xiaozhi-esp32-server config.yaml
  - id: srv-devcall
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/docs/device-call-guide.md
    title: xiaozhi-esp32-server docs/device-call-guide.md
  - id: xz-protocol-doc
    resource: https://ccnphfhqs21z.feishu.cn/wiki/M0XiwldO9iJwHikpXD5cEx71nKh
    title: 小智通信协议（Feishu wiki、未読）
  - id: m2-0926
    resource: process:claude-code-session-2026-09-26
    title: 2026-09-26 M2 実機試験（MAC XX:XX:XX:XX:XX:XX、App 1.5.1、シリアルログ＋xiaozhi-server ログ）
---

> `status: draft` の理由: ソースコードから読み取った内容で、実機・疑似デバイスでの通信確認をまだしていない。公式プロトコル文書（Feishu wiki）は未読。

# トランスポートの選択

- 端末は OTA 応答に `mqtt` キーがあれば MQTT+UDP、`websocket` キーがあれば WebSocket を使う。[^xz-app-224]
- xiaozhi-esp32-server 最小構成は `server.mqtt_gateway` 未設定なら `websocket: {url, token}` を返す（→ [xiaozhi-esp32-server](/services/xiaozhi-esp32-server.md)）。

# 音声チャネルの開閉（自律発話の最大の制約）

- **WebSocket モードでは `Start()` で接続しない**。コメント曰く「音声チャネルが必要になった時だけ接続する」。[^xz-ws-224]
- 接続（`OpenAudioChannel`）は端末側のイベントでのみ行われる：ウェイクワード、ボタン、StackChan ではタッチ等から `ToggleChatState()`。[^xz-app-224]
- サーバー側も無音が `close_connection_no_voice_time`（デフォルト 120 秒）続くと切断する。[^srv-config]
- ⇒ **端末が idle の間、サーバーから端末に届く経路は WebSocket モードには存在しない。**

# 端末が受け付けるサーバー→端末 JSON（v2.2.4 `OnIncomingJson`）

| `type` | 動作 |
|---|---|
| `tts` | `state: start` で Speaking 状態へ、`stop` で Listening/Idle へ戻る、`sentence_start` の `text` を画面表示 |
| `stt` | 認識テキストを画面にユーザー発話として表示 |
| `llm` | `emotion` で表情変更 |
| `mcp` | `payload` を端末 MCP サーバーへ（JSON-RPC）→ [端末MCPツール](/firmware/device-mcp-tools.md) |
| `system` | `command: reboot` のみ |
| `alert` | `status`/`message`/`emotion` を表示し効果音（TTS ではない） |
| `custom` | `CONFIG_RECEIVE_CUSTOM_MESSAGE` 有効時のみ、画面表示 |

[^xz-app-224]

- 受信した Opus 音声は **端末が Speaking 状態の時だけ** 再生キューに入る（`OnIncomingAudio`）。つまりセッション中なら、サーバーが `tts start` → Opus フレーム → `tts stop` を送れば、ユーザー発話なしでも喋らせられる。[^xz-app-224]

# 端末→サーバー JSON（サーバーが処理する種別）

- `hello` / `abort` / `listen` / `iot` / `mcp` / `server` / `ping`。[^srv-types]
- `listen` の `state: detect` に `text` を付けると、サーバーは音声認識を経ずにそのテキストで LLM→TTS を開始する（ウェイクワード判定あり）。`[device_call]` 接頭辞付きならそのテキストを LLM を通さず直接 TTS する。[^srv-listen]
  - 2026-09-26 に疑似デバイスで両方の挙動を確認（`[device_call]` 付きは LLM を呼ばずに読み上げ、同文を `stt` としても返す）。
  - これは「接続中のクライアントからの入力」であり、別プロセス（brain）から既存セッションに差し込む API ではない。

- 2026-09-26 観測: サーバーはツール実行時に `{"type":"stt","text":"% <関数名>"}`、表情用に `{"type":"llm","text":"🙂","emotion":...}` も送る。どちらも表示用で音声は伴わない。疑似デバイスで `text` を拾う時は `tts`/`sentence_start` だけを見ること。

# MQTT+UDP モード

- MQTT は制御チャネルが常時接続なので、サーバー（MQTT ゲートウェイ経由）→端末の JSON は idle 中でも届く。ただし音声（UDP）チャネルを開くのは端末側。
- xiaozhi-esp32-server の「設備呼叫」機能は、idle 端末を起こすために **ファームに `RemoteWakeup` MCP ツールを追加する改造** を要求している（xiaozhi-esp32 2.1.0〜2.2.6 対象）。= 無改造ファームではサーバーから会話を開始できないことの傍証。[^srv-devcall]
- MQTT ゲートウェイ（`xinnan-tech/xiaozhi-mqtt-gateway`）の導入は未検討。

# 実機のセッションの流れ（2026-09-26 観測）

1. idle 中にウェイクワード検出 → `connecting` → WebSocket 接続 → hello 交換。
2. 端末は `listen`/`start`（`mode: auto`）を送り `listening` へ。サーバーは MCP `initialize` → `tools/list` を送る。
3. 発話は端末側 VAD で区切られ、サーバーが ASR → LLM → TTS。`tts start` で `speaking`、`tts stop` で再び `listening`（`mode: auto` なので自動で聞き続ける）。
4. `handle_exit_intent` 等で終了すると `listening -> idle`。無音 `close_connection_no_voice_time`（120 秒）でもサーバーが切断する。

- セッション中は `speaking` と `listening` を往復し続けるので、中継でサーバー発話を差し込む余地はこの間にある（[決定 007](/decisions/007-proactive-speech-path.md)）。[^m2-0926]

# 自律発話への含意

→ [決定 007](/decisions/007-proactive-speech-path.md) を参照。

[^xz-app-224]: xiaozhi-esp32 v2.2.4 application.cc
[^xz-ws-224]: xiaozhi-esp32 v2.2.4 websocket_protocol.cc
[^srv-listen]: xiaozhi-esp32-server listenMessageHandler.py
[^srv-types]: xiaozhi-esp32-server textMessageType.py
[^srv-config]: xiaozhi-esp32-server config.yaml
[^srv-devcall]: xiaozhi-esp32-server docs/device-call-guide.md
[^m2-0926]: 2026-09-26 M2 実機試験
