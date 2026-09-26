# llm-proxy

xiaozhi-server → Vercel AI Gateway の中継。`reasoning_effort` の既定値を注入し、Gateway の API キーを付与する。
理由は `okf/decisions/008-llm-via-vercel-gateway.md`。

依存は aiohttp のみ。追加ビルドを避けるため xiaozhi-server イメージ（aiohttp 同梱）で実行している。
