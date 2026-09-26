---
type: Decision
title: "007（ドラフト）: 自律発話を端末に届ける経路"
description: xiaozhi-server に発話押し込み API が無いことを受けた、自律発話の実装経路の候補と推奨。未決定。
tags: [decision, adr]
status: draft
generated: { by: claude-code/opus-5.5, at: 2026-09-26T08:00:00Z }
sources:
  - id: kickoff
    resource: ../../docs/KICKOFF.md
    title: stackchan-brain キックオフ指示書（human:shingo 作成）
    author: human:shingo
  - id: protocol
    resource: /protocol/xiaozhi-protocol.md
    title: XiaoZhi プロトコルの要点（本バンドル）
  - id: srv-listen
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/main/xiaozhi-server/core/handle/textHandler/listenMessageHandler.py
    title: xiaozhi-esp32-server listenMessageHandler.py
  - id: srv-devcall
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/docs/device-call-guide.md
    title: xiaozhi-esp32-server docs/device-call-guide.md
---

> **未決定。** 人間の判断待ち。実装前に M1〜M3 で検証が必要な前提を含む。

# 背景（2026-09-26 確認）
1. xiaozhi-esp32-server には外部から「この文を喋れ」と押し込む API が無い（HTTP は OTA と視覚解析のみ）。→ [xiaozhi-esp32-server](/services/xiaozhi-esp32-server.md)
2. WebSocket モードの端末は、ウェイクワード・ボタン・タッチの時だけ接続する。idle 中の端末にサーバーから届く経路は無い。[^protocol]
3. 接続中（Listening / Speaking）なら、サーバーが `tts start` → Opus → `tts stop` を送れば端末は喋る。[^protocol]
4. サーバーは接続中クライアントからの `listen`/`detect` + `text` を受けると LLM→TTS を走らせる。`[device_call]` 接頭辞付きなら LLM を通さずそのテキストを直接 TTS する。[^srv-listen]
5. MQTT+リモートウェイクでの会話開始は、ファームに MCP ツールを追加する改造が前提。[^srv-devcall]

# 候補

| 案 | 内容 | 原則との整合 | 課題 |
|---|---|---|---|
| **A. brain を WebSocket 中継にする**（推奨） | OTA が返す `server.websocket` を brain に向け、brain が端末⇔xiaozhi-server を透過中継。発話したい時は brain が上流へ `listen/detect` を注入（`[device_call]` 付きで定型文そのまま、無しで LLM 生成） | 本体改変なし・ファーム改変なし | 端末が接続中である必要がある（常時セッション化の可否を検証）。`[device_call]` 分岐の副作用（`incoming_call` フラグ）の確認 |
| B. MQTT ゲートウェイ＋リモートウェイク | 公式の設備呼叫の仕組みを流用 | **ファーム改変が必要**（原則2違反） | 全モジュール構成（Java・DB）も必要 |
| C. xiaozhi-server にプラグイン / パッチ | サーバー内部から TTS キューに投入 | パッチは原則1違反。プラグインは LLM の function call からしか呼ばれない | |
| D. brain が XiaoZhi プロトコルを全部喋る | xiaozhi-server を置き換える | 原則1の前提（本体に依存）を捨てる | 実装量が大きい |

# 疑似デバイスでの観測（2026-09-26、`sim/text_client.py`）
- `listen/detect` に `[device_call]おはよう、今日もいい天気だね` を送ると、LLM を呼ばずに `stt` → `tts start` → 2文の `sentence_start` → `tts stop` と Opus 71 フレームが返った。**定型文の直接読み上げ経路として機能する。**
- ただしサーバーは同じ文を `stt` としても返すため、実機では画面に「ユーザー発話」として表示される（ファーム v2.2.4 の `stt` 処理）。中継側で上流からの `stt` を握りつぶせば回避できる見込み（未検証）。

# 推奨
案 A。中継なら stt / tts テキストも全部見えるので、状態ブロブの「直近発話」「最終発話からの秒数」も同時に取れる。

# 検証が必要な前提（M1〜M3）
- 端末の接続を長時間維持できるか（`close_connection_no_voice_time` を大きくする／端末側のタイムアウト／バッテリー・発熱）。
- 端末が idle に落ちた時の扱い（反射層のタッチ・近接でセッションを開き直すのは端末任せになる）。
- 注入した `listen/detect` がウェイクワード判定（`wakeup_words`）に誤って一致しないこと。

[^protocol]: XiaoZhi プロトコルの要点
[^srv-listen]: listenMessageHandler.py
[^srv-devcall]: device-call-guide.md
