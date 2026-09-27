---
type: Service
title: llm-proxy（xiaozhi-server → Vercel AI Gateway 中継）
description: xiaozhi-server が送れない reasoning_effort を注入し、Gateway の API キーを付与し、本体が差し込む中国語の固定文言を日本語に置換する中継サービス。
tags: [service, proxy, vercel, llm]
status: stable
generated: { by: claude-code/opus-5.5, at: 2026-09-26T07:45:00Z }
sources:
  - id: code
    resource: ../../llm-proxy/proxy.py
    title: llm-proxy/proxy.py
  - id: xz-openai
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/main/xiaozhi-server/core/providers/llm/openai/openai.py
    title: xiaozhi-esp32-server core/providers/llm/openai/openai.py（server_0.9.6 イメージ内でも同一を確認）
  - id: run-0926
    resource: process:claude-code-session-2026-09-26
    title: 2026-09-26 モック上流と実 Gateway（401）での動作確認
---

# なぜ必要か

- xiaozhi-server の `type: openai` プロバイダがリクエストに入れるのは `model`、`messages`、`stream`、`tools`（function call 時）と、設定にある `max_tokens` / `temperature` / `top_p` / `frequency_penalty` だけ。`extra_body` は特定ドメイン（aliyuncs.com 等）の思考無効化にしか使われない。[^xz-openai]
- GPT-6 Luna は Chat Completions で tools を使うのに `reasoning_effort: none` が必須（→ [GPT-6 Luna](/external/openai-gpt-6-luna.md)）。本体改変なしでこれを満たすため、中継で注入する（設計原則1）。
- ついでに Gateway の API キーを中継だけが持つ。xiaozhi-server の設定（`data/.config.yaml`）にはダミーキーしか入らない。

# 動作

- `POST */chat/completions`: JSON に `reasoning_effort` も `reasoning` も無ければ `LLM_REASONING_EFFORT`（既定 `none`）を足す。[^code]
- 全リクエストで `Authorization` を `Bearer $AI_GATEWAY_API_KEY` に差し替え、`https://ai-gateway.vercel.sh` に同じパスで転送。レスポンス（SSE 含む）はチャンク単位でそのまま返す。[^code]
- 本体が会話履歴に差し込む中国語の固定文言（few-shot 例、ウェイクワード時の「嘿，你好呀」）を、`REWRITES` 表に従って **完全一致で** 日本語に置き換える。対象は `messages[].content` と `tool_calls[].function.arguments` 内の文字列値。理由は [xiaozhi-esp32-server](/services/xiaozhi-esp32-server.md) の「中国語の few-shot 注入」。[^code]
  - 文中に埋め込まれる固定指示は部分置換（`SUBSTRING_REWRITES`）。VLLM が画像説明の質問に付ける「(请使用中文回复)」を日本語の指示に置き換える。画像付きメッセージ（content が配列）の文章部分も対象。
  - 本体の文言が変わると一致しなくなり、置換されないだけ（壊れはしない）。イメージを上げたら `rewritten=` のログ件数で確認する。server_0.9.6 では 1 リクエストあたり 8 件。
- **壊れやすさへのガード**: 置換表は `llm-proxy/rewrites.py`（出典ファイル付き）。xiaozhi-server のイメージを上げたら `python3 scripts/check_upstream_strings.py` で、置換対象の文言がイメージ内にまだあるか検査する（無ければ終了コード 1）。実行中も、tools 付きリクエストで few-shot が 5 回連続で見当たらない、few-shot があるのに 1 件も置換されない、画像説明に日本語指示が入っていない、のいずれかで `UPSTREAM CHANGED?` 警告をログに出す（各 1 回）。セッション最初の 1 往復は few-shot が入らないことがあるので、単発では警告しない。
- **英語の独り言の除去**（`llm-proxy/speech_filter.py`、`LLM_PROXY_SPEECH_FILTER=0` で無効）: SSE の本文を文ごとに溜め、日本語を含まない英文（英単語 2 つ以上）か英単語が日本語の文字より多い文が出たら、その文と以降の本文をすべて捨てる。ツール呼び出しと finish_reason は通す。2026-09-27、常時セッションで崩れた発話（「き念がお呂で使うじゃないといよ」）を受けた GPT-6 Luna（`reasoning_effort: none`）が、返答に "a little more natural?"、"Need ask clarify maybe …"、"natural. 1-2 sentences. Japanese. no emoji needed" のような思考メモを混ぜ、それがそのまま読み上げられた。当夜の返答を再生すると「なるほど。お風呂で使うものの話なんだね。」で止まる。「YouTube見てるの？」「iPhone 17 Pro の話？」「LED を青にしたよ」は通す。
- **brain の自発発話ではツールを使わせない**: 最後の user メッセージが brain の指示（「（ロボットから話しかける場面です」で始まる）で tools 付きなら `tool_choice: "none"` を付ける。Gateway 経由の GPT-6 Luna で、`tool_choice: none` なら写真を撮る依頼でもツールを呼ばず文で答えることを確認（2026-09-27）。ログに `(tool_choice=none)` と出る。
- `LLM_PROXY_LOG_BODY=1` でリクエスト本文をログに出す（デバッグ用。会話内容が残るので常用しない）。
- **宛先ゲート**: ユーザー発話で LLM が呼ばれる前に Jev で分類し、LLM を呼ばずに相槌か無応答で返すことがある（→ [宛先ゲート](/design/addressee-gate.md)）。
- **Jev の窓口**: `POST /jev/evaluate`（Vercel 形式）。呼び先は `JEV_BACKEND`（gateway / typesafe）。brain はここを使う。evals 用に `POST /gate/classify`（記録しない）。
- `GET /healthz` はヘルスチェック用。ポートはホストに公開しない（compose ネットワーク内の `http://llm-proxy:8080/v1`）。
- 追加ビルドを避けるため、aiohttp を同梱している xiaozhi-server イメージで `python /opt/llm-proxy/proxy.py` を実行している。**ソースはファイル単位でマウントしているので、`llm-proxy/` に .py を足したら `docker-compose.yml` の volumes にも足す**（忘れると ModuleNotFoundError で再起動を繰り返す。2026-09-27 に 1 分ほど落ちた）。

# 確認済み

- モック上流で: キーの差し替え、`reasoning_effort: none` の注入、SSE が 0.2 秒間隔で逐次届く（バッファされない）こと。[^run-0926]
- 実 Gateway で: xiaozhi-server から `tools=8`、`reasoning_effort=none` のリクエストが中継され、Gateway の 401（ダミーキー）がそのまま xiaozhi-server に返ること。[^run-0926]

[^code]: llm-proxy/proxy.py
[^xz-openai]: core/providers/llm/openai/openai.py
[^run-0926]: 2026-09-26 動作確認
