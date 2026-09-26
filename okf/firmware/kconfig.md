---
type: Firmware
title: StackChan ファームの Kconfig（接続先設定）
description: 端末が接続するサーバーを決める OTA_URL と STACKCHAN_SERVER_URL。
tags: [firmware, kconfig, ota]
status: stable
stale_after: 2026-12-26T00:00:00Z
generated: { by: claude-code/opus-5.5, at: 2026-09-26T07:00:00Z }
sources:
  - id: kconfig
    resource: https://github.com/m5stack/StackChan/blob/1b5765599fba8aaad1811d9a79358ccc7051f5f3/firmware/main/Kconfig.projbuild
    title: StackChan firmware/main/Kconfig.projbuild
  - id: fw-cmake
    resource: https://github.com/m5stack/StackChan/blob/1b5765599fba8aaad1811d9a79358ccc7051f5f3/firmware/CMakeLists.txt
    title: StackChan firmware/CMakeLists.txt
---

# `CONFIG_OTA_URL`（menu "Xiaozhi Assistant"）

- デフォルト `https://api.tenclass.net/xiaozhi/ota/`。端末は起動時にここへアクセスし、新ファームの有無と **WebSocket / MQTT サーバーのアドレス** を受け取る。[^kconfig]
- 自前サーバーに向けるにはここを `http://<MacのLAN IP>:8003/xiaozhi/ota/` に変えて一度だけリビルドする。xiaozhi-esp32-server の最小構成は OTA エンドポイントを内蔵しているので、端末側の変更はこれだけで済む（→ [xiaozhi-esp32-server](/services/xiaozhi-esp32-server.md)）。

# `CONFIG_STACKCHAN_SERVER_URL`（menu "StackChan Server"）

- StackChan Server（Go 製、アプリ連携・コミュニティ機能）のベース URL。デフォルト `http://47.113.125.164:12800`。HAL が `/stackChan/device/user`、`/stackChan/apps`、`/stackChan/ws` 等のパスを組み立てる。[^kconfig]
- 当面は触らない（設計原則2）。

# 上書き方法

- Kconfig の help 自身が「`sdkconfig.defaults.local` で上書きせよ」と案内しており、CMakeLists.txt がそのファイルを自動で重ねる。[^kconfig] [^fw-cmake]
- 注意（未検証・ESP-IDF の一般的挙動）: 既に `sdkconfig` が生成済みだと defaults の変更が反映されないことがある。その場合は `sdkconfig` を消すか `idf.py fullclean` してからビルドする。

[^kconfig]: StackChan firmware/main/Kconfig.projbuild
[^fw-cmake]: StackChan firmware/CMakeLists.txt
