# 自炊 x トレーニング最適化アプリ

一人暮らし向けの自炊とトレーニングを最適化する週間プラン自動生成アプリです。

## アーキテクチャ

```
[Next.js (Frontend)] → [FastAPI (Backend)] → [Supabase (PostgreSQL + Auth)]
```

## 技術スタック

| レイヤー | 技術 |
|---|---|
| Frontend | Next.js 15 (App Router), TypeScript, Tailwind CSS |
| Backend | FastAPI, Python 3.11, Pydantic |
| DB / Auth | Supabase (PostgreSQL + Row Level Security) |
| ツールチェーン | uv, ruff, ty, pre-commit, pytest, ESLint |

## 前提ツール

- **Node.js** >= 18
- **Python** >= 3.11
- **uv** (Python パッケージマネージャー)
- **Docker** (Supabase ローカル実行用)
- **Supabase CLI** (`npx supabase`)

## クイックスタート

### 1. Supabase ローカル起動

```bash
cd backend
npx supabase start
npx supabase db reset   # マイグレーション + シード適用
```

### 2. Backend 起動

```bash
cd backend
cp .env.example .env
# .env に Supabase のローカル接続情報を設定
uv sync
uv run uvicorn app.main:app --reload
```

### 3. Frontend 起動

```bash
cd frontend
cp .env.example .env.local
# .env.local に Supabase URL/Key と API URL を設定
npm install
npm run dev
```

ブラウザで http://localhost:3000 にアクセス。

## ドキュメント

- [Backend README](./backend/README.md) — API一覧、テスト、セットアップ
- [Frontend README](./frontend/README.md) — ページフロー、コンポーネント構成
- [ロードマップ](./doc/roadmap.md)

## フェーズ状況

| フェーズ | 内容 | 状態 |
|---|---|---|
| 1 | データモデル・栄養エンジン・食事提案・トレーニングテンプレート | 完了 |
| 2a | Backend API + Supabase + Auth | 完了 |
| 2b | Frontend UI + README 整備 | 完了 |
