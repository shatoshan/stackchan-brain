---
type: Service
title: brain（端末 ⇔ xiaozhi-server の WebSocket 中継と自律発話）
description: 端末の WebSocket セッションを xiaozhi-server へ透過中継し、会話を記録する。M3 で判定ループと発話注入を載せる土台。
tags: [service, brain, relay, websocket]
status: stable
generated: { by: claude-code/opus-5.5, at: 2026-09-26T11:21:01Z }
sources:
  - id: code
    resource: ../../brain/relay.py
    title: brain/relay.py
  - id: decision
    resource: /decisions/007-proactive-speech-path.md
    title: 決定 007
  - id: m3-relay
    resource: process:claude-code-session-2026-09-26
    title: 2026-09-26 M3 ステップ1（中継）の疑似デバイス・実機試験
---

# 役割

- [決定 007](/decisions/007-proactive-speech-path.md) の案 A。xiaozhi-server の `server.websocket` を brain（`ws://<LAN IP>:8010/xiaozhi/v1/`）に向けると、端末は OTA 経由で brain に繋ぎ、brain が `ws://xiaozhi-server:8000/xiaozhi/v1/` へ中継する。[^code]
- 現在（ステップ1）は **透過中継と記録だけ**。メッセージは改変しない。発話の注入と判定ループは次のステップで追加する。

# 動作

- 端末の `Authorization` / `Protocol-Version` / `Device-Id` / `Client-Id` ヘッダとクエリ文字列を上流へ引き継ぐ。テキストもバイナリ（Opus）もそのまま双方向に流す。[^code]
- 片側が閉じたらもう片側も閉じる。どちらが先に閉じたか（`device` / `server`）を記録する。[^code]
- セッションごとに `data/brain/sessions/<日時>-<MAC>-<id>.jsonl` へ JSON メッセージを 1 行ずつ記録（`{"t", "dir": "up"|"down"|"meta", "msg"}`）。2000 文字を超えるもの（`tools/list` の結果など）は型と長さだけ。音声は記録しない。[^code]
- 標準ログには発話（`user:`）、返答（`robot:`）、ツール呼び出し、hello / listen / abort を要約して出す。[^code]
- ポート 8010 は LAN に公開する（端末が直接繋ぐため）。`GET /healthz` でヘルスチェック。

# 実測（2026-09-26）

- 実機: AI Agent を開き直すと OTA で新しい URL を受け取り、brain 経由で接続した。「左を向いて」→ `get_head_angles` → `set_head_angles(yaw=-40, pitch=14)` を含め、会話もツール呼び出しも中継前と同様に動いた。[^m3-relay]
- 遅延: 発話の認識結果（`stt`）から最初の返答文まで約 1.6 秒で、中継前と体感差なし。[^m3-relay]

[^code]: brain/relay.py
[^decision]: 決定 007
[^m3-relay]: 2026-09-26 M3 ステップ1 試験
