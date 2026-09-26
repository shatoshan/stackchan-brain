---
type: Runbook
title: 疑似デバイス（実機なしの動作確認）
description: 実機なしで xiaozhi-server と会話を試す方法。テキスト専用の sim/text_client.py と、音声込みの py-xiaozhi。
tags: [runbook, simulator, py-xiaozhi, testing]
status: draft
stale_after: 2026-12-26T00:00:00Z
generated: { by: claude-code/opus-5.5, at: 2026-09-26T08:15:00Z }
sources:
  - id: pyxz
    resource: https://github.com/huangjunsen0406/py-xiaozhi/tree/9bfc807
    title: huangjunsen0406/py-xiaozhi v2.1.2（commit 9bfc807, MIT）
  - id: pyxz-main
    resource: https://github.com/huangjunsen0406/py-xiaozhi/blob/9bfc807/main.py
    title: py-xiaozhi main.py
  - id: pyxz-cfg
    resource: https://github.com/huangjunsen0406/py-xiaozhi/blob/9bfc807/src/utils/config_manager.py
    title: py-xiaozhi src/utils/config_manager.py
  - id: pyxz-ota
    resource: https://github.com/huangjunsen0406/py-xiaozhi/blob/9bfc807/src/activation/ota.py
    title: py-xiaozhi src/activation/ota.py
  - id: pyxz-cli
    resource: https://github.com/huangjunsen0406/py-xiaozhi/blob/9bfc807/src/ui/cli/manager.py
    title: py-xiaozhi src/ui/cli/manager.py
  - id: pyxz-doc
    resource: https://github.com/huangjunsen0406/py-xiaozhi/blob/9bfc807/documents/docs/guide/配置说明.md
    title: py-xiaozhi 配置说明
  - id: dh
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/main/digital-human/README.md
    title: xiaozhi-esp32-server main/digital-human
  - id: srv-ws
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/main/xiaozhi-server/core/websocket_server.py
    title: xiaozhi-esp32-server core/websocket_server.py
---

> `status: draft` の理由: `sim/text_client.py` は動作確認済みだが、py-xiaozhi の手順はソースと文書から書いたもので、まだ実行していない。

# 1. テキスト専用: `sim/text_client.py`（動作確認済み）

- hello → `listen`/`detect` + `text` を 1 発話送り、返ってくる `stt` / `tts` JSON と Opus フレーム数を表示する。音声は再生しない。LLM・TTS まで含めたパイプラインの一往復確認用。
- xiaozhi-server イメージに `websockets` が入っているので、コンテナ内で実行するのが手軽:
  ```bash
  docker compose exec -T xiaozhi-server python - "こんにちは" < sim/text_client.py
  ```
- ホストから実行するなら `pip install websockets` して `python sim/text_client.py --url ws://<LAN IP>:8000/xiaozhi/v1/ "こんにちは"`。
- 送るヘッダ: `Authorization: Bearer test-token`、`Protocol-Version: 1`、`Device-Id`、`Client-Id`。サーバーは `device-id` 必須、auth 無効なら token は見ない。[^srv-ws]

# 2. 音声込み: py-xiaozhi（未実行）

- Python 3.10〜3.12、MIT ライセンス。macOS arm64 用の libopus を同梱（無ければ `brew install opus`）。[^pyxz]
- 導入: `git clone https://github.com/huangjunsen0406/py-xiaozhi && cd py-xiaozhi && uv sync`（GUI を使うなら `uv sync --extra gui`）。[^pyxz]
- 起動: `python main.py --mode cli --protocol websocket`。オプション `--skip-activation` でアクティベーションを飛ばせる。[^pyxz-main]
- 接続先: 設定ファイル `config/config.json` の `SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL` を `http://<LAN IP>:8003/xiaozhi/ota/` に変えるだけ。OTA 応答の `websocket.url` / `token` で `WEBSOCKET_URL` / `WEBSOCKET_ACCESS_TOKEN` が上書きされる（token 空なら `test-token`）。[^pyxz-doc] [^pyxz-ota] [^pyxz-cfg]
  - 設定ファイルの実体は `platformdirs.user_data_dir("py-xiaozhi")/config/config.json`（macOS では `~/Library/Application Support/py-xiaozhi/...` になるはずだが未確認）。`XIAOZHI_DATA_DIR` で変更可。[^pyxz-cfg]
- 自前サーバーの OTA 応答には `activation` キーが無いので、アクティベーション済みとして扱われる。[^pyxz-ota]
- CLI では r / x / q / h 以外の入力はテキストとして `listen`/`detect` で送られる（音声とテキストの両方を試せる）。[^pyxz-cli]

# 3. その他

- xiaozhi-server 同梱の `main/digital-human`（ブラウザのテストページ、ポート 8006）でも OTA URL を入れて会話できる。イメージには含まれないのでリポジトリから別途起動が必要。[^dh]

[^pyxz]: py-xiaozhi README / pyproject.toml
[^pyxz-main]: py-xiaozhi main.py
[^pyxz-cfg]: py-xiaozhi config_manager.py
[^pyxz-ota]: py-xiaozhi ota.py
[^pyxz-cli]: py-xiaozhi cli/manager.py
[^pyxz-doc]: py-xiaozhi 配置说明
[^dh]: main/digital-human
[^srv-ws]: core/websocket_server.py
