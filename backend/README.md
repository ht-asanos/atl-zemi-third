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
| GET | `/plans/weekly/shopping-list?start_date=YYYY-MM-DD` | 週間買い物リスト取得 | 必要 |
| GET | `/plans/weekly/shopping-list/checks?start_date=YYYY-MM-DD` | 買い物チェック状態取得 | 必要 |
| POST | `/plans/weekly/shopping-list/checks` | 買い物チェック状態更新 | 必要 |
| PATCH | `/plans/{id}/meal` | 食事プラン変更 | 必要 |
| PATCH | `/plans/{id}/recipe` | 夕食レシピ差し替え | 必要 |
| PUT | `/profiles/me` | プロフィール更新 | 必要 |
| GET | `/foods/staples` | 主食一覧取得 | 必要 |
| GET | `/foods/mext/search` | 食品DB検索（文科省食品成分DB） | 必要 |
| POST | `/recipes/refresh` | レシピ一括取得（管理者） | 必要 |
| POST | `/recipes/backfill` | 食材マッチ補完（管理者） | 必要 |

## レシピモードの主食指定について

- `POST /plans/weekly` で `mode=recipe` + `staple_name` を指定すると、夕食レシピは主食一致を優先して選定します。
- 主食指定時に一致レシピが 0 件の場合、API は `422` を返します（非一致フォールバック禁止）。
- `PATCH /plans/{id}/recipe` で差し替える場合も、作成時の `staple_name` を保持して同系統レシピを再提案します。

## 買い物リストのチェック仕様

- チェック状態は週単位で保存されます（`start_date` + `group_id`）。
- 買い物リスト生成時、チェック済み材料は除外せず `checked=true` で返却されます。
- フロントは `checked` を使って `未購入 / 購入済み` を分離表示し、再チェック解除も可能です。

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

## migration 014（YouTube列）適用

`014_youtube_recipe_source.sql` は `recipes.youtube_video_id` と `recipes.recipe_source` を追加します。
既存データを消さずに適用する場合は `db reset` ではなく以下を使います。

```bash
cd backend
npx --yes supabase migration up --local
```

## データ投入・補完コマンド

`app.services.data_loader` で使う主要コマンド:

```bash
cd backend

# 既存データ初期ロード（楽天系）
PYTHONPATH=src uv run python -m app.services.data_loader init

# 未マッチ食材の補完（正規化 + MEXTスクレイピング）
PYTHONPATH=src uv run python -m app.services.data_loader backfill

# 食材名正規化だけ再実行
PYTHONPATH=src uv run python -m app.services.data_loader normalize-ingredient-backfill

# MEXT Excel 取込
PYTHONPATH=src uv run python -m app.services.data_loader load-mext-excel <excel_path_or_dir>

# YouTube字幕から主食指定で取り込み（複数チャンネル可）
PYTHONUNBUFFERED=1 PYTHONPATH=src uv run python -m app.services.data_loader \
  fetch-youtube-recipes うどん 25 @Kurashiru,@ryuji825,@sanpiryoron

# 字幕取得チェック（SSL/字幕有無の確認に使う）
PYTHONUNBUFFERED=1 PYTHONPATH=src uv run python -m app.services.data_loader \
  check-youtube-transcript 'https://www.youtube.com/watch?v=<video_id>' ja

# YouTubeレシピの栄養再計算
PYTHONUNBUFFERED=1 PYTHONPATH=src uv run python -m app.services.data_loader \
  repair-youtube-nutrition

# recipe_ingredients を材料名+分量ベースで再構築
PYTHONUNBUFFERED=1 PYTHONPATH=src uv run python -m app.services.data_loader \
  rebuild-recipe-ingredients

# 非食事レシピの棚卸し（dry-run）
PYTHONUNBUFFERED=1 PYTHONPATH=src uv run python -m app.services.data_loader \
  prune-non-meal-recipes

# 非食事レシピを実削除
PYTHONUNBUFFERED=1 PYTHONPATH=src uv run python -m app.services.data_loader \
  prune-non-meal-recipes --execute

# 定期保守ジョブを手動実行（job_logs に記録）
PYTHONUNBUFFERED=1 PYTHONPATH=src uv run python -m app.services.data_loader \
  run-recipe-maintenance --triggered-by manual
```

運用メモ:

- `repair-youtube-nutrition` は既存 YouTube レシピの食材マッチングと栄養計算をやり直します。
- `rebuild-recipe-ingredients` は `recipe_ingredients` をレシピ単位で削除して再構築します。重複行や古い raw 行が疑われるときに使います。
- `prune-non-meal-recipes` は Gemini 品質ゲートで既存レシピを再判定します。まず dry-run を見てから `--execute` を使ってください。
- `run-recipe-maintenance` は `refresh-recipes` → `backfill` → `prune-non-meal-recipes --execute` を順番に実行し、各試行を `job_logs` に保存します。
- GitHub Actions では `.github/workflows/recipe-maintenance.yml` を使います。必要な secrets は `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `RAKUTEN_APP_ID`, `RAKUTEN_ACCESS_KEY`, `GOOGLE_API_KEY` です。
- 定期ジョブが失敗した場合は GitHub Actions の failed run と `job_logs` を見て、どのジョブが何回目で失敗したかを確認してください。
- `upsert_recipe()` は `recipes` テーブルだけを更新し、材料行の保存は行いません。`recipe_ingredients` の正規な更新経路は `match_recipe_ingredients()` です。
- `match_recipe_ingredients()` は対象レシピの既存材料行を毎回置換してから insert するため、raw 材料とマッチ済み材料の二重登録を防ぎます。

## YouTube 管理API（管理者）

管理者トークンは Supabase Auth の `grant_type=password` で取得できます。

```bash
ANON_KEY=<NEXT_PUBLIC_SUPABASE_ANON_KEY>
ADMIN_TOKEN=$(curl -sS 'http://localhost:54321/auth/v1/token?grant_type=password' \
  -H "apikey: ${ANON_KEY}" \
  -H "Authorization: Bearer ${ANON_KEY}" \
  -H 'Content-Type: application/json' \
  --data '{"email":"test@test.com","password":"test1234"}' | python -c 'import json,sys;print(json.load(sys.stdin)["access_token"])')
```

主要エンドポイント:

```bash
# 1) 単一URL: 字幕抽出
curl -sS -X POST 'http://localhost:8000/admin/youtube/extract' \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.youtube.com/watch?v=<video_id>","staple_name":"冷凍うどん"}'

# 2) 単一URL: DB登録
curl -sS -X POST 'http://localhost:8000/admin/youtube/register' \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{"video_id":"<video_id>","recipe_data":{...}}'

# 3) チャンネル一括: source_query -> target_staple 変換して登録
curl -sS -X POST 'http://localhost:8000/admin/youtube/batch-adapt' \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{"channel_handle":"@yugetube2020","source_query":"パスタ","target_staple":"冷凍うどん","max_results":10}'

# 4) YouTube登録済み一覧
curl -sS 'http://localhost:8000/admin/youtube/recipes?page=1&per_page=20' \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"
```

運用メモ:

- `extract` は字幕を取得して draft を返します。自動字幕は自然化を試み、失敗時は raw transcript で続行します。
- `register` は DB 登録前に Gemini 品質ゲートを通します。非食事レシピは `422` で拒否されます。
- `batch-adapt` は `source_query='パスタ'` の場合、動画タイトルが実際にパスタ動画であることを厳格に確認します。検索結果に混ざる雑音動画は `filtered_source_mismatch` になります。
- `batch-adapt` ではタイトルの非食事キーワード除外、字幕取得、抽出後の品質ゲート、主食アレンジ後の付け合わせ除外、最終品質ゲートを通過したものだけが登録されます。
- `no_transcript` は字幕がない動画です。運用上はスキップして問題ありません。

主な `batch-adapt` status:

| status | 意味 |
|---|---|
| `success` | 抽出・アレンジ・登録まで完了 |
| `skipped_existing` | 同じ `youtube_video_id` が既に登録済み |
| `filtered_source_mismatch` | 検索結果に出たが source query の意図とタイトルが一致しない |
| `filtered_non_meal` | Gemini 品質ゲートで非食事と判定 |
| `filtered_accompaniment` | 主食の付け合わせと判定され登録対象外 |
| `no_transcript` | 字幕取得に失敗、または字幕が存在しない |
| `extraction_failed` | 字幕からレシピ構造を抽出できなかった |
| `adaptation_failed` | 主食アレンジ生成に失敗 |
| `registration_failed` | DB 登録または後続処理に失敗 |

管理画面の `/admin/youtube` も同じ API を使っており、単一 URL 登録と一括アレンジの両方に対応しています。詳細な運用手順は [doc/youtube_recipe_ops.md](../doc/youtube_recipe_ops.md) を参照してください。

## YouTube 運用上の制約

- 字幕がない動画は `no_transcript` で終了します。
- 自動字幕の自然化は失敗することがありますが、その場合は raw transcript にフォールバックします。
- `rebuild-recipe-ingredients` 実行後も再構築に失敗するレシピが残ることがあります。その場合はタイトルと `recipe_id` を記録して個別調査してください。

## 再生成テスト（YouTubeが候補に出るか）

1. `POST /plans/weekly` を `mode=recipe`, `staple_name=冷凍うどん` で作成。
2. 週内の `plan_id` に対して `PATCH /plans/{plan_id}/recipe` を複数回実行。
3. 返却の `meal_plan[].recipe.recipe_url` が `youtube.com` か `recipe.rakuten.co.jp` かを集計。

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
