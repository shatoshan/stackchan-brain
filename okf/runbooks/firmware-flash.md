---
type: Runbook
title: ファームの OTA_URL を自前サーバーに向けて書き込む（M2）
description: StackChan 公式ファームを OTA_URL だけ変えてビルドし、USB で書き込む手順。
tags: [runbook, firmware, esp-idf, flash]
status: draft
stale_after: 2026-12-26T00:00:00Z
generated: { by: claude-code/opus-5.5, at: 2026-09-26T08:15:00Z }
sources:
  - id: fw-readme
    resource: https://github.com/m5stack/StackChan/blob/1b5765599fba8aaad1811d9a79358ccc7051f5f3/firmware/README.md
    title: StackChan firmware/README.md
  - id: fw-cmake
    resource: https://github.com/m5stack/StackChan/blob/1b5765599fba8aaad1811d9a79358ccc7051f5f3/firmware/CMakeLists.txt
    title: StackChan firmware/CMakeLists.txt
  - id: kconfig
    resource: https://github.com/m5stack/StackChan/blob/1b5765599fba8aaad1811d9a79358ccc7051f5f3/firmware/main/Kconfig.projbuild
    title: StackChan firmware/main/Kconfig.projbuild
---

> `status: draft` の理由: まだ実行していない。M2 で人間が実機で確認したら `verified` を付ける。

# 手順（予定）

1. ESP-IDF **v5.5.4** を入れる。[^fw-readme]
2. `git clone https://github.com/m5stack/StackChan && cd StackChan/firmware && python3 ./fetch_repos.py`[^fw-readme]
3. `firmware/sdkconfig.defaults.local` を作る（追跡ファイルは変えない）:[^fw-cmake] [^kconfig]
   ```
   CONFIG_OTA_URL="http://<MacのLAN IP>:8003/xiaozhi/ota/"
   ```
4. 既に `sdkconfig` があれば消す（defaults が反映されないのを防ぐ。ESP-IDF の一般的挙動で未検証）。
5. `idf.py build` → USB 接続して `idf.py flash`（必要なら `-p /dev/cu.usbmodem*`）。[^fw-readme]
6. 起動ログ（`idf.py monitor`）で OTA 応答の WebSocket URL が自前サーバーになっていることを確認し、xiaozhi-server のログに接続が来るのを見る。

# 注意

- Mac の LAN IP が変わると端末が繋がらなくなる。ルーターで DHCP 予約するか、mDNS 名を使うか検討（未検討）。
- `STACKCHAN_SERVER_URL` は変えない（アプリ連携はそのまま）。

[^fw-readme]: StackChan firmware/README.md
[^fw-cmake]: StackChan firmware/CMakeLists.txt
[^kconfig]: StackChan firmware/main/Kconfig.projbuild
