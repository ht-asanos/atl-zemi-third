# 自炊 x トレーニング最適化アプリ

一人暮らし向けの自炊とトレーニングを最適化する週間プラン自動生成アプリです。

## 主な機能

- `レシピモード` と `主食モード` の 2 モードで週間プランを生成
- レシピモードでは主食フィルタ（例: 冷凍うどん）を夕食候補に反映
- 右上プロフィールメニューから `プロフィール編集 / 目標変更 / プラン生成設定` に遷移
- 週間買い物リストで材料をチェックし、`未購入 / 購入済み` を切り替え管理
- 材料名の正規化（記号・括弧ノイズ除去）による買い物リスト品質の改善

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

- **Node.js** >= 20
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

## Docker 使い方

### 1. 事前準備

ルートで環境変数ファイルを作成します。

開発用途（ローカル Supabase 接続）:

```bash
cp .env.dev.example .env
```

本番/ステージング想定:

```bash
cp .env.prod.example .env
```

`./.env` を開き、必要な値（`SUPABASE_*`, `NEXT_PUBLIC_*`, `GOOGLE_API_KEY`, `YOUTUBE_API_KEY` など）を設定してください。

### 2. ビルド

```bash
docker compose build
```

キャッシュ無効:

```bash
docker compose build --no-cache
```

### 3. 起動

```bash
docker compose up -d
```

フォアグラウンド起動:

```bash
docker compose up
```

### 4. 動作確認

Backend:

```bash
curl http://localhost:8000/health
```

Frontend:

```bash
curl -I http://localhost:3000
```

### 5. ログ確認

全体:

```bash
docker compose logs -f
```

個別:

```bash
docker compose logs -f backend
docker compose logs -f frontend
```

### 6. 停止・削除

停止:

```bash
docker compose stop
```

停止 + コンテナ削除:

```bash
docker compose down
```

イメージも削除:

```bash
docker compose down --rmi local
```

### 7. 更新反映

```bash
docker compose up -d --build
```

### 8. 補足

- `depends_on: service_healthy` により、backend が healthy になるまで frontend は待機します。
- `NEXT_PUBLIC_*` は frontend のビルド時に埋め込まれるため、値変更時は frontend の再ビルドが必要です。
- Supabase は docker compose 管理外のため、接続先と鍵は `.env` で管理します。
- ブラウザから参照する `NEXT_PUBLIC_SUPABASE_URL` は `http://localhost:54321` を推奨します（`127.0.0.1` と混在させない）。
- Docker コンテナ内から参照する `SUPABASE_URL` は `http://host.docker.internal:54321` を使用します。

### 9. トラブルシューティング（ログインできない / ループする）

`auth/v1/token` が 200 でも、古い frontend ビルドキャッシュや orphan コンテナで画面遷移が不安定になることがあります。
以下で完全リセットしてください。

```bash
docker compose down --remove-orphans
docker builder prune -f
docker compose build --no-cache
docker compose up -d
```

確認:

```bash
docker compose ps
docker compose logs --since=2m frontend backend
```

`Network ... already exists` や `container name is already in use` が出る場合も、上記の `down --remove-orphans` で解消できます。

## ドキュメント

- YouTube レシピ運用は管理画面/API の両方に対応しています。単一 URL の抽出・登録に加えて、チャンネル動画を `source_query -> target_staple` で一括アレンジ登録できます。
- 一括アレンジ登録では、元動画タイトルの厳格フィルタ、字幕取得、Gemini 品質ゲート、付け合わせ除外を通過したものだけが DB に登録されます。
- YouTube レシピの栄養再計算や `recipe_ingredients` の再構築が必要な場合は backend 側の運用コマンドを使用します。
- [Backend README](./backend/README.md) — API一覧、テスト、セットアップ
- [Frontend README](./frontend/README.md) — 画面フロー、UI構成、買い物チェック仕様
- [YouTube Recipe Ops](./doc/youtube_recipe_ops.md) — YouTube 取込、一括アレンジ、復旧運用
- [Admin YouTube Quick Guide](./doc/admin_youtube_quick_guide.md) — `/admin/youtube` の画面ベース運用手順
- [ロードマップ](./doc/roadmap.md)

## フェーズ状況

| フェーズ | 内容 | 状態 |
|---|---|---|
| 1 | データモデル・栄養エンジン・食事提案・トレーニングテンプレート | 完了 |
| 2a | Backend API + Supabase + Auth | 完了 |
| 2b | Frontend UI + README 整備 | 完了 |
