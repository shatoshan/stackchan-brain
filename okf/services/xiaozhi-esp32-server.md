---
type: Service
title: xiaozhi-esp32-server（最小構成）
description: 採用した XiaoZhi 互換サーバー。最小構成（Python 単体、Java 管理 API なし）の起動方法・設定形式・LLM/ASR/TTS の設定キー。
tags: [service, xiaozhi, docker, asr, tts, llm]
resource: https://github.com/xinnan-tech/xiaozhi-esp32-server
status: stable
stale_after: 2026-12-26T00:00:00Z
generated: { by: claude-code/opus-5.5, at: 2026-09-26T07:30:00Z }
sources:
  - id: readme
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/README.md
    title: xiaozhi-esp32-server README（commit 788f530, 2026-09-21）
    author: org:xinnan-tech
    last_modified: 2026-09-21T01:38:29Z
  - id: deploy
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/docs/Deployment.md
    title: docs/Deployment.md（最简化安装）
  - id: compose
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/main/xiaozhi-server/docker-compose.yml
    title: main/xiaozhi-server/docker-compose.yml
  - id: config
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/main/xiaozhi-server/config.yaml
    title: main/xiaozhi-server/config.yaml
  - id: loader
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/main/xiaozhi-server/config/config_loader.py
    title: config/config_loader.py
  - id: openai-llm
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/main/xiaozhi-server/core/providers/llm/openai/openai.py
    title: core/providers/llm/openai/openai.py
  - id: http-server
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/main/xiaozhi-server/core/http_server.py
    title: core/http_server.py
  - id: ota
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/main/xiaozhi-server/core/api/ota_handler.py
    title: core/api/ota_handler.py
  - id: ci
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/.github/workflows/docker-image.yml
    title: .github/workflows/docker-image.yml
  - id: ghcr
    resource: ghcr.io/xinnan-tech/xiaozhi-esp32-server:server_0.9.6（docker buildx imagetools inspect, 2026-09-26）
    title: GHCR image index
  - id: prompt-mgr
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/main/xiaozhi-server/core/utils/prompt_manager.py
    title: core/utils/prompt_manager.py（server_0.9.6 イメージ内で確認）
  - id: ctx
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/docs/context-provider-integration.md
    title: docs/context-provider-integration.md
---

# 位置づけ

- 採用理由は [決定 002](/decisions/002-self-hosted-xiaozhi-server.md)。本体は改変せず、公式 Docker イメージに依存する（設計原則1）。
- **README が「機能未完成、ネットワークセキュリティ評価未了、本番環境で使うな」と明記** → LAN 内で閉じる（[決定 003](/decisions/003-lan-only.md)）。[^readme]
- パイプライン: VAD（SileroVAD ローカル）→ ASR → LLM → TTS。Intent / Memory / VLLM / プラグイン / MCP 接続点は差し込み口。[^readme] [^config]

# デプロイ形態と要求スペック

| 形態 | 中身 | 要求 |
|---|---|---|
| 最简化安装（**採用**） | Python server のみ。設定はファイル、DB なし | FunASR 使用時 2コア4GB、全 API なら 2コア2GB |
| 全模块安装 | + Java manager-api + Web 智控台 + DB | FunASR 使用時 4コア8GB、全 API なら 2コア4GB |

[^readme]

# Docker イメージ

- `ghcr.io/xinnan-tech/xiaozhi-esp32-server:server_<version>` / `server_latest`。最新リリースは **v0.9.6（2026-07-24）**。
- **arm64 も提供されている**。Deployment.md には「0.8.2 以降は x86 のみ、arm64 は自前ビルド」とあるが、これは古い記述。CI（docker-image.yml）は `linux/amd64,linux/arm64` でビルドしており、GHCR の `server_0.9.6` / `server_latest` のマニフェストにも `linux/arm64` がある。[^deploy] [^ci] [^ghcr]
- 本リポジトリは `server_0.9.6` に固定。キー名はこのイメージ内の `config.yaml` でも同一であることを確認済み。
- 公式 compose はミラー `ghcr.nju.edu.cn` を使うが、中国国外では `ghcr.io` を直接使えばよい。
- イメージは約 3GB（arm64、展開後）。

# 起動に必要なファイル（最小構成）

公式 compose が要求するマウント:[^compose]

| ホスト | コンテナ | 用途 |
|---|---|---|
| `./data` | `/opt/xiaozhi-esp32-server/data` | `.config.yaml`（上書き設定）ほか |
| `./models/SenseVoiceSmall/model.pt` | `/opt/xiaozhi-esp32-server/models/SenseVoiceSmall/model.pt` | FunASR 用モデル（約 892MB、イメージに同梱されない） |

- モデル取得元: `https://modelscope.cn/models/iic/SenseVoiceSmall/resolve/master/model.pt`[^deploy]
- ポート: **8000**（WebSocket、パス `/xiaozhi/v1/`）、**8003**（HTTP：OTA と視覚解析）。[^compose] [^config]
- 起動成功ログには `OTA接口是 http://…:8003/xiaozhi/ota/` と `Websocket地址是 ws://…:8000/xiaozhi/v1/` が出る。Docker ではコンテナ内 IP が出るので信用せず、ホストの LAN IP で読み替える。[^deploy]

# 設定ファイルの仕組み

- 本体同梱の `config.yaml` に、`data/.config.yaml` を**再帰的に deep merge** する（dict 同士はキー単位でマージ、それ以外は上書き）。最小限のキーだけ書けばよい。[^loader]
- `.config.yaml` に `manager-api.url` があると全モジュール（API 取得）モードになる。最小構成では書かない。[^loader]
- **環境変数展開の仕組みは無い**（config_loader に `os.environ` 参照なし）。秘密情報を `.env` に置くため、本リポジトリではテンプレートを起動時に展開している（→ [起動手順](/runbooks/server-startup.md)）。[^loader]

# 主要設定キー

| キー | デフォルト | 意味 |
|---|---|---|
| `server.ip` / `server.port` / `server.http_port` | `0.0.0.0` / 8000 / 8003 | 待ち受け |
| `server.websocket` | `ws://你的ip或者域名:端口号/xiaozhi/v1/` | OTA が端末に返す WS URL。「你」を含むと自動生成（Docker では不正確）。**LAN IP を明示する** |
| `server.vision_explain` | 同上 | 視覚解析 URL |
| `server.timezone_offset` | `+8` | OTA 応答の時刻オフセット。日本は `+9` |
| `server.auth.enabled` | `false` | 認証。有効時は OTA がトークンを発行 |
| `server.mqtt_gateway` | `null` | 設定すると OTA が MQTT 設定を返す |
| `close_connection_no_voice_time` | 120 | 無音で切断するまでの秒 |
| `enable_greeting` | true | ウェイクワードに挨拶を返すか |
| `wakeup_words` | 中国語のリスト | テキスト入力がこれに一致するとウェイクワード扱い |
| `prompt` | 台湾の女の子キャラ | システムプロンプト（`agent-base-prompt.txt` テンプレートに埋め込まれる） |
| `mcp_endpoint` | プレースホルダ | MCP 接続点の WS URL |
| `context_providers` | `[{url: ""}]` | ウェイク時に GET して `{{ dynamic_context }}` に注入する HTTP API。応答は `{"code":0,"data":{...}}`[^ctx] |
| `selected_module.{VAD,ASR,LLM,VLLM,TTS,Memory,Intent}` | SileroVAD / FunASR / ChatGLMLLM / ChatGLMVLLM / EdgeTTS / nomem / function_call | 使うモジュール名（下のセクションのキー名を指す） |

[^config]

## ASR（FunASR ローカル）

```yaml
ASR:
  FunASR:
    type: fun_local
    model_dir: models/SenseVoiceSmall
    output_dir: tmp/
    language: auto   # SenseVoice は zh, en, ja, ko, yue に対応。日本語固定なら ja
```
[^config]

## TTS（EdgeTTS）

```yaml
TTS:
  EdgeTTS:
    type: edge
    voice: zh-CN-XiaoxiaoNeural   # 日本語なら ja-JP-NanamiNeural（2026-09-26 に動作確認）
    output_dir: tmp/
    # language: "中文"
```
[^config]

- 選択中 TTS の `language` がシステムプロンプトテンプレート（`agent-base-prompt.txt`）の `{{language}}` に入り、「必ずこの言語で答えよ」と LLM に指示する。未設定だと「中文」。日本語で使うなら必ず設定する。[^prompt-mgr]

## LLM（OpenAI 互換）

- `type: openai` のプロバイダは `model_name`、`api_key`、`base_url`（無ければ `url`）、任意で `temperature`、`max_tokens`、`top_p`、`frequency_penalty`、`timeout` を読む。値が無いパラメータはリクエストに入れない。常に `stream: True`。[^openai-llm]
- 上記以外のパラメータ（`reasoning_effort` など）を送る設定は無い。`extra_body` は `THINKING_DISABLED_DOMAINS`（aliyuncs.com、deepseek.com 等）に一致するドメインの思考無効化にしか使われない。[^openai-llm]
- `selected_module.LLM` に新しいキー名（本リポジトリでは `GatewayLLM`）を指定し、`LLM:` 配下に同名で定義すれば既存定義と干渉しない。現在は [llm-proxy](/services/llm-proxy.md) 経由で [GPT-6 Luna](/external/openai-gpt-6-luna.md) を呼んでいる。

# OTA エンドポイント（§9 未確認事項 → 確認済み）

- **提供している。** 最小構成（`read_config_from_api` が偽）の時だけ、HTTP サーバーが `GET/POST /xiaozhi/ota/` と `/xiaozhi/ota/download/{filename}` を追加する。[^http-server]
- POST 応答には `server_time`、`firmware`、そして `mqtt_gateway` 未設定なら `websocket: {url, token}` が入る（`token` は auth 無効時は空文字）。[^ota]
- ⇒ **端末側の変更は `OTA_URL` を `http://<LAN IP>:8003/xiaozhi/ota/` にするだけで済む**（[Kconfig](/firmware/kconfig.md)）。
- `data/bin/*.bin` に置いたファームを OTA で配る機能もあるが使わない。

# サーバー主導の発話（§9 未確認事項 → 確認済み：外部 API なし）

- HTTP ルートは OTA と `/mcp/vision/explain` だけで、**外部から「この文を喋れ」と押し込む API は無い**。[^http-server]
- 詳細と選択肢は [XiaoZhi プロトコル](/protocol/xiaozhi-protocol.md) と [決定 007](/decisions/007-proactive-speech-path.md)。

[^readme]: xiaozhi-esp32-server README
[^deploy]: docs/Deployment.md
[^compose]: main/xiaozhi-server/docker-compose.yml
[^config]: main/xiaozhi-server/config.yaml
[^loader]: config/config_loader.py
[^openai-llm]: core/providers/llm/openai/openai.py
[^http-server]: core/http_server.py
[^ota]: core/api/ota_handler.py
[^ci]: .github/workflows/docker-image.yml
[^ghcr]: GHCR image index
[^ctx]: docs/context-provider-integration.md
[^prompt-mgr]: core/utils/prompt_manager.py
