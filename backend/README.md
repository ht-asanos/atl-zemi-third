# Backend — FastAPI

## セットアップ

```bash
uv sync
cp .env.example .env
# .env を編集して Supabase 接続情報を設定
```

## 起動

```bash
PYTHONPATH=src uv run uvicorn app.main:app --reload
```

API ドキュメント: http://localhost:8000/docs

## API エンドポイント

| Method | Path | 説明 | 認証 |
|---|---|---|---|
| GET | `/health` | ヘルスチェック | 不要 |
| POST | `/profiles` | プロフィール作成 | 必要 |
| GET | `/profiles/me` | 自分のプロフィール取得 | 必要 |
| POST | `/goals` | 目標作成 (upsert) | 必要 |
| GET | `/goals/me` | 自分の最新目標取得 | 必要 |
| POST | `/plans/weekly` | 週間プラン生成 (upsert) | 必要 |
| GET | `/plans/weekly?start_date=YYYY-MM-DD` | 週間プラン取得 | 必要 |
| PATCH | `/plans/{id}/meal` | 食事プラン変更 | 必要 |
| PUT | `/profiles/me` | プロフィール更新 | 必要 |
| GET | `/foods/staples` | 主食一覧取得 | 必要 |
| POST | `/recipes/refresh` | レシピ一括取得（管理者） | 必要 |
| POST | `/recipes/backfill` | 食材マッチ補完（管理者） | 必要 |

## テスト

```bash
# ユニット + API 結合テスト（Supabase 不要）
uv run pytest -v --cov -m "not integration"

# DB 結合テスト（supabase start が必要）
uv run pytest -v -m integration
```

## Lint / Format / 型チェック

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check
```

## ディレクトリ構成

```
backend/
├── src/app/
│   ├── main.py              # FastAPI アプリ + CORS
│   ├── config.py            # 環境変数設定
│   ├── dependencies/        # 認証・Supabase クライアント
│   ├── routers/             # API ルーター
│   ├── repositories/        # DB アクセス層
│   ├── schemas/             # リクエスト/レスポンス型
│   ├── models/              # ドメインモデル
│   ├── services/            # ビジネスロジック
│   └── data/                # マスターデータ
├── tests/                   # テスト
├── supabase/migrations/     # SQL マイグレーション
└── pyproject.toml
```

## Supabase ローカルセットアップ

```bash
npx supabase start
npx supabase db reset   # マイグレーション + シード適用
npx supabase status     # URL / Key 確認
```

`supabase status` の出力から以下を `.env` に設定:
- `SUPABASE_URL` — API URL
- `SUPABASE_ANON_KEY` — anon key
- `SUPABASE_JWT_SECRET` — JWT secret

## 楽天レシピ API 設定

レシピモードで楽天レシピを取得するには、楽天 API の設定が必要です。

### 1. 楽天デベロッパー登録

https://webservice.rakuten.co.jp/ にアクセスし、アプリを登録してください。

### 2. `.env` に設定

```bash
RAKUTEN_APP_ID=your_app_id
RAKUTEN_ACCESS_KEY=your_access_key   #（不要な場合もあります）
```

### 3. 動作確認

```bash
# レシピ取得（管理者ユーザーで実行）
curl -X POST http://localhost:8000/recipes/refresh \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json"
```
