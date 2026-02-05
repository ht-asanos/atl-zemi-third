# AGENTS.md

This is a guide for AI coding agents (Claude Code, Cursor, Codex, etc.). 
It defines the conventions, workflows, and constraints of this project.

> [!CAUTION]
> **ATL Team Rule:** このファイルは個人のエージェント設定を統一するためのものです。
> 変更する場合は必ずMTGで合意するか、PRを作成してレビューを受けてください。

---

## 🛠 Setup & Development Commands
エージェントは環境構築や実行の際、以下のコマンドを優先して使用してください。

- **Install:** `npm install` (or `pnpm install`)
- **Dev Server:** `npm run dev`
- **Build:** `npm run build`
- **Lint/Fix:** `npm run lint:fix`

## 🐍 Python Toolchain (Pythonプロジェクト向け)
Pythonを扱う場合は、以下のツールと使い方を標準として揃えてください。

### 目的
- 依存関係・実行方法・Lint/Format・型チェックの前提を統一し、環境差分による事故を減らす
- 設定は原則 `pyproject.toml` に集約する

### ツール選定
- **環境構築:** `uv` (パッケージ管理・仮想環境)
- **Lint/Format:** `ruff` (高速リンター & フォーマッター)
- **型チェック:** `ty` (高速型チェッカー)
- **コミット前チェック:** `pre-commit` (自動静的解析)

### 使い方
- **初回セットアップ:** `uv sync`
- **依存追加:** `uv add <package>` ( `uv pip install` は非推奨 )
- **フォーマット:** `uv run ruff format .`
- **lint:** `uv run ruff check .`
- **lint + fix:** `uv run ruff check --fix .`
- **型チェック:** `uv run ty check`
- **pre-commit install:** `uv run pre-commit install`
- **pre-commit 全実行:** `uv run pre-commit run --all-files`

### `pyproject.toml` 例
```toml
[project]
name = "my-project"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[tool.uv]
dev-dependencies = [
    "pre-commit>=4.0.0",
]

[tool.ruff]
line-length = 120
target-version = "py311"

[tool.ruff.lint]
select = [
    "E",
    "F",
    "I",
    "UP",
    "B",
]

[tool.ruff.format]
quote-style = "double"

[tool.ty]
python-version = "3.11"
```

### `.pre-commit-config.yaml` 例
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: check-json
      - id: check-toml
      - id: check-xml
      - id: check-yaml
      - id: debug-statements
      - id: detect-private-key
      - id: end-of-file-fixer
      - id: fix-byte-order-marker
      - id: trailing-whitespace

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.5
    hooks:
      - id: ruff-format
      - id: ruff
        args: ["--fix"]

  - repo: local
    hooks:
      - id: ty-check
        name: ty check
        entry: ty check
        language: system
        pass_filenames: false
```

## 🧪 Testing Instructions
エージェントはコード変更後、以下の手順で整合性を確認してください。

- **Unit Tests:** `npm run test:unit` (変更箇所のテストを優先)
- **Integration:** `npm run test` (マージ前に全体を確認)
- **Pattern:** 特定のテストのみ実行する場合は `npx vitest -t "<test_name>"` を使用。
- **Rule:** 「誰も求めていなくても」変更に関連するテストを追加または更新すること。

## 📐 Code Style & Conventions
- **Language:** TypeScript (Strict mode).
- **Format:** Single quotes, no semicolons.
- **Patterns:** 関数型プログラミングのパターンを推奨。
- **Imports:** - @ 記法によるパスエイリアスを使用すること。
  - ES Modules 優先。CommonJS は避ける。
- **Style:** 実装前に `@docs/style-guide.md` があれば参照すること。

## 📝 PR & Commit Rules
- **PR Title:** `[<component/module>] <Description>`
- **Checklist:** 1. `npm run lint` がパスしているか。
  2. 新規コードに対するテストが含まれているか。
  3. 破壊的変更がある場合はその旨を明記すること。

## 💡 Context & Gotchas (エージェントへの注意)
- **Knowledge Cutoff:** エージェントの知識は最新ではない可能性があるため、最新のライブラリ仕様は必ず `@package.json` のバージョンを確認し、公式ドキュメントへのリンクがあればそれを優先すること。
- **Implicit Rules:**
  - 状態管理には X ライブラリを使用し、独自に `useState` を乱立させない。
  - パフォーマンスの観点から、巨大なループ内での非同期処理は避ける。

---
## 📂 File Hierarchy
- プロジェクト内に複数の `AGENTS.md` が存在する場合、**編集対象のファイルに最も近い（ディレクトリ階層が深い）設定**が優先されます。
