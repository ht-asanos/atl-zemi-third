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