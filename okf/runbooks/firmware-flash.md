---
type: Runbook
title: ファームの OTA_URL を自前サーバーに向けて書き込む（M2）
description: StackChan 公式ファームを OTA_URL だけ変えてビルドし、USB で書き込む手順。
tags: [runbook, firmware, esp-idf, flash]
status: stable
stale_after: 2026-12-26T00:00:00Z
generated: { by: claude-code/opus-5.5, at: 2026-09-26T11:05:00Z }
verified: { by: human:shingo, at: 2026-09-26T11:10:52Z }
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
  - id: idf-setup
    resource: https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32s3/get-started/linux-macos-setup.html
    title: ESP-IDF v5.5.4 Linux/macOS setup
    author: org:espressif
  - id: run-0926
    resource: process:claude-code-session-2026-09-26
    title: 2026-09-26 MacBook Air（macOS 26.6.2、arm64）での実行
---

> 2026-09-26 にエージェントが全手順を実行し、実機での会話と端末 MCP ツール呼び出しまで確認。首と LED が物理的に動くことを人間が確認（`verified`）。

# 1. ESP-IDF v5.5.4 の導入（macOS）

```bash
brew install cmake ninja dfu-util ccache
mkdir -p ~/esp && cd ~/esp
git clone -b v5.5.4 --recursive --depth 1 --shallow-submodules https://github.com/espressif/esp-idf.git
cd ~/esp/esp-idf && ./install.sh esp32s3
. ~/esp/esp-idf/export.sh      # シェルごとに毎回
```

- 公式手順は通常クローン。`--depth 1 --shallow-submodules` はディスク節約のため（本体 656MB）。[^idf-setup]
- 2026-09-26 実績: Homebrew の Python 3.14、cmake 4.4.3 で `install.sh` も `idf.py build` も問題なし。Rosetta 不要。ツールは `~/.espressif`。[^run-0926]

# 2. ファームの取得とビルド

```bash
cd ~/esp && git clone https://github.com/m5stack/StackChan.git
cd StackChan && git checkout 1b5765599fba8aaad1811d9a79358ccc7051f5f3
cd firmware && python3 ./fetch_repos.py        # "Applied patch ... xiaozhi-esp32.patch" が出ることを確認
printf 'CONFIG_OTA_URL="http://<MacのLAN IP>:8003/xiaozhi/ota/"\n' > sdkconfig.defaults.local
git -C ~/esp/StackChan apply <stackchan-brain>/firmware-patches/0002-silent-camera-shutter.patch   # 決定 010
git -C ~/esp/StackChan apply <stackchan-brain>/firmware-patches/0003-always-on-session.patch    # 決定 012（新規ファイルあり）
idf.py reconfigure && idf.py build
grep OTA_URL sdkconfig                          # 上書きされたか確認
```

- `fetch_repos.py` はパッチが当たらないと "cannot be applied cleanly ... skipped" と出して **続行してしまう**。必ずログを確認する。
- ビルドログに `StackChan: detected sdkconfig.defaults.local, applying overlay` が出る。[^fw-cmake] [^run-0926]
- 新規クローンなら `sdkconfig` は無いので削除は不要。既存の作業ツリーで URL を変える時は `sdkconfig` を消してからビルドする（未検証）。
- 2026-09-26 実績: ビルド成功。App version 1.5.1、`stack-chan.bin` 約 3.8MB、`generated_assets.bin` 約 2.3MB。ディスク使用は ESP-IDF + ツール + ビルドで約 5GB。[^run-0926]

# 3. バックアップと書き込み

```bash
esptool.py --port /dev/cu.usbmodem101 flash_id           # ESP32-S3 / 16MB を確認
esptool.py --port /dev/cu.usbmodem101 --baud 921600 read_flash 0 0x1000000 ~/esp/backup/stackchan-factory-<MAC>-<日付>.bin
idf.py -p /dev/cu.usbmodem101 -b 921600 flash
```

- **書き込み前に Flash 全体（16MB）をバックアップする。** 921600bps で約 3.5 分。戻す時は `esptool.py write_flash 0 <file>`。NVS（Wi-Fi 設定等）を含むのでリポジトリには置かない。[^run-0926]
- `idf.py flash` が書くのは bootloader（0x0）、partition table（0x8000）、otadata（0xd000）、app（0x20000）、assets（0xa00000）。NVS（0x9000）は消さない。[^run-0926]
- 2026-09-26 実績: MAC `XX:XX:XX:XX:XX:XX` の個体でバックアップ（sha256 `1454ad42…`）→ 書き込み、全領域 Hash verified。[^run-0926]

# 4. 起動確認

- 起動するとランチャー画面になる。**XiaoZhi（AI エージェント）は起動時には動かず、ランチャーで AI Agent アプリを開いた時に初めて Wi-Fi 接続と OTA 問い合わせが始まる**。[^run-0926]
- シリアル（115200bps）では、起動時に `MCP: Add tool: self.robot.*` が6件、`HAL-RTC load timezone from nvs: JST-9`、`ota confirm check: partition=ota_0` が出た。[^run-0926]
- 確認ポイント: AI Agent を開き「Hi, Stack-chan」と呼ぶと、シリアルに `WS: Connecting to websocket server: ws://<LAN IP>:8000/xiaozhi/v1/`、xiaozhi-server に `hello` と `tools/list`（11 ツール）が来る。
- 2026-09-26 実績: 上記どおり接続し、日本語で会話、首・LED のツール呼び出しも成功（→ [端末MCPツール](/firmware/device-mcp-tools.md)）。Wi-Fi 設定は工場出荷時の NVS に残っていたものがそのまま使われた。[^run-0926]
- シリアルログの取り方: リセットせずに開くなら pyserial で `dtr=False, rts=False` にしてから `open()`（`idf.py monitor` は TTY が必要）。

# 注意

- Mac の LAN IP が変わると端末が繋がらなくなる。ルーターで DHCP 予約するか、mDNS 名を使うか検討（未検討）。
- `STACKCHAN_SERVER_URL` は変えない（アプリ連携はそのまま）。

[^fw-readme]: StackChan firmware/README.md
[^fw-cmake]: StackChan firmware/CMakeLists.txt
[^kconfig]: StackChan firmware/main/Kconfig.projbuild
[^idf-setup]: ESP-IDF v5.5.4 Linux/macOS setup
[^run-0926]: 2026-09-26 MacBook Air での実行
