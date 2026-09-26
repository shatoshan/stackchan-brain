---
type: Firmware
title: StackChan 公式ファームウェア
description: m5stack/StackChan の firmware の構成・ビルド方法と、組み込まれた XiaoZhi エージェント部分。
tags: [firmware, esp-idf, xiaozhi-esp32, stackchan]
status: stable
stale_after: 2026-12-26T00:00:00Z
generated: { by: claude-code/opus-5.5, at: 2026-09-26T07:00:00Z }
sources:
  - id: stackchan-readme
    resource: https://github.com/m5stack/StackChan/blob/1b5765599fba8aaad1811d9a79358ccc7051f5f3/README.md
    title: m5stack/StackChan README
  - id: fw-readme
    resource: https://github.com/m5stack/StackChan/blob/1b5765599fba8aaad1811d9a79358ccc7051f5f3/firmware/README.md
    title: StackChan firmware/README.md
  - id: repos-json
    resource: https://github.com/m5stack/StackChan/blob/1b5765599fba8aaad1811d9a79358ccc7051f5f3/firmware/repos.json
    title: StackChan firmware/repos.json
  - id: fw-patch
    resource: https://github.com/m5stack/StackChan/blob/1b5765599fba8aaad1811d9a79358ccc7051f5f3/firmware/patches/xiaozhi-esp32.patch
    title: StackChan firmware/patches/xiaozhi-esp32.patch
  - id: fw-cmake
    resource: https://github.com/m5stack/StackChan/blob/1b5765599fba8aaad1811d9a79358ccc7051f5f3/firmware/CMakeLists.txt
    title: StackChan firmware/CMakeLists.txt
  - id: sdk-defaults
    resource: https://github.com/m5stack/StackChan/blob/1b5765599fba8aaad1811d9a79358ccc7051f5f3/firmware/sdkconfig.defaults
    title: StackChan firmware/sdkconfig.defaults
  - id: esp-sr-model
    resource: https://github.com/espressif/esp-sr/blob/master/model/wakenet_model/wn9_histackchan_tts3/_MODEL_INFO_
    title: esp-sr wn9_histackchan_tts3 _MODEL_INFO_（master。StackChan の lock は esp-sr 2.3.1、該当タグは未照合）
  - id: xz-protocol-224
    resource: https://github.com/78/xiaozhi-esp32/blob/v2.2.4/main/protocols/protocol.cc
    title: xiaozhi-esp32 v2.2.4 main/protocols/protocol.cc
  - id: xz-app-224
    resource: https://github.com/78/xiaozhi-esp32/blob/v2.2.4/main/application.cc
    title: 78/xiaozhi-esp32 v2.2.4 main/application.cc
---

# リポジトリ

- https://github.com/m5stack/StackChan に firmware / server / app / remote が同居する。README 自身が「このリポジトリの更新はリリース済みファーム・アプリより遅れることがある」と書いている。[^stackchan-readme]

# ビルド

- ESP-IDF **v5.5.4**。手順は `python3 ./fetch_repos.py` → `idf.py build` → `idf.py flash`（USB 直結）。[^fw-readme]
- M5Burner は公式ビルド済みイメージを書き込む手段で、自前設定（`OTA_URL` 変更）を入れるには自分でビルドする必要がある。
- `firmware/sdkconfig.defaults.local` が存在すると `sdkconfig.defaults` に重ねて適用される（CMakeLists.txt が自動で `SDKCONFIG_DEFAULTS` に追加）。**追跡ファイルを書き換えずに `OTA_URL` を上書きする正規の口**。[^fw-cmake] 手順は [ファーム書き込み](/runbooks/firmware-flash.md)。

# AI エージェント部分

- `78/xiaozhi-esp32` を **v2.2.4** で取得し、`patches/xiaozhi-esp32.patch` を当てて組み込む。[^repos-json]
- パッチ内容（2026-09-26 時点）は主に：アクティベーションコードの音声読み上げを無効化してアプリでのバインドを促す表示に置換、アセット読み込み・I2C デバイス周りの修正。**プロトコル処理（`OnIncomingJson` 等）には手を入れていない**。[^fw-patch]
- ASR / LLM / TTS はすべてサーバー側。端末は Opus 音声を WebSocket（または MQTT+UDP）で送受信するだけ。デフォルトの LLM（Qwen）は XiaoZhi クラウド側で動いている。
- プロトコル選択: OTA 応答に `mqtt` があれば MQTT、`websocket` があれば WebSocket を使う（v2.2.4 `InitializeProtocol`）。[^xz-app-224] 詳細は [XiaoZhi プロトコル](/protocol/xiaozhi-protocol.md)。

# ウェイクワード

- ESP-SR の WakeNet モデル `wn9_histackchan_tts3`（`CONFIG_SR_WN_WN9_HISTACKCHAN_TTS3=y`）。`CONFIG_SEND_WAKE_WORD_DATA=n` なのでウェイクワード音声はサーバーに送らない。[^sdk-defaults]
- モデル情報は `wakenet9_tts3h12_Hi,Stack Chan_3_0.585_0.590`。検出時、端末は `{"type":"listen","state":"detect","text":"<ウェイクワード>"}` を送る。[^esp-sr-model] [^xz-protocol-224]
  - 送られる文字列は `Hi,Stack Chan` と推定（モデル情報からの読み取り。実機ログでは未確認）。サーバー側は句読点・空白を除いて `HiStackChan` で照合する。

[^stackchan-readme]: m5stack/StackChan README
[^sdk-defaults]: StackChan firmware/sdkconfig.defaults
[^esp-sr-model]: esp-sr wn9_histackchan_tts3 _MODEL_INFO_
[^xz-protocol-224]: xiaozhi-esp32 v2.2.4 protocol.cc
[^fw-readme]: StackChan firmware/README.md
[^repos-json]: StackChan firmware/repos.json
[^fw-patch]: StackChan firmware/patches/xiaozhi-esp32.patch
[^fw-cmake]: StackChan firmware/CMakeLists.txt
[^xz-app-224]: xiaozhi-esp32 v2.2.4 application.cc
