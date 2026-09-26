---
type: Decision
title: "007: 自律発話は brain の WebSocket 中継で届ける"
description: xiaozhi-server に発話押し込み API が無いため、brain を端末と xiaozhi-server の間の WebSocket 中継にして発話を注入する。
tags: [decision, adr]
status: stable
generated: { by: claude-code/opus-5.5, at: 2026-09-26T08:00:00Z }
sources:
  - id: approval
    resource: process:chat-2026-09-26
    title: 2026-09-26 のユーザー承認（「007は推奨方針で確定」）
    author: human:shingo
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

> **決定（2026-09-26、human:shingo が推奨案 A を承認）。** 下記「検証が必要な前提」は M3 の実装で確認し、結果をこの概念に追記する。

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

# 決定
**案 A を採用する。**[^approval] brain を端末⇔xiaozhi-server の WebSocket 中継にし、発話は上流への `listen`/`detect` 注入で行う（定型文は `[device_call]` 接頭辞で直接読み上げ、自由生成は通常の LLM 経路）。

# 理由
中継なら stt / tts テキストも全部見えるので、状態ブロブの「直近発話」「最終発話からの秒数」も同時に取れる。

# 実装状況

- 2026-09-26 ステップ1（透過中継と記録）を実装し、実機で会話・ツール呼び出しが中継経由で動くことを確認。→ [brain](/services/brain.md)
- 発見: サーバーが切断すると端末は一度自動で再接続する（→ [XiaoZhi プロトコル](/protocol/xiaozhi-protocol.md)）。
- 2026-09-26 ステップ2（`POST /say` による差し込み）を実装し、実機で verbatim / llm の両方で自分から話しかけられることを確認。→ [brain](/services/brain.md)

# 前提の検証結果（2026-09-26）

| 前提 | 結果 |
|---|---|
| 接続を長時間維持できるか | `close_connection_no_voice_time: 600`（human:shingo の判断で既定値にした）で、無音のまま 649 秒維持され、サーバーのタイムアウトで閉じた。端末からは切れなかった。放置中に環境音で ASR が誤作動することもなかった。バッテリー・発熱は未評価。 |
| idle に落ちた時の扱い | タイムアウトで閉じた後、端末は再接続せず idle。idle の端末には届かないので、次の会話はウェイクワード（またはタッチ）待ち。自律発話は「会話が始まってから無音タイムアウトまで」の窓で行う。 |
| ウェイクワード / 終了コマンドとの誤一致 | verbatim は `[device_call]` 分岐がウェイクワード判定より先なので影響なし。llm は brain が予約語と一致する文を拒否する。 |
| `[device_call]` の副作用 | `incoming_call` フラグは読み込んでいない `call_device` プラグインでしか使われず、影響なし。 |
| 差し込み文の画面表示 | サーバーが返す `stt` を brain で握りつぶす。実機画面に指示文や `[device_call]` が出ないことを human:shingo が確認（2026-09-26）。 |

# 当初挙げた検証項目（M1〜M3）
- 実機のセッション中は `speaking`⇔`listening` を往復し続けることは M2 で確認済み（→ [XiaoZhi プロトコル](/protocol/xiaozhi-protocol.md)）。
- 端末の接続を長時間維持できるか（`close_connection_no_voice_time` を大きくする／端末側のタイムアウト／バッテリー・発熱）。
- 端末が idle に落ちた時の扱い（反射層のタッチ・近接でセッションを開き直すのは端末任せになる）。
- 注入した `listen/detect` がウェイクワード判定（`wakeup_words`）に誤って一致しないこと。

[^approval]: 2026-09-26 のユーザー承認
[^protocol]: XiaoZhi プロトコルの要点
[^srv-listen]: listenMessageHandler.py
[^srv-devcall]: device-call-guide.md
