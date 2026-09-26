---
type: Hardware
title: StackChan（M5Stack 公式版）ハードウェア
description: CoreS3 ベースの StackChan 本体とロボット部の物理仕様。
tags: [stackchan, cores3, esp32-s3, hardware]
status: stable
generated: { by: claude-code/opus-5.5, at: 2026-09-26T07:00:00Z }
sources:
  - id: stackchan-readme
    resource: https://github.com/m5stack/StackChan/blob/1b5765599fba8aaad1811d9a79358ccc7051f5f3/README.md
    title: m5stack/StackChan README (commit 1b57655)
    author: org:m5stack
    last_modified: 2026-08-19T08:28:59Z
---

# 本体（CoreS3）

| 項目 | 仕様 |
|---|---|
| SoC | ESP32-S3（240MHz デュアルコア、Wi-Fi / BLE） |
| メモリ | 16MB Flash / 8MB PSRAM |
| 表示 | 2.0 インチ静電容量式タッチ液晶 |
| カメラ | 0.3MP |
| センサ | 近接・照度センサ、9軸 IMU（加速度・ジャイロ・地磁気） |
| 音声 | 1W スピーカー、デュアルマイク |
| その他 | microSD スロット、電源/リセットボタン |

[^stackchan-readme]

# ロボット本体

| 項目 | 仕様 |
|---|---|
| 首サーボ | 2軸フィードバックサーボ：水平（yaw）360°連続回転 / 垂直（pitch）90° |
| LED | RGB LED 2列・計12個 |
| 入出力 | IR 送受信、3ゾーンタッチパネル、NFC モジュール |
| 電源 | 550mAh バッテリー、USB-C（給電・データ） |

[^stackchan-readme]

# このプロジェクトでの意味

- デュアルマイクは xiaozhi-esp32 の AEC / リモートウェイク系機能の前提条件になっている（→ [xiaozhi-esp32-server](/services/xiaozhi-esp32-server.md)）。
- サーボの制御範囲は端末 MCP ツール側で制限される（→ [端末MCPツール](/firmware/device-mcp-tools.md)）。

[^stackchan-readme]: m5stack/StackChan README
