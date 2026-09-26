---
type: Decision
title: "010: 撮影時のシャッター音を消すファームパッチ（原則2の例外）"
description: カメラで定期的に在席確認するため、StackChan の撮影処理が毎回鳴らすシャッター音を 1 行のパッチで止める。原則2に「firmware-patches/ の最小パッチ」の例外を設ける。
tags: [decision, adr, firmware, camera]
status: stable
generated: { by: claude-code/opus-5.5, at: 2026-09-26T14:54:22Z }
sources:
  - id: approval
    resource: process:chat-2026-09-26
    title: 2026-09-26 のユーザー指示（「シャッター音は原則2例外を許容して消して下さい」）
    author: human:shingo
  - id: camera
    resource: https://github.com/m5stack/StackChan/blob/1b5765599fba8aaad1811d9a79358ccc7051f5f3/firmware/main/hal/board/stackchan_camera.cc
    title: StackChan firmware/main/hal/board/stackchan_camera.cc（Capture）
---

# 背景

- `StackChanCamera::Capture()` は先頭で毎回 `hal_bridge::app_play_sound(OGG_CAMERA_SHUTTER)` を鳴らす。`take_photo` は必ず `Capture()` を通るため、brain の在席確認（沈黙中に 15〜20 秒ごと）のたびに音が鳴る。サーバー側からは止められない。[^camera] → [カメラで在席を知る](/design/camera-presence.md)

# 決定

- **設計原則2に例外を設ける。** 端末ファームの変更は「`OTA_URL` / `STACKCHAN_SERVER_URL` の設定」に加え、「`firmware-patches/` で管理する最小限のパッチ」を許す。1 目的 1 パッチ、既存ファイルへの変更は数行、xiaozhi-esp32 部分（プロトコル処理）には触れない。[^approval]
- `firmware-patches/0002-silent-camera-shutter.patch`: `Capture()` のシャッター音の 1 行をコメントアウトする。
- 2026-09-26 に書き込み、在席確認の撮影と「何が見える？」の撮影で音が鳴らないことを human:shingo が実機で確認。
- 帰結: LLM が撮る「何が見える？」の時も音が鳴らなくなる。撮影中であることは音では分からない（LAN 内で閉じ、写真は brain が顔検出するか xiaozhi-server の VLLM に送るだけ）。

# 経緯

- [決定 009](/decisions/009-firmware-proximity-wake.md)（近接センサ）で一度同じ例外を設けたが、センサが使えず取り消した。今回改めて設ける。

[^approval]: 2026-09-26 のユーザー指示
[^camera]: stackchan_camera.cc
