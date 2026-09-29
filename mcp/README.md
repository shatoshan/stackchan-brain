# mcp

xiaozhi-server のサーバー側 MCP クライアント（`data/.mcp_server_settings.json`、`config/xiaozhi/mcp_server_settings.template.json` から生成）につなぐ MCP サーバー。

| ディレクトリ | 内容 |
|---|---|
| `self/` | スタックチャンが自分のこと（仕組み・調子・記憶・判断の理由・最近の変化）を答えるための読み取り専用ツール（決定 013、`okf/services/self-mcp.md`） |

option-quants（M4）も同じ口でつなぐ予定。option-quants とは MCP 契約のみで連携し、コード依存を持たない。
