---
type: Service
title: brain（端末 ⇔ xiaozhi-server の WebSocket 中継と自律発話）
description: 端末の WebSocket セッションを xiaozhi-server へ中継して会話を記録し、判定ループ（Jev）と操作 API から発話を差し込む。
tags: [service, brain, relay, websocket]
status: stable
generated: { by: claude-code/opus-5.5, at: 2026-09-26T11:21:01Z }
sources:
  - id: code
    resource: ../../brain/relay.py
    title: brain/relay.py
  - id: decision
    resource: /decisions/007-proactive-speech-path.md
    title: 決定 007
  - id: m3-relay
    resource: process:claude-code-session-2026-09-26
    title: 2026-09-26 M3 ステップ1（中継）の疑似デバイス・実機試験
  - id: m3-inject
    resource: process:claude-code-session-2026-09-26
    title: 2026-09-26 M3 ステップ2 差し込み試験（疑似デバイス・実機）
---

# 役割

- [決定 007](/decisions/007-proactive-speech-path.md) の案 A。xiaozhi-server の `server.websocket` を brain（`ws://<LAN IP>:8010/xiaozhi/v1/`）に向けると、端末は OTA 経由で brain に繋ぎ、brain が `ws://xiaozhi-server:8000/xiaozhi/v1/` へ中継する。[^code]
- ステップ1で透過中継と記録、ステップ2で発話の差し込み（操作 API）、ステップ3で判定ループ（`brain/judge.py`）を実装。

# 動作

- 端末の `Authorization` / `Protocol-Version` / `Device-Id` / `Client-Id` ヘッダとクエリ文字列を上流へ引き継ぐ。テキストもバイナリ（Opus）もそのまま双方向に流す。[^code]
- 片側が閉じたらもう片側も閉じる。どちらが先に閉じたか（`device` / `server`）を記録する。[^code]
- セッションごとに `data/brain/sessions/<日時>-<MAC>-<id>.jsonl` へ JSON メッセージを 1 行ずつ記録（`{"t", "dir": "up"|"down"|"meta", "msg"}`）。2000 文字を超えるもの（`tools/list` の結果など）は型と長さだけ。音声は記録しない。[^code]
- 標準ログには発話（`user:`）、返答（`robot:`）、ツール呼び出し、hello / listen / abort を要約して出す。[^code]
- ポート 8010 は LAN に公開する（端末が直接繋ぐため）。`GET /healthz` でヘルスチェック。

# 発話の差し込み（操作 API、ポート 8011）

- ホストの `127.0.0.1:8011` にだけ公開（LAN からは使えない）。[^code]
- `GET /sessions`: 中継中のセッション一覧。`state`（connecting / listening / speaking / idle）、`since_user_s`、`since_robot_s`、`injections` を返す。
- `POST /say` `{"text", "mode", "device_id"?}`: 聞き取り中のセッション（`device_id` 省略時は最後に動いたもの）の上流へ `listen`/`detect` を送る。
  - `mode: "verbatim"`: `[device_call]` 接頭辞付き。xiaozhi-server は LLM を通さずそのまま TTS し、会話履歴に assistant 発話として残す。
  - `mode: "llm"`: text をユーザー発話として渡し、LLM が返答を生成する（履歴には user として残る）。`wakeup_words` / `exit_commands` と一致する文は拒否（`BRAIN_RESERVED_WORDS`）。
  - 状態が `listening` でない、ロボット発話終了から 1.5 秒以内、ユーザー発話から 3 秒以内なら 409 で拒否（`BRAIN_MIN_GAP_AFTER_ROBOT` / `BRAIN_MIN_GAP_AFTER_USER`）。
- 差し込んだ文についてサーバーが返す `stt` は端末に流さない（画面の「ユーザー発話」欄に指示文が出るのを防ぐ）。サーバーは `stt` の句読点を一部落とすので、句読点・空白を除いて照合する。[^code]
- 状態の推定: 上り `listen start` → listening、下り `tts start` → speaking、`tts stop` → listening。`stt` のうち `% ` で始まるもの（ツール実行表示）はユーザー発話に数えない。

```bash
curl -s 127.0.0.1:8011/sessions
curl -s -X POST 127.0.0.1:8011/say -d '{"text":"ねえねえ、今日はいい天気だね。"}'
curl -s -X POST 127.0.0.1:8011/say -d '{"mode":"llm","text":"（ロボットから話しかける場面です。…を短く聞いてください）"}'
```

# 判定ループ（`brain/judge.py`）

- 5 秒ごとに中継中のセッションを見て、ルールで絞ってから Jev（`/v1/evaluate`、llm-proxy 経由なので brain はキーを持たない）に判定させ、話すなら表情を送ってから `/say` と同じ処理で差し込む。質問と閾値は [直感層の質問設計](/design/jev-questions.md)。
- Jev が 429 / エラーなら 60 秒から最大 10 分まで倍々で Jev を止め、その間は LLM（`LLM_MODEL`）に同じ分類を JSON で答えさせる。LLM 判定は 1 台あたり 30 秒に 1 回まで。
- 判定はすべて `data/brain/judgments/YYYYMMDD.jsonl` に記録（状態ブロブ、閾値、答え、Jev の生の確率、行動）。evals の素材にする。
- 機嫌（0〜1、初期 0.6）は、自発発話に返事があれば +0.1、なければ −0.1。
- 表情は判定結果を `{"type":"llm","emotion":...}` として brain から端末へ直接送る。
- `BRAIN_JUDGE_ENABLED=0` で止められる。閾値・間隔などは `BRAIN_*` 環境変数（`judge.py` 冒頭）。

# 実測（2026-09-26）

- 実機: AI Agent を開き直すと OTA で新しい URL を受け取り、brain 経由で接続した。「左を向いて」→ `get_head_angles` → `set_head_angles(yaw=-40, pitch=14)` を含め、会話もツール呼び出しも中継前と同様に動いた。[^m3-relay]
- 遅延: 発話の認識結果（`stt`）から最初の返答文まで約 1.6 秒で、中継前と体感差なし。[^m3-relay]
- 差し込み（実機）: verbatim は差し込みから約 0.5 秒で読み上げ開始。差し込んだ文を踏まえてユーザーとの会話が続いた（「ぼく、自分から話しかけられるようになったよ」→「マじか？」→「ほんとだよ…」）。llm モードの指示「今日の予定を一つ短く聞いて」には「今日の予定、ひとつ聞いてもいい？」と許可を求める形で返った（指示文の書き方の課題）。[^m3-inject]
- 疑似デバイスで、発話中の連続差し込みが 409（device is speaking）、予約語が 409 になることを確認。[^m3-inject]

[^code]: brain/relay.py
[^decision]: 決定 007
[^m3-relay]: 2026-09-26 M3 ステップ1 試験
[^m3-inject]: 2026-09-26 M3 ステップ2 差し込み試験
