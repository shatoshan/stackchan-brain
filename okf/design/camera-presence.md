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
  - id: cam-0926
    resource: process:claude-code-session-2026-09-26
    title: 2026-09-26 カメラ在席確認の実機試験
---

> `status: draft` の理由: 実装し実機で動いたが、首の向きの符号、長時間セッションでの誤反応・電力は未確認。

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

# 実装（2026-09-26）

- `brain/vision.py`（ポート 8012、LAN 公開）が Explain 互換の受け口。中継が MCP `initialize` の `vision.url` を `BRAIN_VISION_URL` に書き換え、元の URL は端末ごとに覚える。
- brain は聞き取り中のセッションで 15 秒ごと（`BRAIN_PRESENCE_INTERVAL`）に `take_photo(question="__stackchan_brain_presence__")` を呼ぶ。この目印付きの写真だけ YuNet（OpenCV Zoo 2023mar、OpenCV 4.14）で顔検出し、結果（顔の数、最大の顔の幅比、中心 x/y）を返す。枠を描いた最新 1 枚を `data/brain/camera/last.jpg` に保存。
- それ以外（LLM が撮らせた写真）は元の xiaozhi-server の `/mcp/vision/explain` へ転送。VLLM は llm-proxy 経由の GPT-6 Luna。
- 状態ブロブの `person`: `faces_in_view`、`largest_face_width_ratio`、`seconds_face_visible`、`seconds_since_face_seen`、`checked_seconds_ago`（30 秒より古い結果は null）。
- 話しかける時、顔が見えていれば `get_head_angles` の現在値に `(center_x − 0.5) × 60° × 符号` を足した yaw を向く（`BRAIN_CAMERA_HFOV`、`BRAIN_CAMERA_YAW_SIGN`）。

# 実測（2026-09-26、実機）

- 画像は 320×240 の JPEG で約 5.5〜6.7KB。端末→brain の送信 0.02〜0.12 秒、YuNet の検出 5〜14ms（Mac の Docker）。[^cam-0926]
- 正面約 50cm に座ると顔 1（幅比 0.28〜0.32、信頼度 0.89〜0.92）、画面外に出ると 0。[^cam-0926]
- 撮影の依頼から結果まで、Explain の JPEG 化を含めて数秒以内。発話中などで 20 秒以内に返らない時がある（タイムアウトとして扱う）。[^cam-0926]
- 「何が見える？」で LLM が撮った写真は xiaozhi-server に転送され、室内と人物を説明できた。ただし xiaozhi-server の VLLM は質問末尾に「(请使用中文回复)」を固定で付け、結果を LLM を通さずそのまま読み上げるため中国語になった → llm-proxy で日本語指示に置換して解決。[^cam-0926]

# シャッター音（2026-09-26）

- `StackChanCamera::Capture()` の先頭で毎回 `hal_bridge::app_play_sound(OGG_CAMERA_SHUTTER)` を鳴らす。`take_photo` は必ず `Capture()` を通るので、ファーム無改変では消せない。[^camera]
- 撮影前後に音量を 0 にする回避は不採用: 再生が非同期で確実でなく、音量設定は Flash に保存されるため頻繁に変えると書き込みが増える。
- 対処（ファーム無改変）: 会話中は撮らない。誰も話さない時間が 30 秒続いたら 20 秒ごと、相手が離れた（判定休止中）後は戻りを見るため 15 秒ごとに撮る（`BRAIN_PRESENCE_AFTER_QUIET`、`BRAIN_PRESENCE_INTERVAL`、`BRAIN_PRESENCE_INTERVAL_DORMANT`）。
- 完全に消すため、`Capture()` の 1 行をコメントアウトするパッチを当てた（[決定 010](/decisions/010-firmware-silent-shutter.md)、原則2の例外）。撮影頻度の制限（会話中は撮らない）は電力と帯域のために残す。

# 首の向き

- 顔が画像の右（center_x 0.74）の時に yaw を −8 → 6 に回すと、次の撮影で顔が中央付近（0.46）に来た。`BRAIN_CAMERA_YAW_SIGN=1`（画像の右 = yaw の正）で合っている。[^cam-0926]

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
[^cam-0926]: 2026-09-26 カメラ在席確認の実機試験
