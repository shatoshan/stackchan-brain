# stackchan-brain

M5Stack 製 StackChan（CoreS3）を、自律的に話しかけてくる会話ロボットにするためのサーバー側の頭脳。
ファームは極力改変せず、xiaozhi-esp32-server と brain を Docker で動かす（まず MacBook Air、将来 Pi 5 / N100）。
LLM（GPT-6 Luna）と Jev はすべて Vercel AI Gateway 経由で、キーは `AI_GATEWAY_API_KEY` の 1 本。

## 知識の入口

- **事実（ハード・プロトコル・外部 API・設定キー・決定記録）はすべて `okf/` にある。まず `okf/index.md` を読み、そこから辿る。**
- `okf/` を読み書きする時は `okf` スキル（`.claude/skills/okf/SKILL.md`）のルールに従う。
- `docs/` は自由形式（キックオフ指示書 `docs/KICKOFF.md` など）。事実の正は `okf/` 側。

## 設計原則

1. **xiaozhi-esp32-server 本体は改変しない。** 差し込み口（LLM プロバイダ設定・MCP 接続点・プラグイン・context_providers）だけを使い、本体は公式 Docker イメージとして依存する。
2. **端末ファームは `OTA_URL`（必要なら `STACKCHAN_SERVER_URL`）の変更以外いじらない。** 変更は `firmware/sdkconfig.defaults.local` で行う。
3. **option-quants とは MCP 契約のみで連携する。** コード依存ゼロ。
4. **反射（端末）／直感（Jev）／熟考（LLM = GPT-6 Luna）の3層を守る。** Jev に生成させない。LLM を毎秒呼ばない。
5. **LAN 内で閉じる。** インターネット露出・TLS・認証はスコープ外。ポート転送しない。
6. **秘密情報は `.env` のみ。** キーを増やしたら `.env.example` も同期する。`data/`（生成された設定にキーが入る）と `models/` はコミットしない。
7. **不明な API 仕様・設定キー名は一次情報（公式リポジトリのソース・公式ドキュメント）で確認する。** 推測で設定ファイルを書かない。
8. **知識は `okf/` に書く。** 事実を知ったら概念ファイルに `sources` 付きで追記し、`okf/log.md` を更新する。未確認は `status: draft`。`verified` は付けない（人間が付ける）。`okf/` と実装が食い違ったら勝手に直さず報告する。

## リポジトリ構成

| パス | 内容 |
|---|---|
| `docker-compose.yml` | xiaozhi-server（公式イメージ `server_0.9.6`）＋ llm-proxy ＋ brain。mcp-bridge は M4 で追加 |
| `llm-proxy/` | xiaozhi-server → Vercel AI Gateway 中継（`reasoning_effort` 注入とキー付与） |
| `config/xiaozhi/` | xiaozhi-server 上書き設定テンプレートと、起動時に `.env` で展開するスクリプト |
| `brain/` | 端末 ⇔ xiaozhi-server の WebSocket 中継（8010）、発話差し込み API（127.0.0.1:8011）、Jev 判定ループ |
| `mcp/` | MCP 接続点に繋ぐ MCP サーバー（option-quants、天気等。M4〜） |
| `sim/` | 疑似デバイス（`text_client.py`） |
| `evals/` | 状態ブロブ→Jev 判定の記録と再生（M3〜） |
| `okf/` | OKF v0.2 知識バンドル |

## コマンド

```bash
cp .env.example .env                  # 初回。SERVER_LAN_IP と AI_GATEWAY_API_KEY を書く
docker compose up -d                  # 起動（設定を変えたら --force-recreate）
docker compose ps                     # healthy を確認
docker logs -f brain                  # 会話の要約ログ（user / robot / tool call）
docker logs -f xiaozhi-esp32-server   # サーバーの詳細ログ（LLM の上流エラーは docker logs llm-proxy）
curl http://<LAN IP>:8003/xiaozhi/ota/                                   # OTA 確認
docker compose exec -T xiaozhi-server python - --url ws://brain:8010/xiaozhi/v1/ "こんにちは" < sim/text_client.py   # 実機と同じ経路で一往復
curl -s 127.0.0.1:8011/sessions       # brain の中継中セッション（/say で発話を差し込める）
docker compose exec -T brain python /evals/run.py   # 直感層の回帰テスト（--llm-only で Jev を使わない）
docker compose down
```

初回は ASR モデル（約 900MB）の取得が必要。手順は `okf/runbooks/server-startup.md`。

## 禁止事項

- xiaozhi-server のソースをパッチする、独自イメージをビルドして差し替える（原則1）。
- ファームの追跡ファイルを編集する、`OTA_URL` / `STACKCHAN_SERVER_URL` 以外の Kconfig を変える（原則2）。
- 実キーを `.env` 以外（設定テンプレート・コード・`okf/`・コミットメッセージ）に書く。
- Vercel AI Gateway 以外の LLM プロバイダのキーを直接持ち込む（決定 008）。
- 一次情報を確認せずに設定キー名・モデル ID・API 仕様を書く。
- `okf/` の概念に `verified` を付ける。`deprecated` の概念を根拠に使う。
- サーバーのポートを LAN 外に公開する。

## マイルストーン

- **M0**: 骨格・CLAUDE.md・OKF 初期投入・xiaozhi-server 起動。
- **M1**: LLM を GPT-6 Luna（Vercel AI Gateway 経由）にし、疑似デバイスで一往復。
- **M2**: 実機の `OTA_URL` を自前に向けて書き込み、実機で会話・端末 MCP（首・LED）を確認。人間が `verified` を付ける。
- **M3**: brain の Jev 判定ループ（LLM フォールバック付き）で自律発話・首振り・感情表現。evals に代表ケース。自律発話は brain の WebSocket 中継で届ける（`okf/decisions/007-proactive-speech-path.md`）。
- **M4**: option-quants を MCP で接続。常時稼働機へ移設。
