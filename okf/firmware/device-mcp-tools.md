---
type: Firmware
title: 端末が公開する MCP ツール
description: StackChan ファームが XiaoZhi の MCP でサーバーに公開しているロボット制御ツールと引数範囲。
tags: [firmware, mcp, servo, led]
status: stable
stale_after: 2026-12-26T00:00:00Z
generated: { by: claude-code/opus-5.5, at: 2026-09-26T07:00:00Z }
verified: { by: human:shingo, at: 2026-09-26T11:10:52Z }
sources:
  - id: hal-mcp
    resource: https://github.com/m5stack/StackChan/blob/1b5765599fba8aaad1811d9a79358ccc7051f5f3/firmware/main/hal/hal_mcp.cpp
    title: StackChan firmware/main/hal/hal_mcp.cpp
  - id: hal-cpp
    resource: https://github.com/m5stack/StackChan/blob/1b5765599fba8aaad1811d9a79358ccc7051f5f3/firmware/main/hal/hal.cpp
    title: StackChan firmware/main/hal/hal.cpp
  - id: m2-0926
    resource: process:claude-code-session-2026-09-26
    title: 2026-09-26 M2 実機試験（MAC XX:XX:XX:XX:XX:XX、App 1.5.1、シリアルログ＋xiaozhi-server ログ）
---

# ツール一覧

| ツール名 | 引数（型・デフォルト・範囲） | 戻り値 / 動作 |
|---|---|---|
| `self.robot.get_head_angles` | なし | `{"yaw": n, "pitch": n}`（度）。ニュートラルは `{0,0}` |
| `self.robot.set_head_angles` | `yaw` int（-128〜128、-128 が左）、`pitch` int（0〜90、90 が上）、`speed` int（100〜1000、デフォルト 150） | `true`。`yaw`/`pitch` 省略時は内部値 -9999 で「動かさない」 |
| `self.robot.set_led_color` | `red`/`green`/`blue` int（0〜168、安全範囲） | 左右のネオンライトを同色に |
| `self.robot.create_reminder` | `duration_seconds` int（1〜86400、デフォルト 60）、`message` string、`repeat` bool | リマインダー ID |
| `self.robot.get_reminders` | なし | リマインダー配列 JSON |
| `self.robot.stop_reminder` | `id` int | `true` |

[^hal-mcp]

# 実機で公開されるツール（2026-09-26 観測）

- 実機は上記6つに加え、xiaozhi-esp32 標準の `self.get_device_status`、`self.audio_speaker.set_volume`、`self.screen.set_brightness`、`self.screen.set_theme`、`self.camera.take_photo` の計 **11 ツール** を `tools/list` で返す（`self.reboot` は `[user]` 専用で LLM には出ない）。[^m2-0926]
- xiaozhi-server 側では `.` が `_` に置き換わった名前（例 `self_robot_set_head_angles`）で LLM に渡る。サーバープラグイン 2 つ（`handle_exit_intent`、`get_lunar`）と合わせて LLM に渡る tools は 13〜14 個。[^m2-0926]

# 実機での呼び出し結果（M2）

| 発話 | LLM の呼び出し | 端末ログ |
|---|---|---|
| 右を向いて | `get_head_angles` → `set_head_angles(yaw=30, pitch=25, speed=150)` | `get_head_angles: {"yaw": -4, "pitch": 25}`、`motion set_angles: yaw: 30, pitch: 25, speed: 150` |
| LEDを青にして | `set_led_color(0, 0, 168)` | `set_led_color: r=0, g=0, b=168` |
| 正面に戻って | `set_head_angles(yaw=0, pitch=25)` | `motion set_angles: yaw: 0, pitch: 25, speed: 150` |

- GPT-6 Luna（`reasoning_effort: none`）は現在角を取得してから相対的に動かし、pitch は維持した。[^m2-0926]
- ツール実行ごとに端末画面へ `% <ツール名>` がユーザー発話として表示される（xiaozhi-server の仕様）。[^m2-0926]
- **yaw の正方向（+30）で物理的に右を向き、`set_led_color(0,0,168)` で LED が青く光ることを人間が目視で確認**（2026-09-26）。

# 使うときの注意

- `set_head_angles` の説明文は「自然な対話では ±45° 以内、70° 超はユーザーが明示的に頼んだときだけ」と LLM に指示している。[^hal-mcp]
- LED は「部屋の照明ではなく本体 LED」と明記。値 168 超は非推奨。[^hal-mcp]
- リマインダー発火時は画面にリマインダー表示＋通知音を鳴らすだけで、**TTS で喋るわけではない**。自律発話の代替にはならない。[^hal-cpp]
- これらはサーバーから MCP（`type: "mcp"` の JSON-RPC）で呼ぶ。セッション（音声チャネル）が開いている時にしか届かない点は [XiaoZhi プロトコル](/protocol/xiaozhi-protocol.md) を参照。

[^hal-mcp]: StackChan firmware/main/hal/hal_mcp.cpp
[^hal-cpp]: StackChan firmware/main/hal/hal.cpp
[^m2-0926]: 2026-09-26 M2 実機試験
