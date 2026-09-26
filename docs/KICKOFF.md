# stackchan-brain キックオフ指示書

> 2026-09-26 の最初のセッションで人間から渡された指示書の原文。OKF 対象外（自由形式）。
> ここに書かれた事実のうち、一次情報で確認・訂正したものは `okf/` 側が正（`okf/log.md` 参照）。

このリポジトリを新規作成し、初期骨格・Docker構成・CLAUDE.md・OKF知識バンドルを整備してください。
**推測で埋めず、不明点は一次情報（公式リポジトリ・仕様書）を確認してから実装・記述してください。**
知識は OKF（Open Knowledge Format）v0.2 のバンドル `okf/` に置き、CLAUDE.md には振る舞いの規約だけを書きます。

---

## 1. ゴール

M5Stack製スタックチャン（CoreS3ベース）を、受動応答だけでなく**自律的に話しかけてくる会話ロボット**にする。
ファームウェアは極力改変せず、頭脳をサーバー側（まずMacBook Air上のDocker、将来Raspberry Pi 5 / N100ミニPCへ移設）に置く。

## 2. 文書管理方針（OKF）

### 2.1 まず仕様を読む
着手前に現行仕様を読むこと: `https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md`
v0.1→v0.2 で破壊的変更がある（`timestamp` → `generated: {by, at}`、本文 `# Citations` → フロントマター `sources`）。ネット上の解説記事は古いものが多いので、SPEC.md を正とする。

### 2.2 役割分担
| 置き場所 | 書くもの |
|---|---|
| `CLAUDE.md` | どう振る舞うか（§6の原則、コマンド、禁止事項）。**200行以内**。`okf/index.md` への入口だけ指す。`@` で全体インポートしない |
| `okf/` | 何を知っているか（ハード・プロトコル・外部API・決定記録）。1概念＝1ファイル |
| `.claude/skills/okf/SKILL.md` | `okf/` の読み書きルール（§2.5）。本体は呼ばれた時だけ読まれる |

### 2.3 バンドル構成
```
okf/
├── index.md              # okf_version: "0.2"、各ディレクトリへの目次
├── log.md                # YYYY-MM-DD 見出し、新しい順
├── hardware/             # type: Hardware   端末の物理仕様
├── firmware/             # type: Firmware   公式ファーム、Kconfig、端末MCPツール
├── protocol/             # type: Protocol   XiaoZhi WebSocket/MQTT+UDP プロトコルのメモ
├── services/             # type: Service    xiaozhi-esp32-server、brain、mcp-bridge の役割と設定
├── external/             # type: ExternalAPI  Anthropic API、Jev（Vercel AI Gateway）、EdgeTTS 等
├── design/               # type: Design     3層アーキテクチャ、状態ブロブ仕様、Jev質問設計
├── decisions/            # type: Decision   採用/不採用の決定と理由（ADR相当）
└── runbooks/             # type: Runbook    起動手順、ファーム書き込み手順、疑似デバイスの使い方
```

### 2.4 フロントマターの使い方
- 必須: `type`。推奨: `title`, `description`, `tags`。
- `status`: 一次情報で確認済みなら `stable`、未確認・推測を含むなら **`draft`**。旧情報は削除せず `deprecated`。
- `stale_after`: 仕様が動いているもの（xiaozhi-esp32-server の設定キー、Jev の提供状況、Anthropic のモデル名等）には必ず付ける。目安3か月。
- `sources`: 確認した一次情報（リポジトリのファイルパス、ドキュメントURL）を必ず記録する。
- `generated`: 書いたエージェントを `<producer>/<version>` 形式で記録する（例: `claude-code/opus-5.5`）。
- `verified`: **エージェントは付けない。** 人間が実機・実環境で確認した時に `human:<id>` で付ける。

### 2.5 SKILL.md に書く読み書きルール
読むとき: `okf/index.md` から辿る（いきなりgrepしない）／`deprecated` は使わない／`stale_after` を過ぎていれば古い可能性を添える／`verified` が無いものは断定しない。
書くとき: 1概念1ファイル／自動生成できる情報ではなく一次情報を見ても分からないことを書く／`generated` に自分を書く／`verified` は付けない／変更したら `log.md` に追記／実装と `okf/` が食い違ったら勝手に直さず報告する。

## 3. 初期投入する知識（§3の内容を `okf/` の概念ファイルに転記すること）

以下は事前調査で確認済み。転記時は各項目に `sources` を付け、確認元を明記する。

### hardware/stackchan.md（type: Hardware, status: stable）
- CoreS3ベース。ESP32-S3、16MB Flash / 8MB PSRAM、2.0インチタッチ液晶、0.3MPカメラ、近接・照度センサ、9軸IMU、スピーカー、デュアルマイク。
- ロボット本体: 首サーボ2軸（yaw 360°連続 / pitch 90°）、RGB LED 12個、IR送受信、3ゾーンタッチ、NFC、550mAh電池、USB-C。
- sources: https://github.com/m5stack/StackChan README

### firmware/official-firmware.md（type: Firmware, status: stable）
- 公式リポジトリ https://github.com/m5stack/StackChan（firmware / server / app / remote）。README曰くリリース版より更新が遅れることがある。
- ビルド: ESP-IDF v5.5.4、`python3 fetch_repos.py` → `idf.py build` → `idf.py flash`（USB直結）。M5Burnerは公式ビルド済みイメージ用。
- **AIエージェント部分は `78/xiaozhi-esp32` v2.2.4 にパッチを当てて組み込まれている**（`firmware/repos.json`, `firmware/patches/xiaozhi-esp32.patch`）。
- ASR / LLM / TTS はすべてサーバー側。端末はOpus音声をWebSocketで送受信するだけ。デフォルトのQwenはXiaoZhiクラウド側で動いている。
- sources: `firmware/README.md`, `firmware/repos.json`

### firmware/kconfig.md（type: Firmware, status: stable）
- `OTA_URL` デフォルト `https://api.tenclass.net/xiaozhi/ota/`。端末はここでWebSocketサーバーのアドレスを取得する。**自前サーバーに向けるにはここを変えて一度だけリビルドする。**
- `STACKCHAN_SERVER_URL`: StackChan Server（Go製、アプリ連携・コミュニティ機能）のベースURL。当面は触らない。
- sources: `firmware/main/Kconfig.projbuild`

### firmware/device-mcp-tools.md（type: Firmware, status: stable）
端末がサーバーに公開しているMCPツール:
- `self.robot.get_head_angles` / `self.robot.set_head_angles(yaw, pitch, speed)` — yaw -128〜128、pitch 0〜90、speed 100〜1000、自然な範囲は±45°
- `self.robot.set_led_color`
- `self.robot.create_reminder` / `get_reminders` / `stop_reminder`
- sources: `firmware/main/hal/hal_mcp.cpp`

### services/xiaozhi-esp32-server.md（type: Service, status: draft, stale_after: 3か月後）
- 採用: `xinnan-tech/xiaozhi-esp32-server`（Python主体、Docker対応 x86/arm64、MQTT+UDP / WebSocket、MCP接続点対応）。
- 構成: VAD（SileroVAD ローカル）→ ASR → LLM → TTS。
- 「4コア8GB推奨」はASRをローカル（FunASR/SenseVoice）で回す場合。ASR/TTSを外部APIにすればPi 4クラスでも動く。
- デフォルトTTSは EdgeTTS（無料）。日本語ASRは FunASR が対応。LLM差し替えはOpenAI互換APIが基本。
- **プロジェクト自身が「セキュリティ評価未了、本番非推奨」と明記** → LAN内で閉じ、インターネット露出しない。
- 設定キー名・最小構成の起動手順は未確認 → §8で確認後に `stable` へ。

### external/anthropic-api.md（type: ExternalAPI, status: stable, stale_after: 3か月後）
- OpenAI SDK互換レイヤー: `base_url=https://api.anthropic.com/v1/`、キーをClaude APIキー、モデル名をClaudeモデルにするだけで動く。**テスト・評価目的の互換層で長期本番向けではない**。function callingの `strict` 無視、prompt caching非対応。
- 会話ループを自前で書く段階では Anthropic ネイティブ Messages API に移行する。
- ランタイムLLMは Claude Haiku 系（コストと速度）。開発時のClaude Code本体は Opus 5.5。
- Bedrock/Vertex は LiteLLM プロキシ経由で可能だが旨味が薄く不採用（→ decisions/）。
- sources: https://platform.claude.com/docs/en/cli-sdks-libraries/libraries/openai-sdk

### external/jev.md（type: ExternalAPI, status: draft, stale_after: 3か月後）
- TypeSafe AI の System One Model。用途は**構造化判定**（生成しない）。事前定義した選択肢（最大255）から較正済み確率付きで返す。70〜500ms、入力 $0.042/MTok、出力無料。
- **テキスト入力のみ（画像不可）**。
- 公式コンソールの受付停止中のため **Vercel AI Gateway 経由**で呼ぶ。TypeSafe公式クライアント（`typesafe-sdk`）はベースURLとキーを変えるだけで互換。Choice/Scoreの信頼度は providerMetadata で返る。ZDR/No-Training をリクエスト単位で指定可。
- 代替: OpenRouter（`typesafe/jev-1.13`）、Netlify AI Gateway、Cloudflare Workers AI（リクエスト形式が本家と異なり公式SDK不可）。
- Jevが使えない期間用に、同じ質問群をHaikuにJSONで答えさせるフォールバックを用意し、インターフェースを揃える。
- モデルID・レート制限・現在の提供状況は未確認 → §8。
- sources: https://typesafe.ai/blog/introducing-system-one-models-and-jev, https://vercel.com/i/what-is-jev

### design/three-layer-architecture.md（type: Design, status: stable）
| 層 | 場所 | 時間スケール | 役割 |
|---|---|---|---|
| 1. 反射 | 端末（ESP32） | ms | 近接・照度・IMU・音量の閾値判定、まばたき、視線追従。既存ファームのまま |
| 2. 直感 | brain（Jev） | 数百ms、1〜5秒周期 | 状態ブロブ→ `should_speak` / `speech_kind` / `emotion` / `escalate_to_llm` / `attention_target` を確率付きで判定 |
| 3. 熟考 | brain（Haiku） | 秒 | 発話生成、会話要約（記憶）、状態ブロブに戻す文脈の更新 |
- 発話閾値は機嫌パラメータで動的に変える。定型フレーズ集からの選択はJevに任せ、Haikuは自由生成が必要な時だけ呼ぶ。
- 会話ログはセッションごとにHaikuで要約して永続化し、次回の状態ブロブに含める。
- カメラ等は層1で数値化（顔検出数・顔サイズ・動体有無）してから状態ブロブへ。「何が写っているか」が必要な時だけHaiku visionで1フレームを短文化して混ぜる。

### design/state-blob.md（type: Design, status: draft）
固定フォーマットのJSON: 時刻、人検出、最終発話からの秒数、直近3発話の要約、機嫌スコア、本日の発話回数、外部イベント（option-quantsシグナル等）。フィールド定義は実装時に確定し `stable` へ。

### decisions/（type: Decision, status: stable）
- `001-server-side-brain.md`: ファーム改変を最小化しサーバー側に頭脳を置く。理由: AI AgentがXiaoZhiプロトコルで外出しされているため。
- `002-self-hosted-xiaozhi-server.md`: XiaoZhiクラウド＋MCP接続点ではなく自前サーバー。理由: 自律発話にはサーバー側ループへの介入が必要。
- `003-lan-only.md`: LAN内で閉じる。理由: サーバーのセキュリティ評価未了、コスト最小。
- `004-no-bedrock.md`: Bedrock/Vertex不採用。理由: LiteLLM経由で可能だが料金同等・IAM設定の手間増。
- `005-jev-via-vercel-gateway.md`: Jevは Vercel AI Gateway 経由。理由: 公式受付停止、公式SDK互換、providerMetadataで確率取得可。
- `006-okf-for-knowledge.md`: 知識管理はOKF v0.2、バンドルは可視の `okf/`（`.okf/` ではない）。理由: 確定事実/未確認の区別と来歴を機械可読にするため。可視にするのは人間も読み書きする前提のため。`docs/` は自由形式用に分け、バンドルの適合性を保つ。

## 4. アーキテクチャ（要約）
§3 design/ を参照。反射（端末）／直感（Jev）／熟考（Haiku）の3層。

## 5. リポジトリ骨格

```
stackchan-brain/
├── CLAUDE.md              # 振る舞いの規約のみ。okf/index.md への入口を指す
├── .claude/skills/okf/SKILL.md
├── okf/                   # OKF v0.2 知識バンドル（§2.3）。中身は全てフロントマター付き
├── docs/                  # 自由形式の文書（この KICKOFF.md、図、メモ）。OKF非対象
├── docker-compose.yml     # xiaozhi-server（公式イメージ）+ brain + mcp-bridge
├── brain/                 # Jev定期判定ループ、状態ブロブ組み立て、Haiku発話生成
├── mcp/                   # xiaozhi のMCP接続点に繋ぐMCPサーバー（option-quants照会、天気等）
├── config/                # xiaozhi-server 用設定（LLM=Anthropic互換、TTS、ASR）
├── sim/                   # 実機なしでテストする疑似デバイス（既存クライアントを調査して採用）
├── evals/                 # 状態ブロブ→Jev判定の記録と再生（回帰テスト）
└── .env.example           # ANTHROPIC_API_KEY, VERCEL_AI_GATEWAY_KEY 等。実キーはコミットしない
```

## 6. 設計原則（CLAUDE.md に明記すること）

1. **xiaozhi-esp32-server 本体は改変しない。** 差し込み口（LLMプロバイダ設定・MCP接続点・プラグイン）のみ使い、本体はDockerイメージとして依存する。
2. **端末ファームは `OTA_URL`（必要なら `STACKCHAN_SERVER_URL`）の変更以外いじらない。**
3. **option-quants とはMCP契約のみで連携する。** コード依存ゼロ。
4. 反射／直感／熟考の3層を守る。Jevが生成をしたり、Haikuが毎秒呼ばれたりする設計にしない。
5. LAN内で閉じる。インターネット露出・TLS・認証はスコープ外。
6. 秘密情報は `.env` のみ。`.env.example` を同期する。
7. 不明なAPI仕様・設定キー名は一次情報で確認する。推測で設定ファイルを書かない。
8. **知識は `okf/` に書く。** 事実を知ったら概念ファイルに `sources` 付きで追記し、`log.md` を更新する。未確認の事実は `status: draft`。`verified` は付けない。`okf/` と実装が食い違ったら報告する。

## 7. マイルストーン

- **M0**: リポジトリ作成、骨格、CLAUDE.md、SKILL.md、`okf/` 初期投入（§3）、docker-compose で xiaozhi-server が起動する。
- **M1**: LLMをAnthropic（OpenAI互換レイヤー、Haiku）に差し替え、疑似デバイスから一往復の会話が返る。
- **M2**: 実機の `OTA_URL` を自前サーバーに向けてリビルド・書き込み、実機で会話が通る。端末MCPツール（首・LED）をサーバー側から呼べることを確認。人間が `verified` を付ける。
- **M3**: brain のJev判定ループ（Haikuフォールバック付き）を追加し、自律発話・首振り・感情表現が動く。evals に代表ケースを蓄積。
- **M4**: option-quants をMCP経由で接続し、シグナル実況。常時稼働機（Pi 5 / N100）へ移設。

## 8. この最初のセッションでやること（M0）

1. OKF SPEC.md（§2.1）を読む。
2. `okf/` を §2.3 の構成で作り、§3 の内容を概念ファイルに転記する。`index.md`、`log.md` を作る。
3. `CLAUDE.md`（§6の原則＋入口）と `.claude/skills/okf/SKILL.md`（§2.5）を書く。
4. `xinnan-tech/xiaozhi-esp32-server` の最新README・デプロイ文書を読み、**最小構成（Python単体、Java管理APIなし）**の起動方法・設定ファイル形式・LLM/ASR/TTSの設定キー名を確認する。確認結果を `services/xiaozhi-esp32-server.md` に `sources` 付きで反映し `stable` にする。
5. 確認内容に基づいて `docker-compose.yml` と `config/` を書く。ASRはデフォルト（FunASRローカル）、TTSはEdgeTTS、LLMはAnthropic互換設定。
6. 疑似デバイスに使える既存クライアント（`py-xiaozhi` 等）を調査し、`runbooks/simulator.md` に導入手順を書く。
7. `.env.example` を作る。
8. `docker compose up` で起動確認。動かなければ原因と次の一手を `decisions/` か `log.md` に残す。
9. §9の未確認事項を確認し、結果を該当ファイルに反映する。

## 9. 未確認事項（着手前に確認し、`okf/` に結果を記録すること）

- xiaozhi-esp32-server 側がOTAエンドポイントを提供しているか（提供していれば端末側の変更は `OTA_URL` のみで済む）→ `services/xiaozhi-esp32-server.md`
- xiaozhi-esp32-server の最新版で「サーバー側から能動的にTTS発話を押し込む」手段があるか（自律発話の実装経路。なければ brain がプロトコルを直接喋る必要がある）→ `protocol/`, `decisions/`
- Vercel AI Gateway での Jev のモデルID・レート制限・現在の提供状況 → `external/jev.md`
- Anthropic OpenAI互換レイヤーで使う最新の Haiku モデル名 → `external/anthropic-api.md`
