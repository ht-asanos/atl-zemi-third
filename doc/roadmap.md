# Roadmap: 一人暮らし向け自炊 x トレーニング最適化アプリ

本ロードマップはコードベースの実装状況を正確に反映し、今後の開発方針を示すものである。

差分メモ（2026-03-12）: [roadmap_delta_2026-03-12.md](/Users/hdymacuser/WorkSpace/260401dtzemi/atl-zemi-third/doc/roadmap_delta_2026-03-12.md)

---

## 技術構成

| レイヤー | 技術 |
|---|---|
| Frontend | Next.js 15 (App Router, TypeScript, Tailwind CSS v4, shadcn/ui) |
| Backend | FastAPI (Python 3.11, uv) |
| DB / Auth / Storage | Supabase (PostgreSQL + Auth + Storage) |
| AI | ChatGPT API (感想タグ抽出) |
| 外部データ | MEXT 食品成分データベース (スクレイピング)、楽天レシピ API |
| テスト / Lint | pytest, ruff, ty, pre-commit, ESLint |

---

## API 設計方針

| 方針 | 詳細 |
|---|---|
| 冪等性 | POST 系エンドポイントは `Idempotency-Key` ヘッダーに対応する。重複リクエストは 409 Conflict を返す |
| 所有権 | 全 API で `user_id` は JWT クレームから取得する。パスパラメータやリクエストボディでの指定は不可 |
| エラーコード | 重複送信: 409 Conflict / バリデーション違反: 422 Unprocessable Entity |

---

## 完了済みフェーズ（実績記録）

### Phase 1（完了）: データモデル + 計算エンジン

**目的:** アプリの基盤となるデータ構造と栄養計算ロジックを構築する。

- 栄養計算エンジン（BMR / TDEE / PFC 目標算出）
- 食材マスタ（主食 5 種 + タンパク源 4 種 + かさ増し 3 種） — `backend/src/app/data/food_master.py`
- トレーニングテンプレート（diet / strength / bouldering）
- 食事提案ロジック（主食選択 → 残枠計算 → 組み合わせ生成）
- ユニットテスト一式（177 tests passing）

---

### Phase 2（安定化中）: 週次プラン生成 API + UI

**目的:** ユーザーが初期設定を行い、1 週間分のメニューを確認できる状態にする。

- Profile / Goal API（`POST /profiles`, `GET /profiles/me`, `POST /goals`, `GET /goals/me`）
- 週次プラン生成（classic + recipe モード）— `POST /plans/weekly`, `GET /plans/weekly?start_date=`
- 主食変更 API — `PATCH /plans/{id}/meal`
- Supabase Auth 連携（cookie ベース SSR、`@supabase/ssr`）
- フロントエンド（ログイン → 設定 → 主食選択 → 週間プラン表示）
- Middleware による認証保護（`/setup`, `/staple`, `/plans` へのアクセス制御）

**既知の不具合:**
- 実 DB 経路で `json.dumps` 二重シリアライズ起因のエラーが発生する可能性あり
- ユニットテスト（mock）は全て通過するが、結合テスト（実 Supabase）での検証が未完了

---

### Phase 3（完了）: ログ収集 + 感想解析 + 適応

**目的:** 日々の実行記録と感想から次回提案を自動調整する仕組みを構築する。

- 食事ログ / トレーニングログ API（`POST /logs/meal`, `POST /logs/workout`, `GET`）
- ChatGPT タグ抽出（5 タグ: `too_hard`, `cannot_complete_reps`, `forearm_sore`, `bored_staple`, `too_much_food`）
- ルールベース適応エンジン + 楽観ロック + リビジョン保存（`plan_revisions`）
- フロントエンド日次ページ（ログ記録 + フィードバック入力・結果表示）
- E2E シナリオテスト（設定 → 生成 → ログ → 感想 → 適応の全フロー）

---

### Phase 2.5（部分完了 — ロードマップ外で実装）: レシピ統合

**目的:** 外部レシピデータを取り込み、具体的なレシピ名で献立を提案する。

**実装済み:**
- MEXT 食品 DB スクレイパー（9 カテゴリ対応）+ 食材マッチング（fuzzy match + 信頼度スコア）
- 楽天レシピ API クライアント（新 URL + Bearer 認証対応済み）+ DB キャッシュ（`recipes` / `recipe_ingredients` テーブル）
- レシピモード v3（朝食固定 + 昼食固定 + 夕食日替わりレシピ、PFC フィルタ付き）
- フロントエンドでモード切替（classic / recipe）

**未完了サブタスク:**
- レシピ更新は CLI（`data_loader.py`）のみ。API エンドポイント（`POST /recipes/refresh`）は未実装
- `backfill` コマンドのスクレイピング補完は未実装（コード内に `NOTE: 未実装` と明記）
- 食材マッチングの手動レビューフロー（`manual_review_needed` フラグは保存されるが UI なし）

---

## 今後のフェーズ

### Phase 4: 日常使いの実用性強化（次に着手）

**目的:** 買い物・レシピ差し替え・データ安定性など、日常利用に必要な機能を整備する。

| # | タスク | レイヤー | 優先度 | 備考 |
|---|---|---|---|---|
| 4-1 | 買い物リスト自動生成 | Backend + Frontend | 高 | 週次レシピの `recipe_ingredients` を集約、カテゴリ別・重複マージ表示。新 API: `GET /plans/weekly/shopping-list` |
| 4-2 | レシピモードの夕食再抽選 | Backend + Frontend | 高 | 新 API: `PATCH /plans/{id}/recipe`。**影響範囲**: `schemas/plan.py`（新スキーマ）、`frontend/src/types/plan.ts`（型追加）、`adaptation_engine`（recipe モード対応）、`plan_revisions`（リビジョン保存）。後方互換: classic モードの `PATCH /plans/{id}/meal` は変更しない |
| 4-3 | レシピプール定期自動更新 | Backend + Infra | 高 | **実行基盤**: GitHub Actions (cron schedule) or Supabase Edge Functions。**要件**: 週1回実行、失敗時 3 回リトライ + Slack/メール通知、実行履歴を `job_logs` テーブルに保存。既存 `cmd_refresh_recipes()` を API 化 or GitHub Actions workflow でラップ |
| 4-4 | Phase 2 実 DB 経路のバグ修正 | Backend | 高 | `meal_plan` の JSON シリアライズ問題を特定・修正、実 Supabase での結合テスト追加 |
| 4-5 | 食事写真アップロード | Backend + Frontend | 中 | Supabase Storage（private バケット）、署名 URL（TTL 15分）、ログ画面にカメラ UI |
| 4-6 | レシピお気に入り機能 | Backend + Frontend | 中 | `user_recipe_favorites` テーブル追加、次回プラン生成時に優先選出 |

**Exit Criteria（機能）:**
- 買い物リスト画面で週間レシピの必要食材が一覧表示される
- 夕食レシピを1日単位で差し替えでき、PFC が再計算される
- DB 内レシピが週1回自動更新され、失敗時にアラートが飛ぶ
- `POST /plans/weekly` が実 DB で正常動作する（classic / recipe 両モード）

**Exit Criteria（KPI）:**
- 生成失敗率 < 1%（実 DB 経路での 5xx エラー率）
- 夕食レシピ重複率 = 0%（7日間で同一レシピなし）
- 目標 PFC 乖離 < 20%（夕食の protein が dinner_budget の 80-120% 範囲内）

---

### Phase 5: パーソナライズ + データ蓄積

**目的:** ユーザーの身体データと嗜好を蓄積し、提案の精度を高める。

| # | タスク | レイヤー | 優先度 |
|---|---|---|---|
| 5-1 | 体重・体組成の記録 API + 進捗グラフ UI | Backend + Frontend | 高 |
| 5-2 | 食事嗜好学習（過去ログの好み傾向 → プラン生成に反映） | Backend | 中 |
| 5-3 | 食材マスタ拡充（MEXT 全カテゴリ + backfill スクレイピング補完の実装） | Backend | 中 |
| 5-4 | 週次サマリー通知（実行率・PFC 達成率のメール or Push） | Backend | 低 |

**Exit Criteria（機能）:**
- 体重推移グラフが表示され、目標との差分が可視化される
- ログ蓄積に応じて提案レシピのパーソナライズが体感できる

**Exit Criteria（KPI）:**
- 週間実行率（ログ記録日数 / 7）の可視化が機能すること
- 嗜好反映後のレシピ満足度（ログの satisfaction スコア平均）が反映前より向上

---

### Phase 6: 運用安定 + 高度な機能

**目的:** 運用品質の確保と将来の拡張基盤を整備する。

| # | タスク | レイヤー | 優先度 |
|---|---|---|---|
| 6-1 | アカウント削除フロー（データ + Storage 物理削除、72h 以内） | Backend + Supabase | 高 |
| 6-2 | API レスポンスタイム監視（P95 閾値: `/plans/weekly` < 5s, `/feedback` < 3s, その他 < 2s） | Backend | 中 |
| 6-3 | 週次実行率・継続率ダッシュボード（管理用） | Frontend | 中 |
| 6-4 | PWA 対応（モバイル通知 + オフラインキャッシュ） | Frontend | 低 |
| 6-5 | 適応エンジンの ML 化（ルールベース → 学習ベース） | Backend | 低 |

**Exit Criteria（KPI）:**
- 全エンドポイントで P95 応答時間が上記基準を達成
- 退会後 72h 以内にデータ + Storage が物理削除されること

---

## フェーズ進行まとめ

```
Phase 1 (基盤) ✅ → Phase 2 (MVP コア) 🔧安定化中 → Phase 3 (適応) ✅
                          ↓
                   Phase 2.5 (レシピ統合) ⚠️部分完了
                          ↓
              Phase 4 (実用性強化) → Phase 5 (パーソナライズ) → Phase 6 (運用・拡張)
```
