---
type: Decision
title: "006: 知識管理は OKF v0.2、バンドルは可視の okf/"
description: プロジェクト知識を OKF v0.2 バンドルとして okf/ に置き、docs/ は自由形式用に分ける。
tags: [decision, adr]
status: stable
generated: { by: claude-code/opus-5.5, at: 2026-09-26T08:00:00Z }
sources:
  - id: kickoff
    resource: ../../docs/KICKOFF.md
    title: stackchan-brain キックオフ指示書（human:shingo 作成）
    author: human:shingo
  - id: okf-spec
    resource: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
    title: Open Knowledge Format v0.2 SPEC
---

# 決定
- 知識は OKF v0.2 のバンドルとして、リポジトリ直下の可視ディレクトリ `okf/` に置く（`.okf/` ではない）。[^okf-spec]
- `docs/` は自由形式（キックオフ指示書・図・メモ）用に分け、OKF の対象外とする。
- 振る舞いの規約は `CLAUDE.md`、読み書きルールは `.claude/skills/okf/SKILL.md`。

# 理由
- 確定事実と未確認（`status: draft`）の区別、来歴（`sources`、`generated`）、人間の確認（`verified`）を機械可読にするため。
- 人間も読み書きする前提なので不可視ディレクトリにしない。
- `docs/` を分けることで、フロントマターの無い文書がバンドルの適合性（全 `.md` に `type` 必須）を壊さない。

[^okf-spec]: OKF v0.2 SPEC
