---
type: Decision
title: "012: 待機が続いたら端末から会話を開く常時セッション"
description: 待機中の端末には brain から届かないため、AI Agent の待機が 10 秒続いたら頭タッチと同じ経路で会話を開くファームパッチを当て、話すか黙るかは brain が決める。
tags: [decision, adr, firmware, proactive]
status: draft
generated: { by: claude-code/opus-5.5, at: 2026-09-27T12:00:00Z }
sources:
  - id: issue
    resource: https://github.com/shatoshan/stackchan-brain/issues/1
    title: "#1 待機中の会話開始: AI Agent 待機中に自動で会話を開く（常時セッション）"
  - id: request
    resource: process:chat-2026-09-27
    title: 2026-09-27 のユーザー指示（「#1 を進めて下さい」「パッチを承認します」）
    author: human:shingo
  - id: xz-app
    resource: https://github.com/78/xiaozhi-esp32/blob/v2.2.4/main/application.cc
    title: xiaozhi-esp32 v2.2.4 application.cc（HandleToggleChatEvent、MAIN_EVENT_ERROR、SendMcpMessage）
  - id: xz-proto
    resource: https://github.com/78/xiaozhi-esp32/blob/v2.2.4/main/protocols/protocol.cc
    title: xiaozhi-esp32 v2.2.4 protocol.cc（SendMcpMessage、IsTimeout 120 秒）
  - id: sc-display
    resource: https://github.com/m5stack/StackChan/blob/1b5765599fba8aaad1811d9a79358ccc7051f5f3/firmware/main/hal/board/stackchan_display.cc
    title: StackChan stackchan_display.cc（頭タッチ → toggle_xiaozhi_chat_state、STANDBY で idle）
  - id: sc-board
    resource: https://github.com/m5stack/StackChan/blob/1b5765599fba8aaad1811d9a79358ccc7051f5f3/firmware/main/hal/board/stackchan.cc
    title: StackChan stackchan.cc（PowerSaveTimer、allowShutdownWhenCharging）
  - id: run-0927
    resource: process:claude-code-session-2026-09-27
    title: 2026-09-27 実機試験（シリアルログ、brain / llm-proxy のログ）
  - id: sc-main
    resource: https://github.com/m5stack/StackChan/blob/1b5765599fba8aaad1811d9a79358ccc7051f5f3/firmware/main/main.cpp
    title: StackChan main.cpp（startAiAgentOnBoot）
---

> **決定（2026-09-27、human:shingo がパッチを承認）。** brain 側の受け口とパッチ 0003 は実装・ビルド済み。実機での長時間試験が済むまで draft のままにする。[^request]

# 背景

- WebSocket モードの端末は、待機中はサーバーに繋がっていない。brain から自分で話しかけられるのは、誰かがウェイクワードかタッチで一度会話を開いた後だけ（[決定 007](/decisions/007-proactive-speech-path.md)）。[^issue]
- 近接センサで会話を開く案（[決定 009](/decisions/009-firmware-proximity-wake.md)）はセンサが使えず不採用。IMU・照度や端末側 VAD の案も、きっかけを端末の弱いセンサに頼る点は同じ。開いた後の判断はどのみちサーバー側（カメラ・ASR・Jev）が担う。[^issue]
- 常に音声が流れる弱点は、[宛先ゲート](/design/addressee-gate.md)（人同士の会話やテレビには返事しない）で吸収できるようになった。

# ファームで確認したこと（2026-09-27、コミット固定のソース）

- **頭タッチ**は `hal_bridge::toggle_xiaozhi_chat_state()` → `Application::ToggleChatState()`。待機中なら会話を開き、聞き取り中なら閉じる。会話を開く時にポップ音は鳴らない（鳴るのはウェイクワードの経路だけ）。[^sc-display] [^xz-app]
- `hal_bridge::is_xiaozhi_idle()` は画面の状態表示（STANDBY）から立つフラグ。パッチでは `Application::GetDeviceState() == kDeviceStateIdle` を直接見る。[^sc-display]
- **会話を開けないと警告音が鳴る**: `OpenAudioChannel` が失敗すると `MAIN_EVENT_ERROR` → `Alert(..., OGG_EXCLAMATION)`。サーバーが落ちている時に一定間隔で開き直すと、そのたびに鳴る。→ 失敗したら間隔を延ばす。[^xz-app]
- `Application::SendMcpMessage(payload)` は公開 API で、`{"session_id":…,"type":"mcp","payload":…}` として送る。xiaozhi-esp32 部分を変えずに、端末からサーバーへ目印を送れる。[^xz-proto]
- 省電力タイマー（スリープ・電源オフ）は、USB 給電中は `allowShutdownWhenCharging=false`（既定）なら無効。[決定 011](/decisions/011-usb-powered.md) の USB 給電前提なら、待機中に電源が切れることはない。[^sc-board]
- 電源投入から AI Agent を直接起動する設定（`startAiAgentOnBoot`、NVS キー `boot_ai`）が公式の設定画面にある。パッチと組み合わせれば、電源を入れるだけで繋がる。[^sc-main]

# 決定

- **パッチ `0003-always-on-session.patch`**（原則2の例外の範囲: 新規ファイル 1 つ、`hal.cpp` に呼び出し 2 行、xiaozhi-esp32 部分は無変更）
  - `main/hal/hal_always_on.cpp` を追加し、`Hal::startXiaozhi()` の `start_xiaozhi_app()` より前に起動する（決定 009 と同じ落とし穴）。
  - 待機（`kDeviceStateIdle`）が 10 秒続いたら `toggle_xiaozhi_chat_state()` で会話を開く。
  - 15 秒以内に聞き取り（`kDeviceStateListening`）に入れば、MCP 通知 `notifications/stackchan_brain/auto_open` を送る。入れなければ次の試行を 30 秒後にし、失敗のたびに倍にする（最大 10 分）。警告音が鳴り続けるのを防ぐため。
- **brain**（実装済み）
  - 中継は上記の MCP 通知を xiaozhi-server に流さずに受け取り、そのセッションを「自動で開いた」とする。
  - 自動で開いたセッションは**休止から始める**。人が話すか、カメラに顔が新しく映るまでは話しかけない。人が開いたセッションだけが、従来どおり `just_woken_no_talk`（起こされたのに黙っている）の対象になる。
  - 「**終了**」の意味は「しばらく黙る」: 最後のユーザー発話が `終了` / `おしまい` でサーバーが閉じた場合、次のセッション（10 秒後に自動で開き直す）でも 30 分（`BRAIN_QUIET_AFTER_EXIT`）は顔が映っただけでは話しかけない。人が話せば再開する。
- 常時セッションをやめたい時は、ホームのインジケータでランチャーに戻る（AI Agent 以外ではパッチは動かない）。

# 帰結・懸念

- マイク音声が常時サーバー（LAN 内のローカル ASR）に流れる。認識テキストは宛先ゲートの Jev に送られ、ロボット宛てのものは LLM に送られる（[決定 003](/decisions/003-lan-only.md)）。
- 聞き取り中は LED が点き、端末の待機モーション（`idleRandomMovementLevel`）は止まる。代わりに brain のよそ見が動く。
- 在席確認の撮影が、休止中は 15 秒ごとに一日中続く（シャッター音は [決定 010](/decisions/010-firmware-silent-shutter.md) で消してある）。
- 無音タイムアウト（`XIAOZHI_NO_VOICE_CLOSE_SEC`、600 秒）のたびにセッションが閉じて開き直す。そのたびに xiaozhi-server 側の会話履歴は消える（会話の記憶は #5）。
- 頭タッチは「会話を閉じる」になり、10 秒後に自動で開き直す。
- [#7](https://github.com/shatoshan/stackchan-brain/issues/7)（切断後に一度だけ再接続する挙動）は、パッチを入れると常に開き直すので重要度が下がる。

# 実機試験（2026-09-27、短時間）

- 書き込み後に AI Agent を開くと、`HAL-AlwaysOn ready` から 10 秒で `idle for 10051ms, opening chat` → connecting → listening。brain が目印を受け取り `opened automatically` を記録。[^run-0927]
- 自動で開いたセッションは休止から始まり、その後カメラに顔が映って `person_arrived` で「おかえり」と話しかけた。家族同士の会話（「お風呂行ってくるのかい」など）は宛先ゲートが止め、判定は `person_left_or_busy` で黙った。[^run-0927]
- **見つかった問題と対処**: 開いた時点から目の前にいた人も「新しく映った」扱いになった。無音タイムアウトで開き直すたびに「おかえり」と言ってしまうので、brain は端末ごとに顔が見え続けている記録を持ち、直前のセッションの最後に顔が見えてから 90 秒以内（`BRAIN_FACE_CARRY_SECONDS`）なら次のセッションに引き継ぐようにした。電源投入後に初めて開いた時は前の記録が無いので、今も話しかける。
- 長時間試験（誤反応、Wi-Fi 断、無音タイムアウトでの開き直し）は未実施。

# 未確定

- ビルド: パッチを当てて `idf.py reconfigure && idf.py build` が通る（2026-09-27、`stack-chan.bin` 0x39a870）。
- 待機から開くまでの 10 秒、失敗時の待ち（30 秒〜10 分）は仮の値。
- 長時間の実測: 誤反応、Wi-Fi 断からの復帰、`IsTimeout`（120 秒間サーバーから何も届かないと、端末は会話が閉じたとみなす）との関係。[^xz-proto]

[^issue]: #1 待機中の会話開始
[^xz-app]: xiaozhi-esp32 v2.2.4 application.cc
[^xz-proto]: xiaozhi-esp32 v2.2.4 protocol.cc
[^sc-display]: StackChan stackchan_display.cc
[^sc-board]: StackChan stackchan.cc
[^sc-main]: StackChan main.cpp
[^request]: 2026-09-27 のユーザー指示
[^run-0927]: 2026-09-27 実機試験
