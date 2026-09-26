---
type: Design
title: カメラで在席・顔の向きを知る（ファーム無改変の実現可能性）
description: StackChan のカメラ画像をサーバー側で使う経路の調査結果。AI Agent 中に使えるのは take_photo（Explain）経路で、写真の送り先を brain に向ければ LAN 内で顔検出できる。
tags: [design, camera, presence, feasibility]
status: draft
stale_after: 2026-12-26T00:00:00Z
generated: { by: claude-code/opus-5.5, at: 2026-09-26T14:05:37Z }
sources:
  - id: ws-avatar
    resource: https://github.com/m5stack/StackChan/blob/1b5765599fba8aaad1811d9a79358ccc7051f5f3/firmware/main/hal/hal_ws_avatar.cpp
    title: StackChan firmware/main/hal/hal_ws_avatar.cpp
  - id: app-avatar
    resource: https://github.com/m5stack/StackChan/blob/1b5765599fba8aaad1811d9a79358ccc7051f5f3/firmware/main/apps/app_avatar/app_avatar.cpp
    title: StackChan firmware/main/apps/app_avatar/app_avatar.cpp
  - id: app-ai
    resource: https://github.com/m5stack/StackChan/blob/1b5765599fba8aaad1811d9a79358ccc7051f5f3/firmware/main/apps/app_ai_agent/app_ai_agent.cpp
    title: StackChan firmware/main/apps/app_ai_agent/app_ai_agent.cpp
  - id: hal-warm
    resource: https://github.com/m5stack/StackChan/blob/1b5765599fba8aaad1811d9a79358ccc7051f5f3/firmware/main/hal/hal.cpp
    title: StackChan firmware/main/hal/hal.cpp（requestWarmReboot）
  - id: secret
    resource: https://github.com/m5stack/StackChan/blob/1b5765599fba8aaad1811d9a79358ccc7051f5f3/firmware/main/hal/utils/secret_logic/secret_logic.cpp
    title: StackChan firmware/main/hal/utils/secret_logic/secret_logic.cpp
  - id: camera
    resource: https://github.com/m5stack/StackChan/blob/1b5765599fba8aaad1811d9a79358ccc7051f5f3/firmware/main/hal/board/stackchan_camera.cc
    title: StackChan firmware/main/hal/board/stackchan_camera.cc（Explain）
  - id: mcp-server
    resource: https://github.com/78/xiaozhi-esp32/blob/v2.2.4/main/mcp_server.cc
    title: xiaozhi-esp32 v2.2.4 main/mcp_server.cc（take_photo、ParseCapabilities）
  - id: report
    resource: process:chat-2026-09-26
    title: 2026-09-26 にユーザーが共有した調査レポート（カメラ経路 2 本）
---

> `status: draft` の理由: ソースを読んだ結果で、brain での受け取りはまだ実装・実測していない。

# 結論

| 経路 | AI Agent 中に使えるか | ファーム改変 |
|---|---|---|
| 1. StackChan Server 向け WebSocket（`/stackChan/ws`）のカメラストリーム | **使えない** | 不要だが、Avatar アプリでしか動かない |
| 2. `self.camera.take_photo`（Explain） | **使える**（XiaoZhi のセッションが開いている間） | 不要 |

# 経路 1: `/stackChan/ws`（使えない）

- 実装はレポートの説明どおり: サーバーが `0x05` を送ると 350ms（ビデオモードは 700ms）ごとにフレームを取得し、JPEG（品質 20）にして `[種別 1B][長さ 4B BE][本体]` で送る。`0x06` で停止。URL は `CONFIG_STACKCHAN_SERVER_URL + /stackChan/ws?deviceType=StackChan`、認証ヘッダは既定の弱いシンボルで固定文字列 `hi-stack-chan`。[^ws-avatar] [^secret]
- **しかし、このサービスを起動するのは Avatar アプリ（`AppAvatar::onOpen` → `startWebSocketAvatarService`）だけ。** AI Agent アプリは `requestXiaozhiStart()` を呼ぶだけで、この WebSocket を開かない。[^app-avatar] [^app-ai]
- アプリの切り替えは warm reboot（NVS にアプリ番号を書いて `esp_restart`）なので、Avatar と AI Agent は同時に動かない。[^hal-warm]
- レポートの「ビデオ通話で使われている経路なので音声セッションと同時に動く前提」は Avatar アプリ内の話で、そこでの音声はこの WebSocket 上の独自 Opus（`0x01`）。XiaoZhi の音声セッションとは別物。[^report] [^ws-avatar]

# 経路 2: take_photo / Explain（使える）

- `self.camera.take_photo(question)` は `Capture()` でその場で 1 枚撮り、`Explain(question)` で送る。[^mcp-server]
- 送り先 URL とトークンは、サーバーが MCP `initialize` の `params.capabilities.vision.{url, token}` で端末に渡したもの（`ParseCapabilities` → `SetExplainUrl`）。[^mcp-server]
- 送り方: `POST`、`multipart/form-data`（フィールド `question`、ファイル `file` = `camera.jpg`、JPEG 品質 80）、ヘッダ `Device-Id`、`Client-Id`、`Authorization: Bearer <token>`、chunked。200 以外は失敗扱いで、**レスポンス本文がそのままツールの結果になる**。[^camera]
- ⇒ brain の中継で、下りの MCP `initialize` の `vision.url` を brain の HTTP 受け口に書き換えれば、写真は brain に届く。brain は:
  - 自分で呼んだ `take_photo`（在席確認）なら、LAN 内で顔検出（OpenCV YuNet 等）して結果を返す。クラウドに顔を送らない。
  - LLM が呼んだ `take_photo`（「何が見える？」）なら、xiaozhi-server の `/mcp/vision/explain`（VLLM）へ転送する（要 VLLM 設定）。
- brain からの呼び出しは既存の端末 MCP 直接呼び出し（id 900000 台）で可能（→ [brain](/services/brain.md)）。

# 残る制約

- **XiaoZhi のセッションが開いている間しか使えない。** 待機中（未接続）の端末にはサーバーから届かない（[決定 007](/decisions/007-proactive-speech-path.md)）。「AI Agent を開いて放置 → 人が来たら話しかける」には、最初に一度ウェイクワードかタッチでセッションを開き、無音タイムアウト（`XIAOZHI_NO_VOICE_CLOSE_SEC`）を十分長くしてセッションを保ち続ける必要がある。
  - その間マイク音声は常にサーバーへ流れ、部屋の会話やテレビの声で VAD→ASR→LLM が反応しうる。給電前提。
- 1 枚あたりの撮影＋JPEG 化＋送信時間、画像サイズ（QVGA 想定）、顔検出の距離の限界は未実測。

# 次の一手（案）

1. brain に Explain 受け口を作り、`vision.url` を書き換える。LLM 由来の依頼は xiaozhi-server に転送。
2. brain から数十秒おきに `take_photo` を呼び、YuNet で「顔の数・最大の顔の幅比・中心 x」を出して状態ブロブへ。中心 x は首の yaw に使う。
3. 長時間セッションでの誤反応（テレビ等）と電力を実測する。

[^ws-avatar]: hal_ws_avatar.cpp
[^app-avatar]: app_avatar.cpp
[^app-ai]: app_ai_agent.cpp
[^hal-warm]: hal.cpp
[^secret]: secret_logic.cpp
[^camera]: stackchan_camera.cc
[^mcp-server]: mcp_server.cc
[^report]: 2026-09-26 共有レポート
