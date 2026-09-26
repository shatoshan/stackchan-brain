---
okf_version: "0.2"
---

# stackchan-brain 知識バンドル

自律的に話しかける StackChan の頭脳（サーバー側）に関する知識。読み書きのルールは `.claude/skills/okf/SKILL.md`。変更履歴は [log](log.md)。

# hardware — 端末の物理仕様

* [StackChan ハードウェア](hardware/stackchan.md) - CoreS3 ベースの StackChan 本体とロボット部の物理仕様。

# firmware — 公式ファーム

* [StackChan 公式ファームウェア](firmware/official-firmware.md) - firmware の構成・ビルド方法と、組み込まれた XiaoZhi エージェント部分。
* [Kconfig（接続先設定）](firmware/kconfig.md) - 端末が接続するサーバーを決める OTA_URL と STACKCHAN_SERVER_URL。
* [端末が公開する MCP ツール](firmware/device-mcp-tools.md) - 首・LED・リマインダーの MCP ツールと引数範囲。

# protocol — XiaoZhi プロトコル

* [XiaoZhi 通信プロトコルの要点](protocol/xiaozhi-protocol.md) - メッセージ種別と音声チャネルの開閉条件。自律発話設計の前提。（draft）

# services — サーバー群

* [xiaozhi-esp32-server（最小構成）](services/xiaozhi-esp32-server.md) - 起動方法・設定形式・LLM/ASR/TTS の設定キー、OTA、発話押し込み API の有無。
* [llm-proxy](services/llm-proxy.md) - xiaozhi-server → Vercel AI Gateway 中継。reasoning_effort 注入とキー付与。

# external — 外部 API

* [Vercel AI Gateway](external/vercel-ai-gateway.md) - LLM と Jev を 1 本のキーで呼ぶ統一窓口。エンドポイント・推論設定・カタログ。
* [OpenAI GPT-6 Luna](external/openai-gpt-6-luna.md) - ランタイム LLM。料金・推論努力と function calling の制約。（draft）
* [Anthropic Claude API](external/anthropic-api.md) - 旧ランタイム LLM（Haiku）。（deprecated）
* [Jev via Vercel AI Gateway](external/jev.md) - 直感層の構造化判定に使う Jev の呼び方、料金・制限、レスポンス形式。（draft）

# design — 設計

* [3層アーキテクチャ](design/three-layer-architecture.md) - 反射（端末）/ 直感（Jev）/ 熟考（GPT-6 Luna）に役割と時間スケールを分ける全体設計。
* [状態ブロブ仕様](design/state-blob.md) - 直感層に毎周期渡す固定フォーマット JSON。（draft）

# decisions — 決定記録

* [001: 頭脳はサーバー側に置く](decisions/001-server-side-brain.md) - ファーム改変を最小化し、ロジックはサーバー側に置く。
* [002: 自前の xiaozhi-esp32-server を使う](decisions/002-self-hosted-xiaozhi-server.md) - XiaoZhi クラウドではなく LAN 内に自前サーバー。
* [003: LAN 内で閉じる](decisions/003-lan-only.md) - インターネット露出・TLS・認証はスコープ外。
* [004: Bedrock / Vertex は使わない](decisions/004-no-bedrock.md) - Anthropic API を直接使う。（deprecated → 008）
* [005: Jev は Vercel AI Gateway 経由](decisions/005-jev-via-vercel-gateway.md) - TypeSafe 本家ではなく Vercel 経由。
* [006: 知識管理は OKF v0.2](decisions/006-okf-for-knowledge.md) - 可視の okf/ に置き、docs/ は自由形式用。
* [007: 自律発話を端末に届ける経路](decisions/007-proactive-speech-path.md) - 発話押し込み API が無いことを受けた候補と推奨。（draft・未決定）
* [008: LLM は GPT-6 Luna、Gateway に統一](decisions/008-llm-via-vercel-gateway.md) - コスト効率とキー一本化。llm-proxy を挟む理由。

# runbooks — 手順書

* [xiaozhi-server の起動と疎通確認](runbooks/server-startup.md) - docker compose で起動し OTA と WebSocket を確認する。
* [疑似デバイス](runbooks/simulator.md) - sim/text_client.py と py-xiaozhi で実機なしに会話を試す。（draft）
* [ファームの OTA_URL 変更と書き込み](runbooks/firmware-flash.md) - M2 用。（draft・未実行）
