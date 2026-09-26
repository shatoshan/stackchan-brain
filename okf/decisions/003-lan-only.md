---
type: Decision
title: "003: LAN 内で閉じる"
description: サーバー群はインターネットに露出させず、TLS・認証もスコープ外とする。
tags: [decision, adr]
status: stable
generated: { by: claude-code/opus-5.5, at: 2026-09-26T08:00:00Z }
sources:
  - id: kickoff
    resource: ../../docs/KICKOFF.md
    title: stackchan-brain キックオフ指示書（human:shingo 作成）
    author: human:shingo
  - id: readme
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/README.md
    title: xiaozhi-esp32-server README（警告節）
---

# 決定
xiaozhi-server・brain・mcp-bridge は LAN 内だけで使う。インターネット露出、TLS、認証はスコープ外。

# 理由
- xiaozhi-esp32-server の README が「機能未完成、ネットワークセキュリティ評価未了、本番で使うな」と明記している。[^readme]
- コストを最小にする。

# 帰結

- **ASR はローカル必須（FunASR 等）。** 会話セッション中、端末のマイク音声は途切れずサーバーへ流れる（無音タイムアウト 600 秒、今後はさらに長時間のセッションも想定）。クラウド ASR にすると、部屋の音声がそのまま LAN の外に出る。（2026-09-26 追記）
- ただし、認識されたテキストは LLM（Vercel AI Gateway 経由の GPT-6 Luna）に送られる。長時間セッションで周囲の会話が認識されると、その文字起こしはクラウドに出る。音声そのものより小さいが、ゼロではない。抑えるには、brain の中継で「聞くべき時」以外のマイク音声をサーバーに渡さない（未実装）。
- 画像: 在席確認の写真は brain が LAN 内で顔検出するだけ。LLM が `take_photo` で撮る写真（「何が見える？」）は VLLM としてクラウドに送られる。
- `server.auth.enabled: false` のまま運用する。ポート 8000 / 8003 をルーターで転送しない。

[^readme]: xiaozhi-esp32-server README
