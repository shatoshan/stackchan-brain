---
name: okf
description: stackchan-brain の知識バンドル okf/（OKF v0.2）を読む・書く時のルール。ハード仕様、プロトコル、xiaozhi-server の設定キー、外部 API、設計、決定記録を調べる時や、新しく分かった事実を記録する時に使う。
---

# okf/ の読み書きルール

`okf/` は Open Knowledge Format v0.2 のバンドル。仕様の正は
https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md （v0.1 の `timestamp` や本文 `# Citations` は使わない）。

## 読むとき

1. **`okf/index.md` から辿る。** いきなり grep しない。index の説明文で当たりを付けてから概念ファイルを開く。
2. `status: deprecated` の概念は根拠に使わない（履歴として読むだけ）。
3. `stale_after` を過ぎていたら、「古い可能性がある」と添えて使う。必要なら一次情報を再確認する。
4. `verified` が無い概念は人間の確認を経ていない。断定せず「okf/ によれば〜（未検証）」のように扱う。`status: draft` はなおさら。
5. 本文の脚注 `[^id]` は `sources` の `id` に対応する。根拠を示す時はその `resource` を引く。

## 書くとき

1. **1概念 1ファイル。** 置き場所は type で決める:
   `hardware/`(Hardware) `firmware/`(Firmware) `protocol/`(Protocol) `services/`(Service) `external/`(ExternalAPI) `design/`(Design) `decisions/`(Decision, 連番 `NNN-slug.md`) `runbooks/`(Runbook)。
   `index.md` と `log.md` は予約名なので概念に使わない。
2. **書く価値のあること:** 一次情報を見ても分からないこと（確認結果、食い違い、落とし穴、決定の理由、実行結果）。ソースを読めば自明な情報の丸写しや、自動生成できる一覧は書かない。
3. フロントマター:
   ```yaml
   ---
   type: Service                 # 必須
   title: ...
   description: 1文の要約（index.md にも載せる）
   tags: [...]
   status: stable                # 一次情報で確認済みなら stable、推測・未確認を含むなら draft
   stale_after: 2026-12-26T00:00:00Z   # 動いている仕様（設定キー・モデル名・提供状況）には必ず。目安3か月後
   generated: { by: claude-code/<model>, at: <UTC ISO8601> }   # 書いたのは自分
   sources:
     - id: short-key
       resource: https://github.com/<org>/<repo>/blob/<commit>/<path>   # コミット固定の URL を優先
       title: ...
   ---
   ```
4. **`verified` は付けない。** 人間が実機・実環境で確認した時に `verified: { by: human:<id>, at: ... }` を付ける。
5. 主張ごとに脚注 `[^id]` で出典を付ける。概念間リンクは `/hardware/stackchan.md` のようなバンドル相対パス。
6. 古くなった概念は消さずに `status: deprecated` にし、後継へのリンクを書く。
7. 変更したら **`okf/log.md` に追記**（`## YYYY-MM-DD` 見出し、新しい順、`**Update**:` 等で始める）。概念を増やしたら `okf/index.md` にも1行足す。
8. **実装（compose・設定・コード）と `okf/` が食い違っていたら、どちらも勝手に直さずユーザーに報告する。**
