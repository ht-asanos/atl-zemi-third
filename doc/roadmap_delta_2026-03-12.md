# Roadmap差分メモ (2026-03-12)

`doc/roadmap.md` と、2026-03-12 時点の実装差分を記録する。
本ドキュメントは「ロードマップ本体の修正前に先行で反映された変更点」の一覧である。

---

## 1. Phase 2.5 記述との差分

### 1-1. 楽天レシピAPI認証方式
- `roadmap.md` では「Bearer 認証対応済み」と読める記述になっているが、実装は `applicationId` + `accessKey` のクエリパラメータ方式に修正済み。
- 対象: `backend/src/app/services/rakuten_recipe.py`

### 1-2. レシピ更新/補完APIの実装状況
- `roadmap.md` の「`POST /recipes/refresh` 未実装」は現状と不一致。
- 実際には以下が実装済み:
  - `POST /recipes/refresh`
  - `POST /recipes/backfill`
- 対象: `backend/src/app/routers/recipes.py`, `backend/src/app/services/recipe_refresh.py`

### 1-3. MEXTスクレイパー仕様
- `fooddb.mext.go.jp` の現行DOM/検索仕様に合わせてスクレイパーを更新済み。
- カテゴリID形式の変更（例: `7_11_11214`）にも対応済み。
- 対象: `backend/src/app/services/mext_scraper.py`, `backend/src/app/services/data_loader.py`

---

## 2. Phase 4 進捗との差分

### 2-1. 4-4 以外も先行実装済み
- `roadmap.md` は「Phase 4 これから着手」の表現だが、以下は実装済み:
  - 4-1 買い物リスト (`GET /plans/weekly/shopping-list`)
  - 4-2 夕食レシピ差し替え (`PATCH /plans/{plan_id}/recipe`)
  - 4-4 `json.dumps` 二重シリアライズ修正
  - 4-6 お気に入り機能（API + 優先選出）

### 2-2. 食材栄養の永続化（ロードマップ外の先行拡張）
- `recipe_ingredients` に食材単位の栄養列を追加済み:
  - `kcal`, `protein_g`, `fat_g`, `carbs_g`
- Migration: `backend/supabase/migrations/009_recipe_ingredient_nutrition.sql`

### 2-3. 夕食レシピの栄養表示
- プランの dinner `recipe` に `nutrition_per_serving` を含める実装を追加済み。
- フロントの meal セクションで「食材合算栄養 (1人前)」を表示。
- 対象:
  - `backend/src/app/services/meal_suggestion.py`
  - `frontend/src/components/plans/meal-section.tsx`
  - `frontend/src/types/plan.ts`

---

## 3. 運用上の注意（現状）

### 3-1. 既存プランはスナップショット
- `daily_plans.meal_plan` は生成時JSONを保持するため、`recipes` テーブル更新だけでは既存プランに新しい `nutrition_per_serving` は自動反映されない。
- 反映には以下が必要:
  - 再生成（新規 weekly plan）
  - または既存 `meal_plan` のバックフィル更新

### 3-2. 栄養計算の成立条件
- 楽天レシピ由来データは分量欠損が多く、厳密計算だけでは `nutrition_per_serving` が空になりやすい。
- 現在は分量不明時に推定gを使うフォールバックを導入済み（調味料/油/その他）。
- 対象: `backend/src/app/services/ingredient_matcher.py`

### 3-3. ローカル環境（SSL）
- ローカル環境でMEXTや外部API接続時に証明書エラーが起きる場合、`SSL_CERT_FILE` 等のCAバンドル指定が必要。

---

## 4. 次に roadmap 本体へ反映すべき点

1. Phase 2.5 の「未実装」記述（refresh/backfill）を現状に合わせて更新する。
2. Phase 4 のステータスを「着手前」から「一部完了」に更新する。
3. 「食材単位栄養の永続化 + フロント表示」を Phase 4 実績または Phase 4.x 補足として追記する。
4. `daily_plans` がスナップショット保持であることを運用注意として明記する。
