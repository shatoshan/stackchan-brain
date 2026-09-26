---
type: Decision
title: "009（不採用）: 近接センサで会話を開くファームパッチ"
description: 待機中の端末にはサーバーから届かないため、近接センサ（LTR-553）で人が近くに居続けたら端末から会話を開くパッチを加える。原則2の改訂。
tags: [decision, adr, firmware, proximity]
status: deprecated
generated: { by: claude-code/opus-5.5, at: 2026-09-26T13:04:12Z }
sources:
  - id: approval
    resource: process:chat-2026-09-26
    title: 2026-09-26 のユーザー指示（「ファーム改定してでの近接判定も組み込みたい」）
    author: human:shingo
  - id: fw-grep
    resource: https://github.com/m5stack/StackChan/tree/1b5765599fba8aaad1811d9a79358ccc7051f5f3/firmware/main
    title: StackChan firmware/main（LTR553 / proximity の参照なし）
  - id: ltr553
    resource: https://github.com/m5stack/uiflow-micropython/blob/master/m5stack/patches/2005-Support-LTR553.patch
    title: M5Unified LTR553_Class（uiflow-micropython のパッチとして公開）
  - id: xz-app
    resource: https://github.com/78/xiaozhi-esp32/blob/v2.2.4/main/application.cc
    title: xiaozhi-esp32 v2.2.4 application.cc
---

> **deprecated（2026-09-26）。** 実装・実機計測の結果、LTR-553 は数 cm 程度しか検知できず「人が近くにいる」判定に使えないため、human:shingo の判断で不採用。端末はパッチなしのファームに戻す。原則2の改訂も取り消し。代わりはカメラ（→ [カメラで在席を知る](/design/camera-presence.md)）。

# 実測（2026-09-26、LED パルス 15 回、ゲイン既定）

| 状況 | 近接値（0〜2047） |
|---|---|
| 離れている | 38〜48 |
| 顔 約 20cm / 約 50cm | 52〜71（離れている時とほぼ区別できない） |
| 手のひら 約 3cm | 381〜632 |

- LED パルス 1 回（既定）では、顔を近づけても 0〜15 しか出なかった。
- 実装上の落とし穴: `Hal::startXiaozhi()` の `hal_bridge::start_xiaozhi_app()` は戻らないので、それより後に書いた処理は実行されない。新規 .cpp は `idf.py reconfigure` しないとビルド対象に入らない。

# 背景

- 公式ファームは近接センサ（CoreS3 内蔵 LTR-553）を読んでいない。[^fw-grep]
- WebSocket モードの端末は、待機中はサーバーに接続していない。brain からは届かない（[決定 007](/decisions/007-proactive-speech-path.md)、[XiaoZhi プロトコル](/protocol/xiaozhi-protocol.md)）。
- 「AI Agent を開いていて、人が近くにいて、話しかけがない時に StackChan から話しかける」には、端末が自分から会話を開く必要がある。[^approval]

# 決定

- **設計原則2を改訂する。** 端末ファームの変更は「`OTA_URL` / `STACKCHAN_SERVER_URL`」に加え、「`firmware-patches/` で管理する最小限のパッチ」を許す。パッチは 1 目的 1 ファイル、既存ファイルへの変更は呼び出し数行に留め、プロトコル処理（`application.cc` 等の xiaozhi-esp32 部分）には触れない。[^approval]
- 最初のパッチ `firmware-patches/0001-proximity-wake.patch`:
  - `main/hal/hal_proximity.cpp` を追加。I2C（アドレス 0x23）で LTR-553 の近接値を 200ms ごとに読む。レジスタは M5Unified の実装に合わせる（PART_ID 0x86=0x92、MANUFAC_ID 0x87=0x05、PS_CONTR 0x81=0x03、PS_DATA 0x8D〜0x8E の 11bit）。[^ltr553]
  - AI Agent が待機中（`is_xiaozhi_ready && is_xiaozhi_idle`）に「近い」が 10 秒（テスト用）続いたら、頭タッチと同じ `hal_bridge::toggle_xiaozhi_chat_state()` で会話を開く。一度開いたら、3 秒以上離れるまで再発動しない。
  - `hal.cpp` の `Hal::startXiaozhi()` から起動（AI Agent を開いた時だけ動く）。
  - センサが見つからない / ID が違う時はタスクを終了するだけで、ファームは止めない。
- 会話を開いた後は brain が判断する。まだ誰も話していないセッションは開いて 5 秒で判定に入り、Jev の `just_woken_no_talk` として話しかける（→ [brain](/services/brain.md)）。

# 考慮した代替

- カメラで在席確認（原則内）: 端末の `self.camera.take_photo` を brain から呼び、画像解析で人の有無を見る。会話中しか使えず、待機中の要件を満たさない。画像が外部に送られる。補助としては今後検討。
- ウェイクワード経路（`WakeWordInvoke`）: 使えるが、頭タッチで実績のある `ToggleChatState` 経路を選んだ。[^xz-app]

# 未確定

- 近接値の閾値（近い ≥120、離れた <60）は仮。実機のログ（`HAL-Proximity ps=...`、2 秒ごと）で調整する。
- 10 秒はテスト用。運用値は実機で決める。

[^approval]: 2026-09-26 のユーザー指示
[^fw-grep]: StackChan firmware/main
[^ltr553]: M5Unified LTR553_Class
[^xz-app]: xiaozhi-esp32 v2.2.4 application.cc
